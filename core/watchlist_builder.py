# -*- coding: utf-8 -*-
"""
Watchlist Builder — Lista dinámica de empresas consolidadas.

Construye automáticamente la watchlist de las N empresas más grandes
del mercado americano ordenadas por capitalización de mercado, usando
yfinance como fuente de datos.

Estrategia:
  1. Universo candidato: ~60 empresas del S&P 500 de conocida relevancia
  2. Consultar market cap en vivo via yfinance
  3. Ordenar por market cap descendente → tomar las top N
  4. Combinar con metadatos curados (descripción, sector) si están disponibles
  5. Si yfinance falla → devolver el fallback estático de WATCHLIST_EMPRESAS

Los metadatos (descripcion, sector, sector_label) se mantienen curados
para garantizar calidad, pero el *ranking* es 100% dinámico.
"""

import logging
from typing import Optional

import yfinance as yf

logger = logging.getLogger(__name__)

# ============================================================================
# Universo candidato — ~60 empresas top del S&P 500
# Se actualiza consultando market cap en vivo; el orden aquí NO importa.
# ============================================================================
_CANDIDATOS = [
    "NVDA", "MSFT", "AAPL", "AMZN", "GOOGL", "META", "TSLA", "AVGO",
    "BRK-B", "JPM", "LLY", "V", "UNH", "XOM", "MA", "COST", "HD",
    "NFLX", "PG", "JNJ", "BAC", "WMT", "ABBV", "CRM", "ORCL", "AMD",
    "MRK", "CVX", "KO", "PLTR", "PEP", "TMO", "ABT", "CSCO", "GE",
    "MCD", "IBM", "TXN", "NOW", "ISRG", "COIN", "NET", "CRWD", "SNOW",
    "ADBE", "QCOM", "INTC", "CAT", "GS", "MS", "SPGI", "BLK", "MELI",
    "AMT", "RTX", "T", "VZ", "DUK", "NEE",
]

