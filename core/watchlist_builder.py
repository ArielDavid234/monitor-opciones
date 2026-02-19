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


# ============================================================================
# ============================================================================
#   SECCIÓN EMERGENTES — Lista dinámica de empresas disruptivas
# ============================================================================
# ============================================================================

# Universo candidato emergentes — ~45 disruptores y empresas de hipercrecimiento
# Se excluyen mega-caps (>$250B market cap) que ya compiten en consolidadas.
_CANDIDATOS_EMERGENTES = [
    # Actuales 18
    "IONQ", "RKLB", "AFRM", "SOFI", "UPST", "MNDY", "S", "PATH",
    "CELH", "DKNG", "AXON", "DUOL", "ASTS", "HIMS", "HOOD", "GRAB",
    "JOBY", "SMCI",
    # Candidatos adicionales (~27 más)
    "QBTS",   # D-Wave Quantum
    "RGTI",   # Rigetti Computing
    "LUNR",   # Intuitive Machines (lunar spacecraft)
    "ACHR",   # Archer Aviation (eVTOL)
    "RIVN",   # Rivian (EV trucks)
    "NU",     # Nubank (neobank Latam)
    "BILL",   # Bill.com (SMB payments)
    "TOST",   # Toast (restaurantes tech)
    "GTLB",   # GitLab (DevOps)
    "DDOG",   # Datadog (cloud monitoring)
    "DOCS",   # Doximity (telemedicina doctors)
    "RXRX",   # Recursion Pharma (AI drug discovery)
    "SOUN",   # SoundHound (voice AI)
    "AI",     # C3.ai (enterprise AI)
    "SE",     # Sea Limited (super-app SEA)
    "MQ",     # Marqeta (card issuing)
    "FOUR",   # Shift4 Payments
    "CHPT",   # ChargePoint (EV charging)
    "RBLX",   # Roblox (metaverso)
    "U",      # Unity Technologies (game engine)
    "APP",    # AppLovin (mobile advertising AI)
    "ALAB",   # Astera Labs (connectivity semiconductors AI)
    "ARM",    # ARM Holdings (chip architecture)
    "MSTR",   # MicroStrategy (Bitcoin treasury)
    "IREN",   # Iris Energy (Bitcoin mining / AI)
    "CAVA",   # Cava Group (fast-casual restaurants)
    "BIRK",   # Birkenstock (consumer brand)
]

