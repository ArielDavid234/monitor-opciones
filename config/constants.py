"""
Constantes globales del Monitor de Opciones.
Centraliza todos los valores numéricos y umbrales del proyecto.
"""

# --- App defaults ---
DEFAULT_TICKER = "SPY"             # Ticker por defecto al iniciar la app

# --- Tasas y parámetros financieros ---
RISK_FREE_RATE = 0.045             # Tasa libre de riesgo (~Treasury yield 4.5%)
DEFAULT_TARGET_DELTA = 0.16        # Delta objetivo (≈ 1σ)
DAYS_PER_YEAR = 365.0              # Días por año para calcular T

# --- Umbrales por defecto del escáner ---
DEFAULT_MIN_VOLUME = 30_000
DEFAULT_MIN_OI = 10_000
DEFAULT_MIN_PRIMA = 5_000_000

# --- Detección de clusters ---
CLUSTER_TOLERANCE_PCT = 0.50       # ±50% del umbral de prima
CLUSTER_TOLERANCE_MULTIPLIER = 3   # Multiplicador rango superior
CLUSTER_MAX_STRIKE_DIFF = 10       # Diferencia máxima entre strikes
CLUSTER_MIN_ALERTS = 2             # Mínimo de alertas para intentar detección

# --- Noticias RSS ---
RSS_MAX_ENTRIES = 15               # Máximo de entradas por fuente RSS
RSS_TITLE_DEDUP_LEN = 60           # Longitud de clave para deduplicar títulos
RSS_MAX_DESC_LEN = 300             # Longitud máxima de descripción

# --- Tiempos ---
SCAN_SLEEP_RANGE = (2.5, 5.0)      # Pausa entre llamadas API — aumentada para reducir rate-limiting
ANALYSIS_SLEEP_RANGE = (0.5, 1.5)  # Pausa entre análisis de proyecciones
AUTO_REFRESH_INTERVAL = 600        # Intervalo auto-refresco en segundos (10 min)
SCAN_COOLDOWN_SECONDS = 60         # Tiempo mínimo entre escaneos completos

# --- Límites de escaneo ---
MAX_EXPIRATION_DATES = 8           # Máximo de fechas a escanear — reducido a 8 para menos requests a Yahoo

# --- Score de proyección ---
SCORE_THRESHOLD_ALTA = 65
SCORE_THRESHOLD_MEDIA = 40

# --- Income Score (Venta de Prima) ---
INCOME_SCORE_IV_RANK_MIN = 40          # +20 si IV Rank > este valor
INCOME_SCORE_IV_PCTIL_MIN = 60         # ó IV Percentile > este valor
INCOME_SCORE_DELTA_MAX = 0.20          # +20 si |delta| ≤ este valor
INCOME_SCORE_VOL_MIN = 100             # +20 si volumen > este valor
INCOME_SCORE_OI_MIN = 200              # y open interest > este valor
INCOME_SCORE_DIST_PCT_MIN = 5.0        # +20 si distancia strike % > este valor
INCOME_SCORE_LABEL_ALTA = 80           # "Alta probabilidad" si score ≥ 80
INCOME_SCORE_LABEL_BUENA = 60          # "Buena" si score ≥ 60, "Evitar" si < 60

# --- Filtro estricto — Credit Spread Pipeline ---
CS_WHITELIST = ["SPY", "QQQ", "IWM", "NVDA", "AAPL", "TSLA", "AMD"]
CS_MIN_PRICE = 20                      # Precio mínimo del underlying ($)
CS_MIN_AVG_VOLUME = 1_000_000          # Vol. diario promedio últimos 20 días (acciones)
CS_MIN_CHAIN_OI = 500                  # OI promedio mínimo en strikes cercanos
CS_MIN_IV_RANK = 30                    # IV Rank < 30 → descartar ticker completo
CS_DTE_MIN = 25                        # Mínimo DTE estricto
CS_DTE_MAX = 45                        # Máximo DTE estricto
CS_DELTA_MIN = 0.10                    # |delta vendido| mínimo
CS_DELTA_MAX = 0.20                    # |delta vendido| máximo
CS_ALLOWED_WIDTHS = [2, 3, 5]          # Anchos de spread permitidos
CS_MIN_CREDIT_PCT = 0.15               # Crédito mínimo = 15% del ancho (OTM δ0.10-0.20)
CS_MIN_DIST_PCT = 3.0                  # Distancia mínima del strike (%)
CS_MIN_SOLD_OI = 500                   # OI mínimo del strike vendido
CS_MIN_SOLD_VOL = 100                  # Volumen mínimo del strike vendido
CS_MAX_BID_ASK_PCT = 0.10              # Bid-Ask Spread ≤ 10% del mid price

# --- Score de Oportunidad (Venta de Prima) ---
OPP_SCORE_IV_RANK_MIN = 40             # +20 si IV Rank > 40
OPP_SCORE_DELTA_MIN = 0.12             # +20 si |delta| en [0.12, 0.18]
OPP_SCORE_DELTA_MAX = 0.18
OPP_SCORE_CREDIT_WIDTH_PCT = 0.20      # +20 si crédito ≥ 20% del ancho
OPP_SCORE_DIST_PCT_MIN = 4.0           # +20 si distancia > 4%
OPP_SCORE_VOL_MIN = 100                # +20 si volumen > 100
OPP_SCORE_OI_MIN = 500                 # +20 si OI > 500
OPP_SCORE_BA_CREDIT_PCT = 0.10         # +20 si bid-ask ≤ 10% del crédito
OPP_SCORE_MIN_SHOW = 60                # No mostrar filas con score < 60

# --- Sistema de Alertas — 10 reglas obligatorias ---
ALERT_DEFAULT_ACCOUNT_SIZE = 10_000    # Tamaño de cuenta por defecto ($)
ALERT_MAX_RISK_PCT = 0.05              # Riesgo máximo por trade = 5% de la cuenta
ALERT_TREND_REQUIRED = True            # Regla 5: Neutral = descartar
