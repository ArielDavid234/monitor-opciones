"""
Análisis de proyecciones fundamentales y técnicas de empresas a 10 años.
Combina análisis fundamental (valor intrínseco) y técnico (precio/volumen)
para identificar oportunidades de compra o venta.

Incluye predicción básica de volatilidad implícita (IV) con regresión lineal.
"""
import logging
import numpy as np
import pandas as pd
import yfinance as yf

from config.constants import SCORE_THRESHOLD_ALTA, SCORE_THRESHOLD_MEDIA
from core.scanner import crear_sesion_nueva

logger = logging.getLogger(__name__)


# ============================================================================
#        PREDICCIÓN DE IV  (regresión lineal — explicable)
# ============================================================================

def predict_implied_volatility(
    df_historical: pd.DataFrame,
    forecast_days: int = 5,
) -> dict:
    """Predice IV futura usando regresión lineal sobre datos históricos.

    Modelo simple y transparente: usa features observables del mercado
    (HV, VIX, volumen, precio) para estimar hacia dónde se dirige la IV.

    El objetivo es dar al usuario una referencia cuantitativa para decidir
    si la volatilidad está subiendo (primas caras → vender vol) o bajando
    (primas baratas → comprar vol).

    Features:
      - hv_20d      : volatilidad histórica 20d (momentum de vol)
      - vix_close   : VIX (miedo de mercado / proxy IV SPX)
      - volume      : volumen del subyacente (liquidez / interés)
      - close_price : precio del subyacente (correlación inversa con IV)

    Args:
        df_historical: DataFrame de get_historical_iv() con columnas
                       [date, close_price, volume, hv_20d, vix_close, iv_mean].
        forecast_days: Días hacia adelante para la predicción (default 5).

    Returns:
        dict con:
          predicted_iv   : IV predicha (%)
          forecast_days  : días de forecast
          forecast_range : [iv_baja, iv_alta] — banda ± 1 std error
          r2_score       : R² del modelo en test set
          model_features : lista de features usadas
          coefficients   : dict feature→coeficiente (para transparencia)
          current_iv     : IV actual (último dato)
          interpretation : texto explicativo para el usuario
          direction      : "up" | "down" | "stable"
        O dict con clave "error" si datos insuficientes.
    """
    try:
        from sklearn.linear_model import LinearRegression
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import r2_score
    except ImportError:
        return {"error": "scikit-learn no instalado — predicción IV no disponible"}

    # ── Validación de datos ──────────────────────────────────────
    required_cols = {"hv_20d", "vix_close", "volume", "close_price", "iv_mean"}
    if not isinstance(df_historical, pd.DataFrame) or df_historical.empty:
        return {"error": "DataFrame vacío"}

    missing = required_cols - set(df_historical.columns)
    if missing:
        return {"error": f"Columnas faltantes: {missing}"}

    df = df_historical.dropna(subset=list(required_cols)).copy()
    if len(df) < 30:
        return {"error": f"Datos insuficientes ({len(df)} filas, mínimo 30)"}

    # ── Features y target ────────────────────────────────────────
    features = ["hv_20d", "vix_close", "volume", "close_price"]
    X = df[features].values
    y = df["iv_mean"].values

    # ── Train/Test split ─────────────────────────────────────────
    test_size = max(0.2, 10 / len(X))  # mínimo 10 muestras en test
    test_size = min(test_size, 0.4)     # máximo 40%
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42,
    )

    # ── Entrenar modelo ──────────────────────────────────────────
    model = LinearRegression()
    model.fit(X_train, y_train)

    y_pred_test = model.predict(X_test)
    r2 = r2_score(y_test, y_pred_test)

    # ── Forecast: extrapolar desde las últimas features ──────────
    last_row = df[features].iloc[-1].values.reshape(1, -1)
    predicted_iv = float(model.predict(last_row)[0])

    # Banda de confianza: ± 1 desviación estándar del error
    residuals = y_test - y_pred_test
    pred_std = float(np.std(residuals))
    iv_low = predicted_iv - pred_std
    iv_high = predicted_iv + pred_std

    # ── IV actual y dirección ────────────────────────────────────
    current_iv = float(df["iv_mean"].iloc[-1])
    delta_iv = predicted_iv - current_iv

    if delta_iv > 1.0:
        direction = "up"
    elif delta_iv < -1.0:
        direction = "down"
    else:
        direction = "stable"

    # ── Interpretación financiera ────────────────────────────────
    if direction == "up":
        interp = (
            f"📈 IV predicha **{predicted_iv:.1f}%** (actual {current_iv:.1f}%) "
            f"→ Volatilidad **SUBIENDO** (+{delta_iv:.1f}pp). "
            f"Primas se encarecen — considerar **vender volatilidad** "
            f"(credit spreads, iron condors, covered calls)."
        )
    elif direction == "down":
        interp = (
            f"📉 IV predicha **{predicted_iv:.1f}%** (actual {current_iv:.1f}%) "
            f"→ Volatilidad **BAJANDO** ({delta_iv:.1f}pp). "
            f"Primas se abaratan — considerar **comprar volatilidad** "
            f"(long straddles, debit spreads, protective puts)."
        )
    else:
        interp = (
            f"↔️ IV predicha **{predicted_iv:.1f}%** (actual {current_iv:.1f}%) "
            f"→ Volatilidad **ESTABLE** ({delta_iv:+.1f}pp). "
            f"Sin edge claro en volatilidad — evaluar dirección del subyacente."
        )

    # ── Coeficientes (transparencia) ─────────────────────────────
    coefs = {feat: round(float(c), 6) for feat, c in zip(features, model.coef_)}

    return {
        "predicted_iv": round(predicted_iv, 2),
        "forecast_days": forecast_days,
        "forecast_range": [round(iv_low, 2), round(iv_high, 2)],
        "r2_score": round(r2, 3),
        "model_features": features,
        "coefficients": coefs,
        "current_iv": round(current_iv, 2),
        "delta_iv": round(delta_iv, 2),
        "direction": direction,
        "interpretation": interp,
        "n_samples": len(df),
        "pred_std": round(pred_std, 2),
    }