# ============================================================================
# Metadatos curados — descripción y sector para cada empresa
# Si una empresa entra al top-N pero no está aquí, se generan
# datos básicos desde yfinance (longBusinessSummary, sector).
# ============================================================================
_METADATA: dict[str, dict] = {
    "NVDA":  {"descripcion": "Líder indiscutible en GPUs para IA, centros de datos, gaming y computación científica. Su arquitectura CUDA es el estándar de facto en deep learning.", "sector": "Semiconductores / IA"},
    "MSFT":  {"descripcion": "Gigante del software con Azure (cloud #2 mundial), Office 365, LinkedIn, Xbox y fuerte inversión en IA a través de OpenAI.", "sector": "Software / Cloud / IA"},
    "AAPL":  {"descripcion": "Fabricante del iPhone, Mac, iPad y Apple Watch. Ecosistema cerrado con servicios crecientes (App Store, iCloud, Apple TV+).", "sector": "Hardware / Servicios"},
    "AMZN":  {"descripcion": "Líder en e-commerce y cloud computing (AWS #1 mundial). Expandiéndose en logística, salud, streaming y publicidad.", "sector": "E-Commerce / Cloud"},
    "GOOGL": {"descripcion": "Dueña de Google Search, YouTube, Android y Google Cloud. Líder en publicidad digital y pionera en IA con DeepMind y Gemini.", "sector": "Publicidad Digital / Cloud / IA"},
    "META":  {"descripcion": "Dueña de Facebook, Instagram, WhatsApp y Threads. Fuerte inversión en metaverso (Reality Labs) e IA generativa (LLaMA).", "sector": "Redes Sociales / IA / Metaverso"},
    "TSLA":  {"descripcion": "Líder en vehículos eléctricos, almacenamiento de energía (Megapack), paneles solares y desarrollo de conducción autónoma (FSD).", "sector": "Vehículos Eléctricos / Energía"},
    "AMD":   {"descripcion": "Competidor directo de NVIDIA en GPUs para IA (MI300X) y de Intel en CPUs. Crecimiento acelerado en data centers.", "sector": "Semiconductores"},
    "AVGO":  {"descripcion": "Fabricante de semiconductores para redes, telecomunicaciones e infraestructura. Adquirió VMware para expandirse en software empresarial.", "sector": "Semiconductores / Software"},
    "LLY":   {"descripcion": "Farmacéutica líder con fármacos revolucionarios para diabetes/obesidad (Mounjaro, Zepbound) y pipeline en Alzheimer.", "sector": "Farmacéutica / Biotecnología"},
    "V":     {"descripcion": "Red de pagos digitales más grande del mundo. Se beneficia de la transición global de efectivo a pagos electrónicos.", "sector": "Pagos Digitales / Fintech"},
    "UNH":   {"descripcion": "Mayor aseguradora de salud de EE.UU. con Optum (servicios de datos y salud). Crecimiento estable por envejecimiento poblacional.", "sector": "Salud / Seguros"},
    "PLTR":  {"descripcion": "Plataforma de análisis de datos e IA para gobiernos y empresas. Fuerte crecimiento con contratos militares y AIP (plataforma de IA).", "sector": "Análisis de Datos / IA"},
    "COIN":  {"descripcion": "Principal exchange de criptomonedas en EE.UU. Se beneficia de la adopción institucional de crypto y regulación favorable.", "sector": "Criptomonedas / Fintech"},
    "NET":   {"descripcion": "Plataforma de seguridad y rendimiento web. Protege sitios contra DDoS, ofrece CDN, DNS y soluciones zero-trust para empresas.", "sector": "Ciberseguridad / Cloud"},
    "CRWD":  {"descripcion": "Líder en ciberseguridad endpoint basada en IA/cloud. Plataforma Falcon protege empresas contra amenazas avanzadas.", "sector": "Ciberseguridad"},
    "SNOW":  {"descripcion": "Plataforma de datos en la nube que permite almacenar, analizar y compartir datos masivos entre organizaciones.", "sector": "Cloud / Big Data"},
    "MELI":  {"descripcion": "Líder en e-commerce y fintech en América Latina. Mercado Pago procesa pagos digitales en una región con gran potencial de crecimiento.", "sector": "E-Commerce / Fintech LATAM"},
    "BRK-B": {"descripcion": "Conglomerado de Warren Buffett con posiciones en seguros (GEICO), ferrocarriles (BNSF), energía y cientos de empresas.", "sector": "Conglomerado / Holding"},
    "JPM":   {"descripcion": "Mayor banco de EE.UU. por activos. Líder en banca de inversión, mercados globales y banca minorista.", "sector": "Banca / Finanzas"},
    "XOM":   {"descripcion": "Gigante energético integrado con operaciones en exploración, refinación y petroquímica. Mayor productor de petróleo de EE.UU.", "sector": "Energía / Petróleo"},
    "MA":    {"descripcion": "Segunda red de pagos más grande del mundo. Compite directamente con Visa en transacciones globales.", "sector": "Pagos Digitales / Fintech"},
    "COST":  {"descripcion": "Cadena de almacenes de membresía con altísima fidelización. Modelo de negocio defensivo con crecimiento constante.", "sector": "Retail / Membresía"},
    "HD":    {"descripcion": "Mayor cadena de mejoras del hogar del mundo. Se beneficia de tendencias de renovación de viviendas.", "sector": "Retail / Construcción"},
    "NFLX":  {"descripcion": "Plataforma de streaming líder con 270M+ suscriptores. Expande hacia gaming y publicidad para acelerar ingresos.", "sector": "Streaming / Entretenimiento"},
    "JNJ":   {"descripcion": "Gigante de salud con división de farmacéuticos innovadores, dispositivos médicos y consumer health.", "sector": "Farmacéutica / Salud"},
    "CRM":   {"descripcion": "Líder mundial en CRM empresarial con Einstein AI. Suite completa de ventas, marketing y atención al cliente.", "sector": "SaaS / CRM"},
    "ORCL":  {"descripcion": "Gigante de bases de datos empresariales en transición exitosa al cloud (Oracle Cloud). Fuerte en ERP y IA generativa.", "sector": "Software / Cloud"},
    "MRK":   {"descripcion": "Farmacéutica con Keytruda (el medicamento oncológico más vendido del mundo) y pipeline sólido en VIH y vacunas.", "sector": "Farmacéutica"},
    "ABBV":  {"descripcion": "Farmacéutica con Humira y diversificación a Skyrizi, Rinvoq. Alto dividendo y crecimiento estable.", "sector": "Farmacéutica / Biotecnología"},
    "NOW":   {"descripcion": "Plataforma de automatización de flujos de trabajo empresariales (ITSM, HRSD, SecOps). Crecimiento 20%+ anual sostenido.", "sector": "SaaS / Automatización"},
    "ISRG":  {"descripcion": "Fabricante del robot quirúrgico Da Vinci. Domina la cirugía robótica con modelo de ingresos recurrentes (instrumentos).", "sector": "Médico / Robótica"},
    "ADBE":  {"descripcion": "Suite de creatividad (Photoshop, Illustrator, Premiere) y marketing digital. Transición a SaaS completada.", "sector": "Software / Creatividad"},
    "QCOM":  {"descripcion": "Líder en chips para smartphones (Snapdragon) y conectividad 5G. Expande a autos, PCs e IoT.", "sector": "Semiconductores / 5G"},
    "TXN":   {"descripcion": "Fabricante de semiconductores analógicos y embebidos. Ingresos recurrentes y altísimos márgenes.", "sector": "Semiconductores"},
    "GS":    {"descripcion": "Banco de inversión de primer nivel con leadership en M&A, trading institucional y gestión de activos.", "sector": "Banca de Inversión"},
    "SPGI":  {"descripcion": "Propietario de S&P ratings, S&P 500 index, Platts (energía) y Market Intelligence. Modelo de ingresos escalable.", "sector": "Finanzas / Data"},
    "BLK":   {"descripcion": "Mayor gestor de activos del mundo con $10T+ bajo gestión. Aladdin es el sistema de riesgo que usan los grandes fondos.", "sector": "Gestión de Activos"},
    "IBM":   {"descripcion": "Empresa tecnológica centenaria en transición al hybrid cloud con Red Hat y servicios de IA generativa (watsonx).", "sector": "Cloud / IA Empresarial"},
    "GE":    {"descripcion": "Conglomerado industrial reconvertido en GE Aerospace tras escisiones de GE HealthCare y GE Vernova.", "sector": "Aeroespacial / Industrial"},
    "CAT":   {"descripcion": "Líder mundial en maquinaria de construcción y minería. Se beneficia de inversión en infraestructura global.", "sector": "Maquinaria Industrial"},
}


