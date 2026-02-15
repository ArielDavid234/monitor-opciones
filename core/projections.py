"""
Análisis de proyecciones fundamentales de empresas a 10 años.
"""
import logging
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
            "target_mean": target_mean or 0,
            "target_high": target_high or 0,
            "target_low": target_low or 0,
            "upside_pct": round(upside_pct, 2),
            "recommendation": recommendation,
            "num_analysts": num_analysts or 0,
            "free_cashflow": free_cashflow or 0,
            "beta": beta or 0,
            "fifty_two_high": fifty_two_high or 0,
            "fifty_two_low": fifty_two_low or 0,
            "score": score,
            "clasificacion": clasificacion,
            "razones": razones,
        }, None

    except Exception as e:
        return None, f"Error analizando {symbol}: {str(e)}"