# ============================================================================
#        ENRICHMENT — Datos fundamentales vía Alpha Vantage
# ============================================================================

def _get_fundamentals_yfinance(ticker: str) -> dict:
    """Obtiene fundamentales desde yfinance (fallback gratuito sin API key).

    Devuelve el mismo esquema de dict que get_alpha_vantage_fundamentals.
    """
    try:
        session, _ = crear_sesion_nueva()
        t = yf.Ticker(ticker, session=session)
        info = t.info or {}

        def _sf(key, factor=1.0):
            v = info.get(key)
            try:
                f = float(v) * factor
                return f if not (f != f) else None  # NaN check
            except (TypeError, ValueError):
                return None

        # Earnings history (surprise %)
        quarterly_earnings = []
        last_surprise_pct = None
        last_reported_date = "N/A"
        earnings_beat_streak = 0
        try:
            eh = t.earnings_history
            if eh is not None and not eh.empty:
                for _, row in eh.head(8).iterrows():
                    eps_est = row.get("epsEstimate") if hasattr(row, "get") else row["epsEstimate"]
                    eps_rep = row.get("epsActual") if hasattr(row, "get") else row["epsActual"]
                    surp = row.get("surprisePercent") if hasattr(row, "get") else row["surprisePercent"]
                    date_str = str(row.name.date()) if hasattr(row.name, "date") else str(row.name)
                    try:
                        surp_f = float(surp) * 100 if surp is not None else 0.0
                    except (TypeError, ValueError):
                        surp_f = 0.0
                    quarterly_earnings.append({
                        "date": date_str,
                        "reported_eps": float(eps_rep) if eps_rep is not None else 0.0,
                        "estimated_eps": float(eps_est) if eps_est is not None else 0.0,
                        "surprise_pct": round(surp_f, 2),
                    })
                if quarterly_earnings:
                    last_surprise_pct = quarterly_earnings[0]["surprise_pct"]
                    last_reported_date = quarterly_earnings[0]["date"]
                    for q in quarterly_earnings:
                        if q["surprise_pct"] > 0:
                            earnings_beat_streak += 1
                        else:
                            break
        except Exception:
            pass

        short_pct = _sf("shortPercentOfFloat", 100) or 0.0

        return {
            "peg_ratio": _sf("pegRatio"),
            "pe_forward": _sf("forwardPE"),
            "pe_trailing": _sf("trailingPE"),
            "ev_to_ebitda": _sf("enterpriseToEbitda"),
            "book_value": _sf("bookValue"),
            "revenue_ttm": _sf("totalRevenue") or 0,
            "eps_ttm": _sf("trailingEps"),
            "profit_margin": round(_sf("profitMargins", 100) or 0, 2) or None,
            "gross_margin_pct": round(_sf("grossMargins", 100) or 0, 2),
            "operating_margin": round(_sf("operatingMargins", 100) or 0, 2) or None,
            "roe": round(_sf("returnOnEquity", 100) or 0, 2) or None,
            "roa": round(_sf("returnOnAssets", 100) or 0, 2) or None,
            "short_interest_pct": round(short_pct, 2),
            "beta": _sf("beta"),
            "dividend_yield": round(_sf("dividendYield", 100) or 0, 2) or None,
            "analyst_target": _sf("targetMeanPrice"),
            "week_52_high": _sf("fiftyTwoWeekHigh") or 0,
            "week_52_low": _sf("fiftyTwoWeekLow") or 0,
            "last_earnings_date": last_reported_date,
            "last_surprise_pct": last_surprise_pct,
            "earnings_beat_streak": earnings_beat_streak,
            "quarterly_earnings": quarterly_earnings,
            "name": info.get("longName") or info.get("shortName", ticker),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "description": info.get("longBusinessSummary", ""),
            "source": "Yahoo Finance",
        }
    except Exception as e:
        return {"error": f"yfinance fundamentals error: {e}"}


