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