# Metadatos curados para los candidatos adicionales emergentes.
# Los actuales 18 ya tienen metadatos en WATCHLIST_EMERGENTES (fallback).
_METADATA_EMERGENTES: dict[str, dict] = {
    # 18 actuales — se copian de WATCHLIST_EMERGENTES para tener todo en un lugar
    "IONQ": {"nombre": "IonQ Inc.", "descripcion": "Pionera en computación cuántica con tecnología de iones atrapados. Construye computadoras cuánticas accesibles via cloud.", "sector": "Computación Cuántica", "por_que_grande": "La computación cuántica resolverá problemas que las computadoras clásicas no pueden (fármacos, materiales, criptografía). IonQ tiene la tecnología más precisa del mercado y ya tiene contratos con gobiernos y Fortune 500. Si la cuántica escala, será la NVIDIA de esta nueva era."},
    "RKLB": {"nombre": "Rocket Lab USA", "descripcion": "Fabricante de cohetes Electron y Neutron para lanzamiento de satélites pequeños y medianos. También fabrica componentes espaciales.", "sector": "Aeroespacial / Lanzamientos", "por_que_grande": "La economía espacial crecerá a $1T+ en 2035. Rocket Lab es el segundo lanzador más frecuente del mundo después de SpaceX. Su cohete Neutron competirá directamente con Falcon 9. Vertical integrada: cohetes + satélites + componentes."},
    "AFRM": {"nombre": "Affirm Holdings", "descripcion": "Plataforma de 'compra ahora, paga después' (BNPL). Integrada en Amazon, Shopify y miles de comercios para pagos a plazos sin tarjeta.", "sector": "Fintech / BNPL", "por_que_grande": "La Generación Z rechaza las tarjetas de crédito tradicionales y prefiere pagos transparentes a plazos. Affirm crece con el e-commerce y ya procesa miles de millones."},
    "SOFI": {"nombre": "SoFi Technologies", "descripcion": "Plataforma financiera todo-en-uno: préstamos, inversiones, banking, crypto. Tiene licencia bancaria completa.", "sector": "Fintech / Banca Digital", "por_que_grande": "El banco digital del futuro. Licencia bancaria le permite captar depósitos baratos y prestar. Millennials y Gen Z prefieren apps a sucursales."},
    "UPST": {"nombre": "Upstart Holdings", "descripcion": "Plataforma de préstamos impulsada por IA que evalúa riesgo crediticio mejor que los métodos tradicionales (FICO).", "sector": "IA / Fintech / Préstamos", "por_que_grande": "Su IA aprueba más préstamos con menos riesgo que el score FICO tradicional. Si los bancos adoptan masivamente su plataforma, Upstart puede intermediar billones en créditos."},
    "MNDY": {"nombre": "monday.com Ltd.", "descripcion": "Plataforma de gestión de trabajo (Work OS) que permite a equipos construir flujos de trabajo personalizados sin código.", "sector": "SaaS / Productividad", "por_que_grande": "El trabajo remoto/híbrido es permanente. monday.com reemplaza herramientas fragmentadas con una plataforma unificada. Crece 30%+ anual, alta retención de clientes."},
    "S":    {"nombre": "SentinelOne Inc.", "descripcion": "Plataforma de ciberseguridad autónoma impulsada por IA. Protege endpoints, cloud e identidades con respuesta automatizada en tiempo real.", "sector": "Ciberseguridad / IA", "por_que_grande": "Los ciberataques crecen exponencialmente con la IA. SentinelOne ofrece protección completamente automatizada. Es el producto de ciberdefensa más moderno del mercado."},
    "PATH": {"nombre": "UiPath Inc.", "descripcion": "Líder mundial en automatización robótica de procesos (RPA). Robots de software que automatizan tareas repetitivas en empresas.", "sector": "Automatización / RPA / IA", "por_que_grande": "Cada empresa quiere reducir costos automatizando tareas manuales. UiPath combina RPA con IA. El mercado de automatización empresarial alcanzará $30B+ y UiPath es el líder claro."},
    "CELH": {"nombre": "Celsius Holdings", "descripcion": "Marca de bebidas energéticas saludables en rápido crecimiento. Compite con Monster y Red Bull con productos fitness-oriented.", "sector": "Bebidas / Consumo", "por_que_grande": "La tendencia de salud y fitness es irreversible. Celsius crece +40% anual quitando cuota de mercado a Monster/Red Bull. Distribución con PepsiCo le da acceso global."},
    "DKNG": {"nombre": "DraftKings Inc.", "descripcion": "Plataforma de apuestas deportivas online y fantasía deportiva. Líder en estados donde se legaliza el betting.", "sector": "Apuestas Deportivas / Gaming", "por_que_grande": "Las apuestas deportivas se legalizan estado por estado en EE.UU. (mercado potencial $40B+). DraftKings tiene la marca más reconocida y la mejor tecnología del sector."},
    "AXON": {"nombre": "Axon Enterprise", "descripcion": "Fabricante de Tasers y cámaras corporales para policía. Plataforma de evidencia digital en la nube (Axon Cloud).", "sector": "Seguridad Pública / SaaS", "por_que_grande": "La transparencia policial es una mega-tendencia global. Axon domina cámaras corporales y tiene un monopolio virtual en Tasers. Su software cloud genera ingresos recurrentes."},
    "DUOL": {"nombre": "Duolingo Inc.", "descripcion": "App #1 mundial para aprender idiomas con gamificación e IA. Expandiéndose a matemáticas y música.", "sector": "EdTech / IA", "por_que_grande": "Domina el aprendizaje de idiomas globalmente con 100M+ usuarios activos mensuales. Se expande a nuevas materias creando una super-app de educación. El mercado EdTech alcanzará $400B+."},
    "ASTS": {"nombre": "AST SpaceMobile", "descripcion": "Construye la primera red celular espacial: satélites que conectan directamente con celulares normales sin modificación.", "sector": "Telecomunicaciones Espaciales", "por_que_grande": "5 mil millones de personas no tienen cobertura móvil confiable. Si logra enviar señal 4G/5G desde satélites a celulares normales, conectará al mundo entero. Acuerdos con AT&T, Vodafone y más."},
    "HIMS": {"nombre": "Hims & Hers Health", "descripcion": "Plataforma de telemedicina y salud personalizada. Vende tratamientos para caída de cabello, salud sexual, piel y salud mental online.", "sector": "Telemedicina / Salud Digital", "por_que_grande": "La salud se digitaliza. Millennials y Gen Z prefieren consultas online. Hims crece +40% anual, tiene millones de suscriptores y se expande a GLP-1 (pérdida de peso)."},
    "HOOD": {"nombre": "Robinhood Markets", "descripcion": "Plataforma de trading sin comisiones para acciones, opciones, crypto. Democratizó la inversión para jóvenes.", "sector": "Fintech / Trading", "por_que_grande": "La mayor transferencia de riqueza de la historia ($84T de boomers a millennials/Gen Z) se acerca. Robinhood añade retirement accounts, crypto, tarjetas. Puede ser el Charles Schwab de la nueva generación."},
    "GRAB": {"nombre": "Grab Holdings", "descripcion": "Super-app del sudeste asiático: transporte, entregas de comida, pagos digitales y servicios financieros en una sola app.", "sector": "Super-App / Fintech Asia", "por_que_grande": "700 millones de personas en el sudeste asiático, clase media en explosión. Grab es la app dominante para moverse, comer y pagar. Si se convierte en el WeChat del sudeste asiático, será gigante."},
    "JOBY": {"nombre": "Joby Aviation", "descripcion": "Desarrolla taxis aéreos eléctricos (eVTOL) para transporte urbano. Aviones eléctricos de despegue y aterrizaje vertical.", "sector": "Movilidad Aérea / eVTOL", "por_que_grande": "El tráfico urbano empeora globalmente. Joby tiene la certificación FAA más avanzada, respaldo de Toyota y acuerdo con Delta Airlines. Mercado potencial de $1T+ si la regulación permite operaciones comerciales."},
    "SMCI": {"nombre": "Super Micro Computer", "descripcion": "Fabricante de servidores e infraestructura de cómputo para data centers de IA. Socio clave de NVIDIA para desplegar GPUs.", "sector": "Infraestructura IA / Servidores", "por_que_grande": "Cada GPU de NVIDIA necesita un servidor. SMCI fabrica los servidores optimizados de IA más rápido que nadie. Mientras la demanda de IA crezca, SMCI crece con ella."},
    # Candidatos adicionales
    "QBTS": {"nombre": "D-Wave Quantum", "descripcion": "Pionera en computación cuántica de recocido (annealing). Ofrece acceso cloud a sus sistemas cuánticos comerciales.", "sector": "Computación Cuántica", "por_que_grande": "Única empresa cuántica con sistemas comerciales en producción desde hace más de una década. Su enfoque de annealing resuelve problemas de optimización reales hoy, sin esperar la cuántica universal."},
    "RGTI": {"nombre": "Rigetti Computing", "descripcion": "Fabrica chips cuánticos superconductores y ofrece acceso a computadores cuánticos via cloud (QCS).", "sector": "Computación Cuántica", "por_que_grande": "Uno de los pocos fabricantes integrados verticalmente en cuántica: diseña el chip, lo fabrica y opera el sistema. La carrera cuántica tiene múltiples ganadores potenciales y Rigetti es jugador clave."},
    "LUNR": {"nombre": "Intuitive Machines", "descripcion": "Empresa aeroespacial que opera misiones lunares comerciales para la NASA bajo el programa CLPS.", "sector": "Aeroespacial / Lunar", "por_que_grande": "Primera empresa privada en aterrizar con éxito en la Luna (2024). La economía lunar está en sus inicios: minería de helio-3, bases lunares, turismo. Intuitive Machines es el proveedor de referencia de la NASA para la Luna."},
    "ACHR": {"nombre": "Archer Aviation", "descripcion": "Desarrolla aeronaves eléctrico de despegue vertical (eVTOL) para taxis aéreos urbanos. Modelo Midnight con 60 millas de autonomía.", "sector": "Movilidad Aérea / eVTOL", "por_que_grande": "United Airlines y Stellantis son inversores estratégicos. Certificación FAA en progreso para 2025. Los taxis aéreos en ciudades como Nueva York o LA pueden revolucionar la movilidad urbana."},
    "RIVN": {"nombre": "Rivian Automotive", "descripcion": "Fabricante de camionetas y SUVs eléctricos. Proveedor exclusivo de furgonetas de entrega para Amazon.", "sector": "Vehículos Eléctricos", "por_que_grande": "El segmento de pickups y SUVs eléctricos es el más lucrativo de EE.UU. Amazon garantiza demanda con 100,000 furgonetas contratadas. Con escala, Rivian puede ser el Ford/GM eléctrico del futuro."},
    "NU":   {"nombre": "Nu Holdings (Nubank)", "descripcion": "Neobank líder en América Latina con +100M clientes en Brasil, México y Colombia. Tarjetas, préstamos, inversiones y seguros 100% digitales.", "sector": "Fintech / Banca Digital LATAM", "por_que_grande": "América Latina tiene 650M personas con acceso bancario limitado. Nubank ya es rentable, crece a +25% anual y tiene la mayor base de clientes fintech del mundo. Es el banco del futuro de toda una región."},
    "BILL": {"nombre": "Bill.com Holdings", "descripcion": "Plataforma de automatización financiera para PYMEs: cuentas por pagar/cobrar, gestión de facturas y pagos B2B.", "sector": "Fintech / SaaS / PYMEs", "por_que_grande": "30 millones de PYMEs en EE.UU. siguen gestionando sus finanzas con Excel o QuickBooks. Bill.com automatiza ese proceso ahorrando horas semanales. El mercado de pagos B2B en EE.UU. mueve $25T anuales."},
    "TOST": {"nombre": "Toast Inc.", "descripcion": "Plataforma tecnológica todo-en-uno para restaurantes: POS, pagos, delivery, gestión de empleados y analytics.", "sector": "Fintech / Restaurant Tech", "por_que_grande": "Los restaurantes son uno de los sectores más inefficientes en tecnología. Toast tiene ya 120,000+ restaurantes y crece 30%+. Si captura la mitad de los restaurantes de EE.UU. y expande internacionalmente, es una empresa enorme."},
    "GTLB": {"nombre": "GitLab Inc.", "descripcion": "Plataforma DevSecOps completa: código, CI/CD, seguridad y operaciones en un solo lugar. Alternativa a GitHub.", "sector": "DevOps / SaaS", "por_que_grande": "Cada empresa de software necesita DevOps. GitLab integra todo el ciclo de desarrollo en una plataforma unificada con seguridad incorporada. Con el auge del software, demanda de DevOps no para de crecer."},
    "DDOG": {"nombre": "Datadog Inc.", "descripcion": "Plataforma de observabilidad y monitoreo para infraestructura cloud, aplicaciones y seguridad en tiempo real.", "sector": "Cloud / Observabilidad / SaaS", "por_que_grande": "Toda empresa cloud necesita monitorear su infraestructura. Datadog consolida docenas de herramientas en una plataforma. Crece 25%+ anual con clientes Fortune 500. El mercado de observabilidad superará $50B+."},
    "DOCS": {"nombre": "Doximity Inc.", "descripcion": "Red social y plataforma de telemedicina exclusiva para médicos. 80%+ de los médicos de EE.UU. usan Doximity.", "sector": "Telemedicina / SaaS Médico", "por_que_grande": "Tiene el mayor red de profesionales médicos de EE.UU. Monetiza con farmacéuticas (marketing) y telemedicina. Márgenes altísimos (40%+ EBITDA). A medida que la medicina se digitaliza, Doximity es la infraestructura indispensable."},
    "RXRX": {"nombre": "Recursion Pharmaceuticals", "descripcion": "Usa IA y biología computacional para descubrir fármacos. Mapea el efecto de millones de compuestos en células.", "sector": "IA / Drug Discovery / Biotech", "por_que_grande": "El descubrimiento de fármacos tarda 12 años y cuesta $2.6B. La IA puede reducir ese tiempo y costo drásticamente. Recursion tiene el dataset biológico más grande del mundo y alianzas con Roche y Sanofi."},
    "SOUN": {"nombre": "SoundHound AI", "descripcion": "Plataforma de IA de voz para automóviles, restaurantes y dispositivos. Reconocimiento de voz en tiempo real sin nube.", "sector": "IA de Voz / Edge AI", "por_que_grande": "La voz es la interfaz del futuro para coches, electrodomésticos y comercio. SoundHound está integrado en marcas como Hyundai, Kia, Mercedes y cientos de restaurantes. El mercado de IA conversacional superará $100B."},
    "AI":   {"nombre": "C3.ai Inc.", "descripcion": "Proveedor de aplicaciones de IA empresarial preconfiguradas para sectores como energía, manufactura y finanzas.", "sector": "EA (Enterprise AI) / SaaS", "por_que_grande": "Las empresas necesitan IA pero no tienen equipos para construirla desde cero. C3.ai ofrece aplicaciones listas para usar que se integran con datos existentes. El mercado de IA empresarial superará $500B en 2030."},
    "SE":   {"nombre": "Sea Limited", "descripcion": "Conglomerado digital del sudeste asiático: Garena (gaming), Shopee (e-commerce) y SeaMoney (fintech).", "sector": "Super-App / E-Commerce / Gaming SEA", "por_que_grande": "700 millones de personas en una región con clase media explosiva. Garena genera caja, Shopee es el Amazon del SEA y SeaMoney bancariza a millones sin cuenta. Es la plataforma digital dominante de la región de más rápido crecimiento del mundo."},
    "MQ":   {"nombre": "Marqeta Inc.", "descripcion": "Plataforma de emisión de tarjetas de crédito/débito virtual. Permite a empresas crear sus propias tarjetas programables.", "sector": "Fintech / Card Issuing", "por_que_grande": "Cada empresa quiere tener su propia tarjeta (Block, Uber, DoorDash usan Marqeta). La infraestructura de tarjetas es invisible pero esencial. A medida que más empresas lancen productos financieros embedded, Marqeta procesa todos esos pagos."},
    "FOUR": {"nombre": "Shift4 Payments", "descripcion": "Procesador de pagos integrado para restaurantes, hoteles, estadios y entretenimiento. Adquiriendo mercados internacionales.", "sector": "Fintech / Pagos", "por_que_grande": "Procesa pagos para los sectores de mayor volumen (hospitalidad, entretenimiento). Expansión agresiva en Europa y LATAM. A diferencia de competidores, está verticalmente integrado con software + hardware + pagos."},
    "CHPT": {"nombre": "ChargePoint Holdings", "descripcion": "Red de carga de vehículos eléctricos más grande de Norteamérica y Europa. Software de gestión de flota EV.", "sector": "Infraestructura EV / Energía", "por_que_grande": "Para cada EV en carretera, se necesitan 3 puntos de carga. ChargePoint tiene 300,000+ puertos de carga. A medida que la adopción de EVs crece, ChargePoint crece con ellos. Es la gasolinera del futuro."},
    "RBLX": {"nombre": "Roblox Corporation", "descripcion": "Plataforma de juegos y creación de experiencias en 3D con 80M+ usuarios activos diarios, principalmente menores de 17.", "sector": "Metaverso / Gaming / UGC", "por_que_grande": "Roblox es el metaverso real que ya existe: millones crean y monetizan experiencias. La Generación Alpha crece jugando Roblox. Cuando esa generación tenga poder adquisitivo, Roblox puede convertirse en la plataforma de entretenimiento dominante."},
    "U":    {"nombre": "Unity Technologies", "descripcion": "Motor de creación de juegos y experiencias 3D en tiempo real. Usado en el 70% de los juegos móviles del mundo.", "sector": "Game Engine / Metaverso / IA", "por_que_grande": "Unity es la herramienta para construir el metaverso y la realidad aumentada. El 70% de los juegos móviles usan Unity. Con la expansión de AR/VR y IA generativa para 3D, Unity es la infraestructura creativa del mundo virtual."},
    "APP":  {"nombre": "AppLovin Corporation", "descripcion": "Plataforma de marketing y monetización de apps móviles impulsada por IA. El algoritmo AXON optimiza anuncios con alta precisión.", "sector": "AdTech / IA / Mobile", "por_que_grande": "La publicidad móvil es el mayor canal de marketing digital. El algoritmo de IA de AppLovin (AXON) bate a Meta y Google en ROAS para apps. Creciendo a 30%+ anual y entrando en e-commerce. Puede ser la plataforma de ads del mundo móvil."},
    "ALAB": {"nombre": "Astera Labs", "descripcion": "Semiconductores de conectividad para centros de datos de IA. Chips PCIe, CXL y Ethernet que conectan GPUs y CPUs.", "sector": "Semiconductores / IA Infrastructure", "por_que_grande": "Construir un data center de IA no es solo poner GPUs: necesitas conectividad ultra-rápida. Astera Labs proporciona los chips de interconexión que hacen funcionar los clústeres de IA de hiperescaladores como Amazon, Google y Microsoft."},
    "ARM":  {"nombre": "ARM Holdings", "descripcion": "Diseñadora de arquitecturas de chips (ISA) usada en el 99% de los smartphones del mundo y creciendo en servidores e IA.", "sector": "Semiconductores / Arquitectura de Chips", "por_que_grande": "La arquitectura ARM está en 250 mil millones de chips vendidos. Con la transición a IA edge (chips eficientes), Apple Silicon (M-series), AWS Graviton y coches autónomos, ARM es la base de toda la computación moderna y futura."},
    "MSTR": {"nombre": "MicroStrategy / Strategy", "descripcion": "Empresa de software convertida en el mayor tenedor corporativo de Bitcoin (~470,000 BTC). Modelo de 'Bitcoin treasury company'.", "sector": "Bitcoin / Criptomonedas / Software", "por_que_grande": "Con la adopción institucional de Bitcoin como 'digital gold', MSTR es el mayor vehículo de exposición a BTC en mercados tradicionales. Si Bitcoin alcanza $500K-$1M, el valor de su tesorería se multiplica. Es una apuesta apalancada en Bitcoin."},
    "IREN": {"nombre": "Iris Energy", "descripcion": "Empresa de minería de Bitcoin con energía 100% renovable y expansión hacia infraestructura de IA (GPU cloud).", "sector": "Bitcoin Mining / IA Cloud", "por_que_grande": "Minería de Bitcoin sostenible con expansión estratégica hacia GPU-as-a-Service para IA. Cuando los precios del Bitcoin suben o la demanda de GPUs para IA se dispara, IREN se beneficia de ambos. Dos catalizadores de crecimiento en uno."},
    "CAVA": {"nombre": "Cava Group", "descripcion": "Cadena de restaurantes fast-casual mediterráneos de rápido crecimiento en EE.UU. Conocida como 'el Chipotle mediterráneo'.", "sector": "Restaurantes / Consumo", "por_que_grande": "Chipotle tardó 20 años en llegar a 3,000 restaurantes y multiplicó su acción por 100x. Cava tiene solo 350+ locales y crece 17%+ en nuevas aperturas anuales. La comida mediterránea es la tendencia saludable que reemplaza la comida mexicana."},
    "BIRK": {"nombre": "Birkenstock Holding", "descripcion": "Fabricante de sandalias premium de más de 250 años de historia. Marca de lujo accesible con fuerte presencia global.", "sector": "Consumo Aspiracional / Moda", "por_que_grande": "De sandalias de hippies a icono de moda global. La colaboración con Hermès, el efecto Barbie (2023) y la expansión en Asia convierten a Birkenstock en una marca aspiracional. Modelo de negocio de alto margen y fidelización extrema de clientes."},
}


