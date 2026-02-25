# -*- coding: utf-8 -*-
"""
Clasificador de flujo institucional de opciones.

Categoriza cada trade/fila del scanner en una de las siguientes clases,
alineadas con plataformas profesionales (Unusual Whales, Cheddar Flow,
FlowAlgo, BlackBoxStocks, TrendSpider):

    - Bearish Speculation
    - Bullish Speculation
    - Hedge (Protective Put)
    - Premium Selling
    - Spread / Neutral
    - Unclassified

Funciona tanto fila-a-fila como vectorizado sobre DataFrames completos.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# ============================================================================
#                    UMBRALES CONFIGURABLES
# ============================================================================
# Prima mínima (USD) para considerar flujo institucional relevante
PREMIUM_SPEC_MIN = 50_000          # Bearish/Bullish Speculation
PREMIUM_HEDGE_MIN = 500_000        # Hedge (Protective Put)

# OI mínimo de incremento esperado para posiciones nuevas
OI_INCREASE_MIN = 50

# Delta (absoluto) range para especulación pura
DELTA_SPEC_LOW = 0.15
DELTA_SPEC_HIGH = 0.80

# Delta (absoluto) profundo para hedge
DELTA_HEDGE_DEEP = 0.70

# Distance% mínima para considerar ITM profundo (hedge detection)
ITM_DEEP_DISTANCE_PCT = 8.0


# ============================================================================
#                    CLASIFICACIÓN POR FILA
# ============================================================================
def classify_flow_type(row) -> str:
    """Clasifica una fila del DataFrame del scanner.

    Acepta dict o pd.Series. Usa las columnas estándar del scanner:
        Tipo (CALL/PUT), Lado (Ask/Bid/Mid/N/A), Delta, OI, OI_Chg,
        Prima_Volumen, Moneyness (ITM/ATM/OTM/N/A), Distance_Pct.

    Returns
    -------
    str  Una de: Bearish Speculation, Bullish Speculation,
         Hedge, Premium Selling, Spread / Neutral, Unclassified.
    """
    # ── Extraer valores con tolerancia a NaN / None ──────────────────────
    def _safe(key, default=None):
        v = row.get(key, default) if isinstance(row, dict) else row.get(key, default)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return default
        return v

    tipo = str(_safe("Tipo", _safe("Tipo_Opcion", ""))).upper()
    lado = str(_safe("Lado", "N/A")).strip()
    delta_raw = _safe("Delta")
    oi_chg = _safe("OI_Chg", 0)
    premium = float(_safe("Prima_Volumen", 0) or 0)
    moneyness = str(_safe("Moneyness", "N/A")).upper()
    distance_pct = float(_safe("Distance_Pct", 0) or 0)

    # Delta absoluto (puts son negativos, calls positivos)
    if delta_raw is not None:
        try:
            abs_delta = abs(float(delta_raw))
        except (ValueError, TypeError):
            abs_delta = None
    else:
        abs_delta = None

    # ── Validación: si faltan datos clave → Unclassified ────────────────
    if tipo not in ("CALL", "PUT"):
        return "Unclassified"
    if lado == "N/A" and abs_delta is None:
        return "Unclassified"

    is_ask = lado == "Ask"
    is_bid = lado == "Bid"
    is_mid = lado == "Mid"
    is_put = tipo == "PUT"
    is_call = tipo == "CALL"

    oi_positive = (oi_chg is not None and oi_chg > OI_INCREASE_MIN)
    is_atm_otm = moneyness in ("ATM", "OTM")
    is_itm = moneyness == "ITM"

    delta_in_spec = (
        abs_delta is not None and DELTA_SPEC_LOW <= abs_delta <= DELTA_SPEC_HIGH
    )
    delta_deep = abs_delta is not None and abs_delta >= DELTA_HEDGE_DEEP
    itm_deep = is_itm and distance_pct >= ITM_DEEP_DISTANCE_PCT

    # ── 1. Hedge (Protective Put) ───────────────────────────────────────
    #    PUT comprado (Ask), ITM profundo o delta muy alto, prima gigante.
    #    Se evalúa ANTES de Bearish Spec para no confundir hedges con bets.
    if is_put and is_ask and premium >= PREMIUM_HEDGE_MIN:
        if itm_deep or delta_deep:
            return "Hedge"

    # ── 2. Bearish Speculation ──────────────────────────────────────────
    if is_put and is_ask and is_atm_otm:
        if premium >= PREMIUM_SPEC_MIN:
            if oi_positive or delta_in_spec:
                return "Bearish Speculation"
        # Relajar si delta está en rango especulativo y prima es al menos razonable
        if delta_in_spec and premium > 0:
            return "Bearish Speculation"

    # ── 3. Bullish Speculation ──────────────────────────────────────────
    if is_call and is_ask and is_atm_otm:
        if premium >= PREMIUM_SPEC_MIN:
            if oi_positive or delta_in_spec:
                return "Bullish Speculation"
        if delta_in_spec and premium > 0:
            return "Bullish Speculation"

    # ── 4. Premium Selling ──────────────────────────────────────────────
    #    Ejecución en Bid → está vendiendo la opción (credit strategies).
    if is_bid and oi_positive:
        return "Premium Selling"
    if is_bid and is_atm_otm and premium > 0:
        return "Premium Selling"

    # ── 5. Spread / Neutral ─────────────────────────────────────────────
    #    Ejecución en Mid sugiere spread (no es buyer ni seller agresivo).
    if is_mid:
        return "Spread / Neutral"

    # ── 6. Default ──────────────────────────────────────────────────────
    return "Unclassified"


# ============================================================================
#                    CLASIFICACIÓN VECTORIZADA
# ============================================================================
def classify_flow_bulk(df: pd.DataFrame) -> pd.Series:
    """Clasifica TODAS las filas de un DataFrame de forma vectorizada.

    Sigue la misma lógica de prioridad que classify_flow_type pero
    usando operaciones numpy para ~10× rendimiento sobre DataFrames grandes.

    Returns
    -------
    pd.Series[str] — categorías del mismo largo que df.
    """
    if df.empty:
        return pd.Series(dtype=str)

    n = len(df)

    # ── Extraer arrays ──────────────────────────────────────────────────
    tipo = df.get("Tipo", df.get("Tipo_Opcion", pd.Series([""] * n))).str.upper().values
    lado = df.get("Lado", pd.Series(["N/A"] * n)).fillna("N/A").str.strip().values
    premium = pd.to_numeric(df.get("Prima_Volumen", 0), errors="coerce").fillna(0).values
    moneyness = df.get("Moneyness", pd.Series(["N/A"] * n)).fillna("N/A").str.upper().values
    distance_pct = pd.to_numeric(df.get("Distance_Pct", 0), errors="coerce").fillna(0).values

    delta_raw = pd.to_numeric(df.get("Delta", np.nan), errors="coerce").fillna(np.nan).values
    abs_delta = np.abs(delta_raw)

    oi_chg = pd.to_numeric(df.get("OI_Chg", 0), errors="coerce").fillna(0).values

    # ── Máscaras booleanas ──────────────────────────────────────────────
    is_put = tipo == "PUT"
    is_call = tipo == "CALL"
    is_ask = lado == "Ask"
    is_bid = lado == "Bid"
    is_mid = lado == "Mid"

    is_atm_otm = np.isin(moneyness, ["ATM", "OTM"])
    is_itm = moneyness == "ITM"
    oi_pos = oi_chg > OI_INCREASE_MIN
    delta_spec = ~np.isnan(abs_delta) & (abs_delta >= DELTA_SPEC_LOW) & (abs_delta <= DELTA_SPEC_HIGH)
    delta_deep = ~np.isnan(abs_delta) & (abs_delta >= DELTA_HEDGE_DEEP)
    itm_deep = is_itm & (distance_pct >= ITM_DEEP_DISTANCE_PCT)
    prem_spec = premium >= PREMIUM_SPEC_MIN
    prem_hedge = premium >= PREMIUM_HEDGE_MIN
    prem_any = premium > 0

    # ── Inicializar resultado ───────────────────────────────────────────
    result = np.full(n, "Unclassified", dtype=object)

    # Orden inverso de prioridad: los últimos sobreescriben a los primeros
    # 5. Spread / Neutral
    result = np.where(is_mid, "Spread / Neutral", result)

    # 4. Premium Selling
    m_ps1 = is_bid & oi_pos
    m_ps2 = is_bid & is_atm_otm & prem_any
    result = np.where(m_ps1 | m_ps2, "Premium Selling", result)

    # 3. Bullish Speculation
    m_bs_strong = is_call & is_ask & is_atm_otm & prem_spec & (oi_pos | delta_spec)
    m_bs_delta = is_call & is_ask & is_atm_otm & delta_spec & prem_any
    result = np.where(m_bs_strong | m_bs_delta, "Bullish Speculation", result)

    # 2. Bearish Speculation
    m_bear_strong = is_put & is_ask & is_atm_otm & prem_spec & (oi_pos | delta_spec)
    m_bear_delta = is_put & is_ask & is_atm_otm & delta_spec & prem_any
    result = np.where(m_bear_strong | m_bear_delta, "Bearish Speculation", result)

    # 1. Hedge (Protective Put) — highest priority
    m_hedge = is_put & is_ask & prem_hedge & (itm_deep | delta_deep)
    result = np.where(m_hedge, "Hedge", result)

    return pd.Series(result, index=df.index)


# ============================================================================
#                    BADGE / COLOR
# ============================================================================
# Colores para badges HTML en la UI (fondo, texto, borde)
FLOW_COLORS: dict[str, dict[str, str]] = {
    "Bearish Speculation": {
        "bg": "rgba(239,68,68,0.12)",
        "color": "#ef4444",
        "border": "rgba(239,68,68,0.25)",
        "variant": "bear",
    },
    "Bullish Speculation": {
        "bg": "rgba(0,255,136,0.12)",
        "color": "#00ff88",
        "border": "rgba(0,255,136,0.25)",
        "variant": "bull",
    },
    "Hedge": {
        "bg": "rgba(245,158,11,0.13)",
        "color": "#f59e0b",
        "border": "rgba(245,158,11,0.25)",
        "variant": "hedge",
    },
    "Premium Selling": {
        "bg": "rgba(59,130,246,0.13)",
        "color": "#60a5fa",
        "border": "rgba(59,130,246,0.25)",
        "variant": "sellprem",
    },
    "Spread / Neutral": {
        "bg": "rgba(148,163,184,0.12)",
        "color": "#94a3b8",
        "border": "rgba(148,163,184,0.18)",
        "variant": "spread",
    },
    "Unclassified": {
        "bg": "rgba(100,116,139,0.10)",
        "color": "#64748b",
        "border": "rgba(100,116,139,0.15)",
        "variant": "unclass",
    },
}


def flow_badge(flow_type: str) -> str:
    """Return HTML badge for a flow type, matching the ok-badge system."""
    info = FLOW_COLORS.get(flow_type, FLOW_COLORS["Unclassified"])
    return (
        f'<span class="ok-badge ok-badge-{info["variant"]}">'
        f'{flow_type}</span>'
    )


# ============================================================================
#         DETECCIÓN DE HEDGE INSTITUCIONAL (Smart Money Hedge Alert)
# ============================================================================
# Umbrales conservadores — solo se activa en casos contundentes.
HEDGE_ALERT_PREMIUM_L1 = 500_000       # Nivel 1 (warning) — prima mínima
HEDGE_ALERT_PREMIUM_L2 = 1_500_000     # Nivel 2 (critical) — prima muy alta
HEDGE_ALERT_DELTA_L1 = 0.70            # |delta| mínimo nivel 1
HEDGE_ALERT_DELTA_L2 = 0.80            # |delta| mínimo nivel 2
HEDGE_ALERT_OI_CHG_L1 = 30             # OI_Chg mínimo nivel 1
HEDGE_ALERT_OI_CHG_L2 = 100            # OI_Chg mínimo nivel 2
HEDGE_ALERT_MIN_DTE = 30               # DTE mínimo (excluir weeklies especulativos)


def _parse_dte(vencimiento) -> int | None:
    """Calcula DTE a partir de un string de fecha 'YYYY-MM-DD'."""
    from datetime import date
    if not vencimiento:
        return None
    try:
        exp = date.fromisoformat(str(vencimiento)[:10])
        return max((exp - date.today()).days, 0)
    except (ValueError, TypeError):
        return None


def detect_institutional_hedge(row) -> dict:
    """Detecta hedge institucional pesado en una fila del scanner.

    Evalúa si una operación de PUT representa protección institucional
    agresiva (compra de PUT ITM profundo con prima enorme), señal de
    miedo real al downside.

    Parameters
    ----------
    row : dict | pd.Series
        Fila con columnas del scanner: Tipo/Tipo_Opcion, Lado, Delta,
        OI_Chg, Prima_Volumen, Moneyness, Distance_Pct, Vencimiento.

    Returns
    -------
    dict  Con claves {alerta, nivel, explicacion, color} si califica,
          o dict vacío {} si no.
    """
    def _safe(key, default=None):
        v = row.get(key, default) if isinstance(row, dict) else row.get(key, default)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return default
        return v

    # ── Requisito obligatorio: PUT ──────────────────────────────────────
    tipo = str(_safe("Tipo", _safe("Tipo_Opcion", ""))).upper()
    if tipo != "PUT":
        return {}

    # ── Requisito: ejecución agresiva (Ask) ─────────────────────────────
    lado = str(_safe("Lado", "N/A")).strip()
    if lado != "Ask":
        return {}

    # ── Prima (filtro más discriminante) ────────────────────────────────
    premium = float(_safe("Prima_Volumen", 0) or 0)
    if premium < HEDGE_ALERT_PREMIUM_L1:
        return {}

    # ── Delta (profundidad ITM) ─────────────────────────────────────────
    delta_raw = _safe("Delta")
    abs_delta: float | None = None
    if delta_raw is not None:
        try:
            abs_delta = abs(float(delta_raw))
        except (ValueError, TypeError):
            abs_delta = None

    # Moneyness
    moneyness = str(_safe("Moneyness", "N/A")).upper()
    is_itm = moneyness == "ITM"

    # Si no es ITM y no tiene delta profundo → no es hedge
    if not is_itm and (abs_delta is None or abs_delta < HEDGE_ALERT_DELTA_L1):
        return {}

    # ── OI Change (posición nueva) ──────────────────────────────────────
    oi_chg = float(_safe("OI_Chg", 0) or 0)
    if oi_chg < HEDGE_ALERT_OI_CHG_L1:
        return {}

    # ── DTE (excluir weeklies) ──────────────────────────────────────────
    vencimiento = _safe("Vencimiento")
    dte = _parse_dte(vencimiento)
    if dte is not None and dte < HEDGE_ALERT_MIN_DTE:
        return {}

    # ── Clasificar nivel ────────────────────────────────────────────────
    score = 0
    reasons = []

    if premium >= HEDGE_ALERT_PREMIUM_L2:
        score += 2
        reasons.append(f"Prima ${premium:,.0f} ≥ ${HEDGE_ALERT_PREMIUM_L2:,.0f}")
    else:
        reasons.append(f"Prima ${premium:,.0f}")

    if abs_delta is not None and abs_delta >= HEDGE_ALERT_DELTA_L2:
        score += 1
        reasons.append(f"|Δ| {abs_delta:.2f} ≥ {HEDGE_ALERT_DELTA_L2}")
    elif abs_delta is not None:
        reasons.append(f"|Δ| {abs_delta:.2f}")

    if oi_chg >= HEDGE_ALERT_OI_CHG_L2:
        score += 1
        reasons.append(f"OI↑ +{oi_chg:,.0f}")
    else:
        reasons.append(f"OI↑ +{oi_chg:,.0f}")

    distance = float(_safe("Distance_Pct", 0) or 0)
    if distance >= ITM_DEEP_DISTANCE_PCT:
        score += 1
        reasons.append(f"ITM profundo ({distance:.1f}%)")

    if dte is not None and dte >= 90:
        reasons.append(f"DTE {dte}d (LEAP)")

    reason_str = " · ".join(reasons)

    if score >= 2:
        return {
            "alerta": "🔴 ALTA ALERTA: Hedge Institucional Pesado",
            "nivel": "critical",
            "explicacion": (
                f"PUT ITM comprado agresivamente en Ask con prima masiva → "
                f"instituciones cubriendo downside risk (miedo real). {reason_str}"
            ),
            "color": "#dc3545",
        }
    else:
        return {
            "alerta": "🟠 Protección Institucional Detectada",
            "nivel": "warning",
            "explicacion": (
                f"PUT ITM comprado en Ask con prima alta → cobertura "
                f"institucional contra caída. {reason_str}"
            ),
            "color": "#ffa726",
        }


def detect_hedge_bulk(df: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Versión vectorizada de detect_institutional_hedge.

    Returns
    -------
    tuple de 3 pd.Series (mismo índice que df):
        - Hedge_Alert  : str  (texto de alerta o "")
        - Hedge_Level  : str  ("critical" | "warning" | "")
        - Hedge_Detail : str  (explicación o "")
    """
    from datetime import date

    n = len(df)
    empty = pd.Series([""] * n, index=df.index)
    if df.empty:
        return empty.copy(), empty.copy(), empty.copy()

    tipo = df.get("Tipo", df.get("Tipo_Opcion", pd.Series([""] * n))).str.upper().values
    lado = df.get("Lado", pd.Series(["N/A"] * n)).fillna("N/A").str.strip().values
    premium = pd.to_numeric(df.get("Prima_Volumen", 0), errors="coerce").fillna(0).values
    moneyness = df.get("Moneyness", pd.Series(["N/A"] * n)).fillna("N/A").str.upper().values
    distance_pct = pd.to_numeric(df.get("Distance_Pct", 0), errors="coerce").fillna(0).values
    delta_raw = pd.to_numeric(df.get("Delta", np.nan), errors="coerce").fillna(np.nan).values
    abs_delta = np.abs(delta_raw)
    oi_chg = pd.to_numeric(df.get("OI_Chg", 0), errors="coerce").fillna(0).values

    # DTE desde Vencimiento
    today = date.today()
    dte = np.full(n, 999, dtype=int)  # default alto (pasa filtro)
    if "Vencimiento" in df.columns:
        for i, v in enumerate(df["Vencimiento"].values):
            parsed = _parse_dte(v)
            if parsed is not None:
                dte[i] = parsed

    # ── Máscaras ────────────────────────────────────────────────────────
    is_put = tipo == "PUT"
    is_ask = lado == "Ask"
    prem_l1 = premium >= HEDGE_ALERT_PREMIUM_L1
    oi_ok = oi_chg >= HEDGE_ALERT_OI_CHG_L1
    dte_ok = dte >= HEDGE_ALERT_MIN_DTE
    is_itm = moneyness == "ITM"
    delta_l1 = ~np.isnan(abs_delta) & (abs_delta >= HEDGE_ALERT_DELTA_L1)
    itm_or_deep = is_itm | delta_l1

    # Máscara base: todo nivel 1 como mínimo
    base = is_put & is_ask & prem_l1 & oi_ok & dte_ok & itm_or_deep

    # Score para nivel
    prem_l2 = premium >= HEDGE_ALERT_PREMIUM_L2
    delta_l2 = ~np.isnan(abs_delta) & (abs_delta >= HEDGE_ALERT_DELTA_L2)
    oi_l2 = oi_chg >= HEDGE_ALERT_OI_CHG_L2
    deep_itm = is_itm & (distance_pct >= ITM_DEEP_DISTANCE_PCT)

    score = (prem_l2.astype(int) * 2) + delta_l2.astype(int) + oi_l2.astype(int) + deep_itm.astype(int)
    is_critical = base & (score >= 2)
    is_warning = base & ~is_critical

    # ── Construir resultados ────────────────────────────────────────────
    alert_text = np.full(n, "", dtype=object)
    alert_level = np.full(n, "", dtype=object)
    alert_detail = np.full(n, "", dtype=object)

    alert_text[is_critical] = "🔴 ALTA ALERTA: Hedge Institucional Pesado"
    alert_text[is_warning] = "🟠 Protección Institucional Detectada"

    alert_level[is_critical] = "critical"
    alert_level[is_warning] = "warning"

    # Generar explicaciones para filas que califican
    for i in np.where(base)[0]:
        parts = [f"Prima ${premium[i]:,.0f}"]
        if not np.isnan(abs_delta[i]):
            parts.append(f"|Δ| {abs_delta[i]:.2f}")
        parts.append(f"OI↑ +{oi_chg[i]:,.0f}")
        if distance_pct[i] >= ITM_DEEP_DISTANCE_PCT:
            parts.append(f"ITM profundo ({distance_pct[i]:.1f}%)")
        if dte[i] >= 90:
            parts.append(f"DTE {dte[i]}d")
        detail = " · ".join(parts)
        if is_critical[i]:
            alert_detail[i] = f"PUT ITM comprado agresivamente con prima masiva → miedo institucional real. {detail}"
        else:
            alert_detail[i] = f"PUT ITM comprado en Ask → cobertura institucional contra caída. {detail}"

    return (
        pd.Series(alert_text, index=df.index),
        pd.Series(alert_level, index=df.index),
        pd.Series(alert_detail, index=df.index),
    )


