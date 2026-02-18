"""
Watchlists de empresas monitoreadas.
Empresas consolidadas y emergentes con proyección a 10 años.
"""

# ============================================================================
#    WATCHLIST — EMPRESAS CON PROYECCIÓN A 10 AÑOS
# ============================================================================
WATCHLIST_EMPRESAS = {
    "NVDA": {
        "nombre": "NVIDIA Corporation",
        "sector": "Semiconductores / IA",
    },
    "MSFT": {
        "nombre": "Microsoft Corporation",
        "descripcion": "Gigante del software con Azure (cloud #2 mundial), Office 365, LinkedIn, Xbox y fuerte inversión en IA a través de OpenAI.",
        "sector": "Software / Cloud / IA",
    },
    "GOOGL": {
        "nombre": "Alphabet Inc. (Google)",
        "descripcion": "Dueña de Google Search, YouTube, Android y Google Cloud. Líder en publicidad digital y pionera en IA con DeepMind y Gemini.",
        "sector": "Publicidad Digital / Cloud / IA",
    },
    "AMZN": {
        "nombre": "Amazon.com Inc.",
        "descripcion": "Líder en e-commerce y cloud computing (AWS #1 mundial). Expandiéndose en logística, salud, streaming y publicidad.",
        "sector": "E-Commerce / Cloud",
    },
    "META": {
        "nombre": "Meta Platforms Inc.",
        "descripcion": "Dueña de Facebook, Instagram, WhatsApp y Threads. Fuerte inversión en metaverso (Reality Labs) e IA generativa (LLaMA).",
        "sector": "Redes Sociales / IA / Metaverso",
    },
    "AAPL": {
        "nombre": "Apple Inc.",
        "descripcion": "Fabricante del iPhone, Mac, iPad y Apple Watch. Ecosistema cerrado con servicios crecientes (App Store, iCloud, Apple TV+).",
        "sector": "Hardware / Servicios",
    },
    "TSLA": {
        "nombre": "Tesla Inc.",
        "descripcion": "Líder en vehículos eléctricos, almacenamiento de energía (Megapack), paneles solares y desarrollo de conducción autónoma (FSD).",
        "sector": "Vehículos Eléctricos / Energía",
    },
    "AMD": {
        "nombre": "Advanced Micro Devices",
        "descripcion": "Competidor directo de NVIDIA en GPUs para IA (MI300X) y de Intel en CPUs. Crecimiento acelerado en data centers.",
        "sector": "Semiconductores",
    },
    "AVGO": {
        "nombre": "Broadcom Inc.",
        "descripcion": "Fabricante de semiconductores para redes, telecomunicaciones e infraestructura. Adquirió VMware para expandirse en software empresarial.",
        "sector": "Semiconductores / Software",
    },
    "LLY": {
        "nombre": "Eli Lilly and Company",
        "descripcion": "Farmacéutica líder con fármacos revolucionarios para diabetes/obesidad (Mounjaro, Zepbound) y pipeline en Alzheimer.",
        "sector": "Farmácutica / Biotecnología",
    },
    "V": {
        "nombre": "Visa Inc.",
        "descripcion": "Red de pagos digitales más grande del mundo. Se beneficia de la transición global de efectivo a pagos electrónicos.",
        "sector": "Pagos Digitales / Fintech",
    },
    "UNH": {
        "nombre": "UnitedHealth Group",
        "descripcion": "Mayor aseguradora de salud de EE.UU. con Optum (servicios de datos y salud). Crecimiento estable por envejecimiento poblacional.",
        "sector": "Salud / Seguros",
    },
    "PLTR": {
        "nombre": "Palantir Technologies",
        "descripcion": "Plataforma de análisis de datos e IA para gobiernos y empresas. Fuerte crecimiento con contratos militares y AIP (plataforma de IA).",
        "sector": "Análisis de Datos / IA",
    },
    "COIN": {
        "nombre": "Coinbase Global",
        "descripcion": "Principal exchange de criptomonedas en EE.UU. Se beneficia de la adopción institucional de crypto y regulación favorable.",
        "sector": "Criptomonedas / Fintech",
    },
    "NET": {
        "nombre": "Cloudflare Inc.",
        "descripcion": "Plataforma de seguridad y rendimiento web. Protege sitios contra DDoS, ofrece CDN, DNS y soluciones zero-trust para empresas.",
        "sector": "Ciberseguridad / Cloud",
    },
    "CRWD": {
        "nombre": "CrowdStrike Holdings",
        "descripcion": "Líder en ciberseguridad endpoint basada en IA/cloud. Plataforma Falcon protege empresas contra amenazas avanzadas.",
        "sector": "Ciberseguridad",
    },
    "SNOW": {
        "nombre": "Snowflake Inc.",
        "descripcion": "Plataforma de datos en la nube que permite almacenar, analizar y compartir datos masivos entre organizaciones.",
        "sector": "Cloud / Big Data",
    },
    "MELI": {
        "nombre": "MercadoLibre Inc.",
        "descripcion": "Líder en e-commerce y fintech en América Latina. Mercado Pago procesa pagos digitales en una región con gran potencial de crecimiento.",
        "sector": "E-Commerce / Fintech LATAM",
    },
}