def enrich_with_fundamentals(ticker: str) -> dict:
    """Enriquece el análisis de un ticker con datos fundamentales.

    Intenta Alpha Vantage primero; si no hay API key configurada, usa
    yfinance como fallback gratuito con el mismo esquema de datos.

    Args:
        ticker: Símbolo del activo (e.g. "AAPL").

    Returns:
        dict con fundamentals enriquecidos + interpretación, o dict con "error".
    """
    try:
        from infrastructure.api_integrations import get_alpha_vantage_fundamentals
        raw = get_alpha_vantage_fundamentals(ticker)
    except ImportError:
        raw = {"error": "api_integrations no disponible"}

    # Si Alpha Vantage falla por falta de key (o cualquier error), usar yfinance
    if "error" in raw:
        logger.info("%s: Alpha Vantage no disponible (%s) — usando yfinance fallback", ticker, raw["error"][:60])
        raw = _get_fundamentals_yfinance(ticker)

    if "error" in raw:
        return raw

    # ── Interpretaciones financieras ─────────────────────────────
    signals = []
    score_adjustment = 0  # ajuste al score de proyección

    # PEG
    peg = raw.get("peg_ratio")
    if peg is not None and peg > 0:
        if peg < 1.0:
            signals.append(f"📗 PEG **{peg:.2f}** → Infravalorada vs crecimiento (oportunidad)")
            score_adjustment += 8
        elif peg < 1.5:
            signals.append(f"📗 PEG **{peg:.2f}** → Valuación razonable")
            score_adjustment += 3
        elif peg < 2.5:
            signals.append(f"📙 PEG **{peg:.2f}** → Moderadamente cara")
        else:
            signals.append(f"📕 PEG **{peg:.2f}** → Sobrevalorada — precaución")
            score_adjustment -= 5

    # Earnings surprise
    surprise = raw.get("last_surprise_pct")
    beat_streak = raw.get("earnings_beat_streak", 0)
    if surprise is not None:
        if surprise > 10:
            signals.append(
                f"📈 Earnings surprise **+{surprise:.1f}%** "
                f"({'racha de ' + str(beat_streak) + ' beats' if beat_streak > 1 else 'último quarter'})"
                f" → Momentum positivo"
            )
            score_adjustment += 5
        elif surprise > 0:
            signals.append(f"📈 Earnings surprise **+{surprise:.1f}%** → Beat moderado")
            score_adjustment += 2
        elif surprise < -5:
            signals.append(f"📉 Earnings surprise **{surprise:.1f}%** → Miss significativo — riesgo")
            score_adjustment -= 5
        else:
            signals.append(f"📉 Earnings surprise **{surprise:.1f}%** → Ligero miss")
            score_adjustment -= 2

    # Short interest
    short_pct = raw.get("short_interest_pct", 0)
    if short_pct > 20:
        signals.append(f"🔴 Short Interest **{short_pct:.1f}%** → Muy alto — posible squeeze o caída")
        score_adjustment -= 3
    elif short_pct > 10:
        signals.append(f"🟡 Short Interest **{short_pct:.1f}%** → Alto — vigilar cobertura corta")
    elif short_pct > 5:
        signals.append(f"🟡 Short Interest **{short_pct:.1f}%** → Moderado")
    elif short_pct > 0:
        signals.append(f"🟢 Short Interest **{short_pct:.1f}%** → Bajo — sentimiento positivo")
        score_adjustment += 2

    # ROE
    roe = raw.get("roe")
    if roe is not None and roe > 0:
        if roe > 25:
            signals.append(f"💪 ROE **{roe:.1f}%** → Retorno excepcional sobre capital")
            score_adjustment += 3
        elif roe > 15:
            signals.append(f"📗 ROE **{roe:.1f}%** → Retorno sólido")
        elif roe > 0:
            signals.append(f"📙 ROE **{roe:.1f}%** → Retorno modesto")

    # Profit margin
    pm = raw.get("profit_margin")
    if pm is not None and pm > 0:
        if pm > 20:
            signals.append(f"💰 Margen neto **{pm:.1f}%** → Alta rentabilidad")
        elif pm > 10:
            signals.append(f"📗 Margen neto **{pm:.1f}%** → Saludable")

    # Dividendo
    div_yield = raw.get("dividend_yield")
    if div_yield is not None and div_yield > 0:
        signals.append(f"💵 Dividendo **{div_yield:.2f}%** anual")

    # ── Summary interpretation ───────────────────────────────────
    if score_adjustment > 5:
        overall = "🟢 **Fundamentales favorables** — refuerzan tesis alcista en opciones"
    elif score_adjustment > 0:
        overall = "🟡 **Fundamentales neutros-positivos** — sin señales de alarma"
    elif score_adjustment > -5:
        overall = "🟡 **Fundamentales mixtos** — evaluar con cautela"
    else:
        overall = "🔴 **Fundamentales débiles** — riesgo elevado en operaciones con opciones"

    enriched = {
        **raw,
        "signals": signals,
        "score_adjustment": score_adjustment,
        "overall_interpretation": overall,
    }

    logger.info(f"{ticker}: Enrichment OK — {len(signals)} señales, adj={score_adjustment:+d}")
    return enriched