def construir_watchlist_emergentes(
    n: int = 18,
    fallback: Optional[dict] = None,
) -> dict:
    """
    Construye dinámicamente la watchlist de empresas emergentes/disruptivas.

    Metodología:
      1. Universo candidato: ~45 disruptores y empresas de hipercrecimiento
      2. Obtener market cap y momentum de 52 semanas via yfinance (fast_info)
      3. Filtrar: excluir mega-caps (>$250B) que ya deberían estar en consolidadas
                 y micro-caps (<$150M) con poco liquidity
      4. Calcular score de disrupción = momentum_52w * 0.6 + (market_cap relativo) * 0.4
      5. Ordenar por score → tomar top N
      6. Si yfinance falla → usar fallback estático (WATCHLIST_EMERGENTES)

    Args:
        n: Número de empresas a devolver (default 18).
        fallback: Watchlist estática a devolver si yfinance falla completamente.

    Returns:
        dict {ticker: {nombre, descripcion, sector, por_que_grande, ...}}
    """
    scores: dict[str, float] = {}
    market_caps: dict[str, float] = {}

    for sym in _CANDIDATOS_EMERGENTES:
        try:
            fi = yf.Ticker(sym).fast_info
            mc = getattr(fi, "market_cap", None) or 0.0
            yc = getattr(fi, "year_change", None)  # fracción, ej: 0.45 = +45%

            # Filtrar mega-caps (ya pertenecen a consolidadas) y micro-caps
            if mc > 250e9 or mc < 150e6:
                continue
            # Si no hay momentum disponible, usar 0 como neutro
            momentum = float(yc) if yc is not None else 0.0

            market_caps[sym] = mc
            scores[sym] = momentum  # ranking principal: momentum 52w
        except Exception as exc:
            logger.debug("No se pudo obtener datos de %s: %s", sym, exc)

    if not scores:
        logger.warning("No se obtuvieron scores emergentes — usando watchlist estática.")
        return fallback or {}

    # Ordenar por momentum descendente → tomar top N
    top_n = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:n]

    logger.info(
        "Top %d emergentes por momentum 52w: %s",
        n,
        ", ".join(
            f"{sym}({pct:+.0%})" for sym, pct in top_n
        ),
    )

    watchlist: dict = {}
    for sym, momentum in top_n:
        if sym in _METADATA_EMERGENTES:
            entry = dict(_METADATA_EMERGENTES[sym])
        else:
            entry = _obtener_metadata_yfinance(sym)

        entry["market_cap_live"] = market_caps.get(sym, 0)
        entry["momentum_52w"] = momentum
        watchlist[sym] = entry

    # Asegurar que todos tienen nombre
    for sym in watchlist:
        if "nombre" not in watchlist[sym]:
            watchlist[sym]["nombre"] = sym

    return watchlist
