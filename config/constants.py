"""
Constantes globales del Monitor de Opciones.
Centraliza todos los valores numéricos y umbrales del proyecto.
"""

# --- Tasas y parámetros financieros ---
RISK_FREE_RATE = 0.045             # Tasa libre de riesgo (~Treasury yield 4.5%)
DEFAULT_TARGET_DELTA = 0.16        # Delta objetivo (≈ 1σ)
DAYS_PER_YEAR = 365.0              # Días por año para calcular T

# --- Umbrales por defecto del escáner ---
DEFAULT_MIN_VOLUME = 30_000
DEFAULT_MIN_OI = 10_000
DEFAULT_MIN_PRIMA = 5_000_000
DEFAULT_QUICK_FILTER = 1_000

# --- Detección de clusters ---
CLUSTER_TOLERANCE_PCT = 0.50       # ±50% del umbral de prima
CLUSTER_TOLERANCE_MULTIPLIER = 3   # Multiplicador rango superior
CLUSTER_MAX_STRIKE_DIFF = 10       # Diferencia máxima entre strikes
CLUSTER_MIN_CONTRACTS = 2          # Mínimo de contratos para formar cluster
CLUSTER_MIN_ALERTS = 2             # Mínimo de alertas para intentar detección

# --- Noticias RSS ---
RSS_MAX_ENTRIES = 15               # Máximo de entradas por fuente RSS
RSS_TITLE_DEDUP_LEN = 60           # Longitud de clave para deduplicar títulos
RSS_MAX_DESC_LEN = 300             # Longitud máxima de descripción

# --- Tiempos ---
SCAN_SLEEP_RANGE = (2.0, 4.5)      # Pausa entre llamadas API en escaneo
ANALYSIS_SLEEP_RANGE = (1.0, 2.5)  # Pausa entre análisis de proyecciones
AUTO_REFRESH_INTERVAL = 300        # Intervalo auto-refresco en segundos (5 min)

# --- Score de proyección ---
SCORE_THRESHOLD_ALTA = 65
SCORE_THRESHOLD_MEDIA = 40

# --- UI ---
SIDEBAR_WIDTH_PX = 310