# ============================================================================
#    WATCHLIST — EMPRESAS EMERGENTES CON PROYECCIÓN A 10 AÑOS
# ============================================================================
WATCHLIST_EMERGENTES = {
    "IONQ": {
        "nombre": "IonQ Inc.",
        "descripcion": "Pionera en computación cuántica con tecnología de iones atrapados. Construye computadoras cuánticas accesibles via cloud.",
        "sector": "Computación Cuántica",
        "por_que_grande": "La computación cuántica resolverá problemas que las computadoras clásicas no pueden (fármacos, materiales, criptografía). IonQ tiene la tecnología más precisa del mercado y ya tiene contratos con gobiernos y Fortune 500. Si la cuántica escala, será la NVIDIA de esta nueva era.",
    },
    "RKLB": {
        "nombre": "Rocket Lab USA",
        "descripcion": "Fabricante de cohetes Electron y Neutron para lanzamiento de satélites pequeños y medianos. También fabrica componentes espaciales.",
        "sector": "Aeroespacial / Lanzamientos",
        "por_que_grande": "La economía espacial crecerá a $1T+ en 2035. Rocket Lab es el segundo lanzador más frecuente del mundo después de SpaceX. Su cohete Neutron competirá directamente con Falcon 9. Vertical integrada: cohetes + satélites + componentes.",
    },
    "AFRM": {
        "nombre": "Affirm Holdings",
        "descripcion": "Plataforma de 'compra ahora, paga después' (BNPL). Integrada en Amazon, Shopify y miles de comercios para pagos a plazos sin tarjeta.",
        "sector": "Fintech / BNPL",
        "por_que_grande": "La Generación Z rechaza las tarjetas de crédito tradicionales y prefiere pagos transparentes a plazos. Affirm crece con el e-commerce y ya procesa miles de millones. Si captura una fracción del mercado de crédito al consumo ($4T), será gigante.",
    },
    "SOFI": {
        "nombre": "SoFi Technologies",
        "descripcion": "Plataforma financiera todo-en-uno: préstamos, inversiones, banking, crypto. Tiene licencia bancaria completa.",
        "sector": "Fintech / Banca Digital",
        "por_que_grande": "El banco digital del futuro. Licencia bancaria le permite captar depósitos baratos y prestar. Millennials y Gen Z prefieren apps a sucursales. Si reemplaza aunque sea el 5% de la banca tradicional de EE.UU., es una empresa de $100B+.",
    },
    "UPST": {
        "nombre": "Upstart Holdings",
        "descripcion": "Plataforma de préstamos impulsada por IA que evalúa riesgo crediticio mejor que los métodos tradicionales (FICO).",
        "sector": "IA / Fintech / Préstamos",
        "por_que_grande": "Su IA aprueba más préstamos con menos riesgo que el score FICO tradicional. Si los bancos adoptan masivamente su plataforma, Upstart puede intermediar billones en créditos. Disrumpir la evaluación de riesgo crediticio es un mercado enorme.",
    },
    "MNDY": {
        "nombre": "monday.com Ltd.",
        "descripcion": "Plataforma de gestión de trabajo (Work OS) que permite a equipos construir flujos de trabajo personalizados sin código.",
        "sector": "SaaS / Productividad",
        "por_que_grande": "El trabajo remoto/híbrido es permanente. monday.com reemplaza herramientas fragmentadas con una plataforma unificada. Crece 30%+ anual, alta retención de clientes, y se expande a CRM, dev y marketing. Puede convertirse en el sistema operativo del trabajo.",
    },
    "S": {
        "nombre": "SentinelOne Inc.",
        "descripcion": "Plataforma de ciberseguridad autónoma impulsada por IA. Protege endpoints, cloud e identidades con respuesta automatizada en tiempo real.",
        "sector": "Ciberseguridad / IA",
        "por_que_grande": "Los ciberataques crecen exponencialmente con la IA. SentinelOne ofrece protección completamente automatizada (sin intervención humana). A medida que toda empresa necesite ciberdefensa avanzada, S tiene el producto más moderno del mercado.",
    },
    "PATH": {
        "nombre": "UiPath Inc.",
        "descripcion": "Líder mundial en automatización robótica de procesos (RPA). Robots de software que automatizan tareas repetitivas en empresas.",
        "sector": "Automatización / RPA / IA",
        "por_que_grande": "Cada empresa quiere reducir costos automatizando tareas manuales. UiPath combina RPA con IA para automatizar procesos complejos. El mercado de automatización empresarial alcanzará $30B+ y UiPath es el líder claro.",
    },
    "CELH": {
        "nombre": "Celsius Holdings",
        "descripcion": "Marca de bebidas energéticas saludables en rápido crecimiento. Compite con Monster y Red Bull con productos fitness-oriented.",
        "sector": "Bebidas / Consumo",
        "por_que_grande": "La tendencia de salud y fitness es irreversible. Celsius crece +40% anual quitando cuota de mercado a Monster/Red Bull. Distribución con PepsiCo le da acceso global. Si captura 10-15% del mercado de energy drinks ($80B), será colosal.",
    },
    "DKNG": {
        "nombre": "DraftKings Inc.",
        "descripcion": "Plataforma de apuestas deportivas online y fantasía deportiva. Líder en estados donde se legaliza el betting.",
        "sector": "Apuestas Deportivas / Gaming",
        "por_que_grande": "Las apuestas deportivas se legalizan estado por estado en EE.UU. (mercado potencial $40B+). Cada legalización es crecimiento instantáneo. DraftKings tiene la marca más reconocida y la mejor tecnología del sector.",
    },
    "AXON": {
        "nombre": "Axon Enterprise",
        "descripcion": "Fabricante de Tasers y cámaras corporales para policía. Plataforma de evidencia digital en la nube (Axon Cloud).",
        "sector": "Seguridad Pública / SaaS",
        "por_que_grande": "La transparencia policial es una mega-tendencia global. Axon domina cámaras corporales y tiene un monopolio virtual en Tasers. Su software cloud para gestión de evidencia genera ingresos recurrentes. Se expande a seguridad privada e internacional.",
    },
    "DUOL": {
        "nombre": "Duolingo Inc.",
        "descripcion": "App #1 mundial para aprender idiomas con gamificación e IA. Expandiéndose a matemáticas y música.",
        "sector": "EdTech / IA",
        "por_que_grande": "Domina el aprendizaje de idiomas globalmente con 100M+ usuarios activos mensuales. La IA personaliza cada lección. Se expande a nuevas materias (matemáticas, música) creando una super-app de educación. El mercado EdTech alcanzará $400B+.",
    },
    "ASTS": {
        "nombre": "AST SpaceMobile",
        "descripcion": "Construye la primera red celular espacial: satélites que conectan directamente con celulares normales sin modificación.",
        "sector": "Telecomunicaciones Espaciales",
        "por_que_grande": "5 mil millones de personas no tienen cobertura móvil confiable. Si logra enviar señal 4G/5G desde satélites a celulares normales, conectará al mundo entero. Acuerdos con AT&T, Vodafone y más. Es extremadamente ambicioso pero el premio es enorme.",
    },
    "HIMS": {
        "nombre": "Hims & Hers Health",
        "descripcion": "Plataforma de telemedicina y salud personalizada. Vende tratamientos para caída de cabello, salud sexual, piel y salud mental online.",
        "sector": "Telemedicina / Salud Digital",
        "por_que_grande": "La salud se digitaliza. Millennials y Gen Z prefieren consultas online. Hims crece +40% anual, tiene millones de suscriptores y márgenes crecientes. Se expande a GLP-1 (pérdida de peso) y más condiciones. Puede ser el Amazon de la salud personal.",
    },
    "HOOD": {
        "nombre": "Robinhood Markets",
        "descripcion": "Plataforma de trading sin comisiones para acciones, opciones, crypto. Democratizó la inversión para jóvenes.",
        "sector": "Fintech / Trading",
        "por_que_grande": "La mayor transferencia de riqueza de la historia ($84T de boomers a millennials/Gen Z) se acerca. Estos inversores usan apps, no brokers tradicionales. Robinhood añade retirement accounts, crypto, tarjetas. Puede ser el Charles Schwab de la nueva generación.",
    },
    "GRAB": {
        "nombre": "Grab Holdings",
        "descripcion": "Super-app del sudeste asiático: transporte, entregas de comida, pagos digitales y servicios financieros en una sola app.",
        "sector": "Super-App / Fintech Asia",
        "por_que_grande": "700 millones de personas en el sudeste asiático, clase media en explosión. Grab es la app dominante para moverse, comer y pagar. La digitalización financiera de la región apenas comienza. Si se convierte en el WeChat del sudeste asiático, será gigante.",
    },
    "JOBY": {
        "nombre": "Joby Aviation",
        "descripcion": "Desarrolla taxis aéreos eléctricos (eVTOL) para transporte urbano. Aviones eléctricos de despegue y aterrizaje vertical.",
        "sector": "Movilidad Aérea / eVTOL",
        "por_que_grande": "El tráfico urbano empeora globalmente. Los taxis aéreos eléctricos podrían ser la solución para ciudades grandes. Joby tiene la certificación FAA más avanzada, respaldo de Toyota y acuerdo con Delta Airlines. Mercado potencial de $1T+ si la regulación permite operaciones comerciales.",
    },
    "SMCI": {
        "nombre": "Super Micro Computer",
        "descripcion": "Fabricante de servidores e infraestructura de cómputo para data centers de IA. Socio clave de NVIDIA para desplegar GPUs.",
        "sector": "Infraestructura IA / Servidores",
        "por_que_grande": "Cada GPU de NVIDIA necesita un servidor. SMCI fabrica los servidores optimizados de IA más rápido que nadie (liquid cooling, racks optimizados). Mientras la demanda de IA crezca, SMCI crece con ella. Es el 'pico y pala' de la fiebre del oro de la IA.",
    },
}
