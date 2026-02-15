"""
Análisis de proyecciones fundamentales y técnicas de empresas a 10 años.
Combina análisis fundamental (valor intrínseco) y técnico (precio/volumen)
para identificar oportunidades de compra o venta.
"""
import logging
import pandas as pd
import yfinance as yf

from config.constants import SCORE_THRESHOLD_ALTA, SCORE_THRESHOLD_MEDIA
from core.scanner import crear_sesion_nueva

logger = logging.getLogger(__name__)


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