def hedge_alert_badge(alert_text: str, level: str) -> str:
    """Return HTML badge for a hedge alert."""
    if not alert_text:
        return ""
    variant = "hedgecrit" if level == "critical" else "hedgewarn"
    return f'<span class="ok-badge ok-badge-{variant}">{alert_text}</span>'


def add_smart_money_tier(df: pd.DataFrame) -> pd.DataFrame:
    """Categoriza filas por cuartil de sm_flow_score en 4 tiers.

    Requiere que el DataFrame ya tenga la columna 'sm_flow_score'
    (generada por calculate_sm_flow_score). Si no existe, agrega
    la columna con valor 'N/A' sin lanzar excepción.

    Tiers:
        Retail  — score 0-50   (flujo minorista o señal débil)
        Mixed   — score 50-75  (señal mixta, sin consenso claro)
        Smart   — score 75-90  (alta probabilidad institucional)
        Whale   — score 90-100 (tier máximo: movimiento de whale)
    """
    if 'sm_flow_score' not in df.columns:
        df = df.copy()
        df['smart_money_tier'] = 'N/A'
        return df
    df = df.copy()
    df['smart_money_tier'] = pd.cut(
        df['sm_flow_score'],
        bins=[0, 50, 75, 90, 100],
        labels=['Retail', 'Mixed', 'Smart', 'Whale'],
        include_lowest=True,
    ).astype(str)
    return df