# ============================================================================
#        PROYECCIONES FUNDAMENTALES (existente)
# ============================================================================


def analizar_proyeccion_empresa(symbol, info_empresa=None):
    """
    Analiza los fundamentales de una empresa vía yfinance para evaluar
    su potencial de crecimiento a largo plazo (10 años).

    Usa datos gratuitos: crecimiento de ingresos, márgenes,
    recomendaciones de analistas, flujo de caja, etc.

    Returns:
        dict con métricas y score, o None + error
    """
    try:
        session, perfil = crear_sesion_nueva()
        ticker = yf.Ticker(symbol, session=session)

        info = ticker.info or {}

        # Datos básicos
        nombre = info.get("longName") or info.get("shortName", symbol)
        precio = info.get("currentPrice") or info.get("regularMarketPrice", 0)
        market_cap = info.get("marketCap", 0)
        sector_yf = info.get("sector", "N/A")
        industria = info.get("industry", "N/A")

        # Métricas de crecimiento
        revenue_growth = info.get("revenueGrowth", 0)  # QoQ
        earnings_growth = info.get("earningsGrowth", 0)
        revenue = info.get("totalRevenue", 0)
        gross_margins = info.get("grossMargins", 0)
        operating_margins = info.get("operatingMargins", 0)
        profit_margins = info.get("profitMargins", 0)

        # Valuación
        forward_pe = info.get("forwardPE", 0)
        trailing_pe = info.get("trailingPE", 0)
        peg_ratio = info.get("pegRatio", 0)
        
        # *** CALCULAR PEG MANUALMENTE SI NO ESTÁ DISPONIBLE ***
        # PEG = PER / Tasa de crecimiento anual del BPA (%)
        # Si Yahoo no provee PEG, lo calculamos nosotros
        if not peg_ratio or peg_ratio <= 0:
            # Usar el PER más confiable que tengamos
            pe_to_use = forward_pe if forward_pe and forward_pe > 0 else trailing_pe
            # Convertir earningsGrowth (decimal) a porcentaje
            earnings_growth_pct = earnings_growth * 100 if earnings_growth else 0
            
            if pe_to_use and pe_to_use > 0 and earnings_growth_pct > 0:
                # PEG = PER / % de crecimiento
                peg_ratio = pe_to_use / earnings_growth_pct
                logger.info(f"{symbol}: PEG calculado manualmente = {peg_ratio:.3f} (PER={pe_to_use:.1f}, Crec={earnings_growth_pct:.1f}%)")
        
        price_to_sales = info.get("priceToSalesTrailing12Months", 0)

        # Analistas
        target_mean = info.get("targetMeanPrice", 0)
        target_high = info.get("targetHighPrice", 0)
        target_low = info.get("targetLowPrice", 0)
        recommendation = info.get("recommendationKey", "N/A")
        num_analysts = info.get("numberOfAnalystOpinions", 0)

        # Flujo de caja
        free_cashflow = info.get("freeCashflow", 0)
        operating_cashflow = info.get("operatingCashflow", 0)

        # Beta (volatilidad vs mercado)
        beta = info.get("beta", 0)

        # Performance histórico (52 semanas)
        fifty_two_high = info.get("fiftyTwoWeekHigh", 0)
        fifty_two_low = info.get("fiftyTwoWeekLow", 0)

        # Upside potencial según analistas
        upside_pct = 0
        if precio and target_mean:
            upside_pct = ((target_mean - precio) / precio) * 100

        # === ANÁLISIS TÉCNICO (Precio, Indicadores, Volumen) ===
        tecnico = {}
        try:
            hist = ticker.history(period="1y")
            if not hist.empty and len(hist) >= 20:
                close = hist['Close']
                high = hist['High']
                low = hist['Low']
                volume = hist['Volume']

                # — Medias Móviles (SMA 20, 50, 200) —
                sma_20 = close.rolling(20).mean()
                sma_50 = close.rolling(50).mean()
                sma_200 = close.rolling(200).mean() if len(close) >= 200 else pd.Series([None] * len(close), index=close.index)

                # — RSI (14 periodos) —
                delta_price = close.diff()
                gain = delta_price.where(delta_price > 0, 0).rolling(14).mean()
                loss_val = (-delta_price.where(delta_price < 0, 0)).rolling(14).mean()
                rs = gain / loss_val
                rsi_series = 100 - (100 / (1 + rs))

                # — ADX (14 periodos) — Fuerza de la tendencia
                tr = pd.DataFrame({
                    'hl': high - low,
                    'hc': abs(high - close.shift(1)),
                    'lc': abs(low - close.shift(1))
                }).max(axis=1)
                plus_dm = high.diff()
                minus_dm = -low.diff()
                plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
                minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
                atr_14 = tr.rolling(14).mean()
                plus_di = 100 * (plus_dm.rolling(14).mean() / atr_14)
                minus_di = 100 * (minus_dm.rolling(14).mean() / atr_14)
                di_sum = plus_di + minus_di
                di_sum = di_sum.replace(0, 1)  # evitar div/0
                dx = 100 * abs(plus_di - minus_di) / di_sum
                adx_series = dx.rolling(14).mean()

                # — Valores actuales —
                current = close.iloc[-1]
                sma20_val = sma_20.iloc[-1] if pd.notna(sma_20.iloc[-1]) else 0
                sma50_val = sma_50.iloc[-1] if pd.notna(sma_50.iloc[-1]) else 0
                sma200_val = sma_200.iloc[-1] if pd.notna(sma_200.iloc[-1]) else 0
                rsi_val = rsi_series.iloc[-1] if pd.notna(rsi_series.iloc[-1]) else 50
                adx_val = adx_series.iloc[-1] if pd.notna(adx_series.iloc[-1]) else 0

                # — Determinación de Tendencia —
                if sma20_val > 0 and sma50_val > 0:
                    if current > sma20_val and sma20_val > sma50_val:
                        tendencia = "ALCISTA"
                    elif current < sma20_val and sma20_val < sma50_val:
                        tendencia = "BAJISTA"
                    else:
                        tendencia = "LATERAL"
                else:
                    tendencia = "N/D"

                # — Análisis de Volumen —
                avg_vol_20 = volume.rolling(20).mean().iloc[-1]
                recent_vol = volume.tail(5).mean()
                vol_ratio = round(recent_vol / avg_vol_20, 2) if avg_vol_20 > 0 else 1.0

                # — Posición en rango de 52 semanas —
                high_52 = close.max()
                low_52 = close.min()
                rango_pct = (current - low_52) / (high_52 - low_52) if (high_52 - low_52) > 0 else 0.5

                # — Soporte y resistencia (aprox. últimos 20 días) —
                soporte_20d = round(float(close.tail(20).min()), 2)
                resistencia_20d = round(float(close.tail(20).max()), 2)

                # — Datos para gráfico (últimos 90 días) —
                chart_data = hist.tail(90)
                tecnico = {
                    "sma_20": round(float(sma20_val), 2),
                    "sma_50": round(float(sma50_val), 2),
                    "sma_200": round(float(sma200_val), 2),
                    "rsi": round(float(rsi_val), 1),
                    "adx": round(float(adx_val), 1),
                    "tendencia": tendencia,
                    "vol_avg_20d": int(avg_vol_20) if pd.notna(avg_vol_20) else 0,
                    "vol_reciente": int(recent_vol) if pd.notna(recent_vol) else 0,
                    "vol_ratio": vol_ratio,
                    "rango_52w_pct": round(rango_pct * 100, 1),
                    "soporte_20d": soporte_20d,
                    "resistencia_20d": resistencia_20d,
                    "chart_dates": [d.strftime('%Y-%m-%d') for d in chart_data.index],
                    "chart_close": [round(float(v), 2) for v in chart_data['Close'].tolist()],
                    "chart_volume": [int(v) for v in chart_data['Volume'].tolist()],
                    "chart_sma20": [round(float(v), 2) if pd.notna(v) else None for v in sma_20.tail(90).tolist()],
                    "chart_sma50": [round(float(v), 2) if pd.notna(v) else None for v in sma_50.tail(90).tolist()],
                }
                logger.info(f"{symbol}: Técnico OK — Tendencia={tendencia}, RSI={rsi_val:.1f}, ADX={adx_val:.1f}")
        except Exception as e:
            logger.warning(f"{symbol}: Error en análisis técnico: {e}")
            tecnico = {}

        # === SCORE DE PROYECCIÓN (0-100) ===
        score = 0
        razones = []

        # 1. Crecimiento de ingresos (0-25 pts)
        rg = revenue_growth if revenue_growth else 0
        if rg > 0.30:
            score += 25; razones.append(f"Ingresos creciendo {rg*100:.0f}% (excelente)")
        elif rg > 0.15:
            score += 18; razones.append(f"Ingresos creciendo {rg*100:.0f}% (fuerte)")
        elif rg > 0.05:
            score += 10; razones.append(f"Ingresos creciendo {rg*100:.0f}% (moderado)")
        elif rg > 0:
            score += 5; razones.append(f"Ingresos creciendo {rg*100:.0f}% (bajo)")

        # 2. Márgenes operativos (0-20 pts)
        om = operating_margins if operating_margins else 0
        if om > 0.30:
            score += 20; razones.append(f"Margen operativo {om*100:.0f}% (excepcional)")
        elif om > 0.20:
            score += 15; razones.append(f"Margen operativo {om*100:.0f}% (alto)")
        elif om > 0.10:
            score += 10; razones.append(f"Margen operativo {om*100:.0f}% (saludable)")
        elif om > 0:
            score += 5; razones.append(f"Margen operativo {om*100:.0f}%")

        # 3. Upside de analistas (0-20 pts)
        if upside_pct > 30:
            score += 20; razones.append(f"Analistas ven +{upside_pct:.0f}% de subida")
        elif upside_pct > 15:
            score += 15; razones.append(f"Analistas ven +{upside_pct:.0f}% de subida")
        elif upside_pct > 5:
            score += 10; razones.append(f"Analistas ven +{upside_pct:.0f}% de subida")
        elif upside_pct > 0:
            score += 5; razones.append(f"Analistas ven +{upside_pct:.0f}% modesto")

        # 4. Flujo de caja libre positivo (0-15 pts)
        if free_cashflow and free_cashflow > 0:
            fcf_margin = free_cashflow / revenue if revenue else 0
            if fcf_margin > 0.20:
                score += 15; razones.append("Flujo de caja libre excepcional")
            elif fcf_margin > 0.10:
                score += 10; razones.append("Flujo de caja libre fuerte")
            else:
                score += 5; razones.append("Flujo de caja libre positivo")

        # 5. Recomendación de analistas (0-10 pts)
        rec_lower = recommendation.lower() if recommendation else ""
        if rec_lower in ("strong_buy", "strongbuy"):
            score += 10; razones.append("Consenso: COMPRA FUERTE")
        elif rec_lower == "buy":
            score += 8; razones.append("Consenso: COMPRA")
        elif rec_lower in ("overweight",):
            score += 6; razones.append("Consenso: SOBREPONDERAR")
        elif rec_lower == "hold":
            score += 3; razones.append("Consenso: MANTENER")

        # 6. PEG ratio favorable (0-10 pts)
        if peg_ratio and 0 < peg_ratio < 1:
            score += 10; razones.append(f"PEG {peg_ratio:.2f} (infravalorada vs crecimiento)")
        elif peg_ratio and 0 < peg_ratio < 1.5:
            score += 6; razones.append(f"PEG {peg_ratio:.2f} (valuación razonable)")
        elif peg_ratio and 0 < peg_ratio < 2.5:
            score += 3; razones.append(f"PEG {peg_ratio:.2f}")

        # Clasificación
        if score >= SCORE_THRESHOLD_ALTA:
            clasificacion = "ALTA"
        elif score >= SCORE_THRESHOLD_MEDIA:
            clasificacion = "MEDIA"
        else:
            clasificacion = "BAJA"

        # === SCORE TÉCNICO (0-100) ===
        score_tecnico = 0
        señales_tecnicas = []
        if tecnico:
            t = tecnico
            # 1. Tendencia (0-30 pts)
            if t["tendencia"] == "ALCISTA":
                score_tecnico += 30; señales_tecnicas.append("Tendencia alcista (precio > SMA20 > SMA50)")
            elif t["tendencia"] == "LATERAL":
                score_tecnico += 15; señales_tecnicas.append("Tendencia lateral / consolidación")
            else:
                score_tecnico += 5; señales_tecnicas.append("Tendencia bajista — precaución")

            # 2. RSI (0-20 pts)
            rsi_v = t["rsi"]
            if 40 <= rsi_v <= 60:
                score_tecnico += 20; señales_tecnicas.append(f"RSI {rsi_v:.0f} — zona neutral, buen punto de entrada")
            elif 30 <= rsi_v < 40:
                score_tecnico += 18; señales_tecnicas.append(f"RSI {rsi_v:.0f} — cerca de sobreventa, posible rebote")
            elif rsi_v < 30:
                score_tecnico += 15; señales_tecnicas.append(f"RSI {rsi_v:.0f} — SOBREVENTA, posible oportunidad")
            elif 60 < rsi_v <= 70:
                score_tecnico += 12; señales_tecnicas.append(f"RSI {rsi_v:.0f} — fuerza alcista moderada")
            elif rsi_v > 70:
                score_tecnico += 5; señales_tecnicas.append(f"RSI {rsi_v:.0f} — SOBRECOMPRA, riesgo de corrección")

            # 3. ADX — fuerza de tendencia (0-20 pts)
            adx_v = t["adx"]
            if adx_v > 25:
                score_tecnico += 20; señales_tecnicas.append(f"ADX {adx_v:.0f} — tendencia fuerte")
            elif adx_v > 20:
                score_tecnico += 15; señales_tecnicas.append(f"ADX {adx_v:.0f} — tendencia moderada")
            elif adx_v > 15:
                score_tecnico += 10; señales_tecnicas.append(f"ADX {adx_v:.0f} — tendencia débil")
            else:
                score_tecnico += 5; señales_tecnicas.append(f"ADX {adx_v:.0f} — sin tendencia clara")

            # 4. Volumen (0-15 pts)
            vr = t["vol_ratio"]
            if vr > 1.5:
                score_tecnico += 15; señales_tecnicas.append(f"Volumen +{(vr-1)*100:.0f}% vs promedio — interés alto")
            elif vr > 1.1:
                score_tecnico += 10; señales_tecnicas.append(f"Volumen +{(vr-1)*100:.0f}% vs promedio — actividad normal-alta")
            elif vr > 0.8:
                score_tecnico += 7; señales_tecnicas.append("Volumen en rango normal")
            else:
                score_tecnico += 3; señales_tecnicas.append(f"Volumen bajo ({vr:.0%} del promedio)")

            # 5. Posición en rango 52 semanas (0-15 pts)
            rp = t["rango_52w_pct"]
            if 20 <= rp <= 60:
                score_tecnico += 15; señales_tecnicas.append(f"Precio al {rp:.0f}% del rango 52s — zona de valor")
            elif 60 < rp <= 80:
                score_tecnico += 10; señales_tecnicas.append(f"Precio al {rp:.0f}% del rango 52s — fuerza")
            elif rp > 80:
                score_tecnico += 5; señales_tecnicas.append(f"Precio al {rp:.0f}% del rango 52s — cerca de máximos")
            elif rp < 20:
                score_tecnico += 8; señales_tecnicas.append(f"Precio al {rp:.0f}% del rango 52s — cerca de mínimos")

        # === VEREDICTO COMBINADO ===
        score_combinado = round((score * 0.55) + (score_tecnico * 0.45)) if tecnico else score
        if score_combinado >= 70:
            veredicto = "OPORTUNIDAD DE COMPRA"
        elif score_combinado >= 50:
            veredicto = "CONSIDERAR — Vigilar entrada"
        elif score_combinado >= 35:
            veredicto = "MANTENER / ESPERAR"
        else:
            veredicto = "PRECAUCIÓN — No recomendado"

        return {
            "symbol": symbol,
            "nombre": nombre,
            "precio": precio,
            "market_cap": market_cap,
            "sector": sector_yf,
            "industria": industria,
            "revenue_growth": rg,
            "earnings_growth": earnings_growth or 0,
            "gross_margins": gross_margins or 0,
            "operating_margins": om,
            "profit_margins": profit_margins or 0,
            "forward_pe": forward_pe or 0,
            "trailing_pe": trailing_pe or 0,
            "peg_ratio": peg_ratio or 0,
            "price_to_sales": price_to_sales or 0,
            "revenue": revenue or 0,
            "target_mean": target_mean or 0,
            "target_high": target_high or 0,
            "target_low": target_low or 0,
            "upside_pct": round(upside_pct, 2),
            "recommendation": recommendation,
            "num_analysts": num_analysts or 0,
            "free_cashflow": free_cashflow or 0,
            "operating_cashflow": operating_cashflow or 0,
            "beta": beta or 0,
            "fifty_two_high": fifty_two_high or 0,
            "fifty_two_low": fifty_two_low or 0,
            "score": score,
            "score_tecnico": score_tecnico,
            "score_combinado": score_combinado,
            "clasificacion": clasificacion,
            "razones": razones,
            "señales_tecnicas": señales_tecnicas,
            "veredicto": veredicto if tecnico else clasificacion,
            "tecnico": tecnico,
        }, None

    except Exception as e:
        return None, f"Error analizando {symbol}: {str(e)}"