# ============================================================================
# Función principal
# ============================================================================

def construir_watchlist_consolidadas(
    n: int = 18,
    fallback: Optional[dict] = None,
) -> dict:
    """
    Construye la watchlist de las N empresas con mayor capitalización
    del universo candidato, consultando market cap en tiempo real.

    Parámetros
    ----------
    n        : número de empresas a incluir (default 18)
    fallback : dict estático a devolver si yfinance falla completamente

    Retorna
    -------
    dict en el mismo formato que WATCHLIST_EMPRESAS:
        {ticker: {nombre, descripcion, sector}, ...}

    ordenado por market cap descendente.
    """
    logger.info("Construyendo watchlist dinámica (universo=%d, top=%d)...", len(_CANDIDATOS), n)

    market_caps = {}

    try:
        # Descarga en batch para eficiencia (una sola llamada)
        tickers_str = " ".join(_CANDIDATOS)
        data = yf.download(
            tickers_str,
            period="1d",
            progress=False,
            auto_adjust=True,
            group_by="ticker",
        )

        # Consultar market cap individualmente (no viene en download)
        for sym in _CANDIDATOS:
            try:
                t = yf.Ticker(sym)
                info = t.fast_info  # mucho más rápido que .info
                mc = getattr(info, "market_cap", None)
                if mc and mc > 0:
                    market_caps[sym] = mc
                else:
                    # Fallback: estimar desde precio × shares
                    mc2 = getattr(info, "shares", None)
                    price = getattr(info, "last_price", None)
                    if mc2 and price:
                        market_caps[sym] = mc2 * price
            except Exception as e:
                logger.debug("No se pudo obtener market cap de %s: %s", sym, e)
                continue

    except Exception as e:
        logger.warning("Error en descarga batch yfinance: %s", e)

    if not market_caps:
        logger.warning("No se obtuvo ningún market cap — usando watchlist estática.")
        return fallback or {}

    # Ordenar por market cap descendente y tomar top N
    top_n = sorted(market_caps.items(), key=lambda x: x[1], reverse=True)[:n]

    logger.info(
        "Top %d por market cap: %s",
        n,
        ", ".join(f"{sym}(${mc/1e12:.1f}T)" if mc >= 1e12 else f"{sym}(${mc/1e9:.0f}B)"
                  for sym, mc in top_n)
    )

    # Construir el dict de watchlist
    watchlist = {}
    for sym, mc in top_n:
        if sym in _METADATA:
            entry = dict(_METADATA[sym])
        else:
            # Empresa nueva en el top que no tiene metadatos curados
            # → intentar obtenerlos de yfinance
            entry = _obtener_metadata_yfinance(sym)

        entry["market_cap_live"] = mc  # guardar para referencia
        watchlist[sym] = entry

    # Rellenar nombre si falta
    for sym in watchlist:
        if "nombre" not in watchlist[sym]:
            watchlist[sym]["nombre"] = sym

    return watchlist


def _obtener_metadata_yfinance(sym: str) -> dict:
    """
    Obtiene nombre, sector y una descripción corta desde yfinance
    para empresas sin metadatos curados.
    """
    try:
        info = yf.Ticker(sym).info
        nombre = info.get("longName") or info.get("shortName") or sym
        sector = info.get("sector") or info.get("industry") or "N/D"
        desc = info.get("longBusinessSummary", "")
        # Recortar a 300 caracteres para no saturar la UI
        if desc and len(desc) > 300:
            desc = desc[:297] + "..."
        return {
            "nombre": nombre,
            "descripcion": desc or f"Empresa del sector {sector}.",
            "sector": sector,
        }
    except Exception:
        return {
            "nombre": sym,
            "descripcion": "",
            "sector": "N/D",
        }
