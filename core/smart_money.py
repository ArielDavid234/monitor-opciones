# -*- coding: utf-8 -*-
"""
Smart Money Flow Score — Puntuación de convicción institucional (0-100).

Combina cuatro señales independientes para cuantificar la probabilidad de que
una transacción de opciones sea de origen institucional / "smart money":
    1. Volume Intensity   — ¿cuánto volumen relativo hay?
    2. OI Freshness       — ¿el volumen supera ampliamente el OI (nueva posición)?
    3. Delta Conviction   — ¿el delta indica una apuesta direccional fuerte?
    4. Moneyness Sweet Spot — ¿está en la zona de máxima eficiencia (5-8% OTM/ITM)?
"""
import numpy as np
import pandas as pd


def calculate_sm_flow_score(df: pd.DataFrame, spot_price: float) -> pd.DataFrame:
    """
    Smart Money Conviction Score (0-100)
    Combina: Volume Intensity + OI Freshness + Delta Conviction + Moneyness Sweet Spot
    Usado en el scanner de unusual options activity.
    """
    df = df.copy()

    # ── Column aliases ───────────────────────────────────────────────────────
    # Supports both lowercase/yfinance naming and scanner title-case naming.
    # If the scanner columns exist (Volumen, OI, Delta, Strike) and the
    # lowercase versions don't, create lowercase aliases so the formula below
    # can always reference the same names regardless of the data source.
    _aliases = {
        "Volumen": "volume",
        "OI":      "openInterest",
        "Delta":   "delta",
        "Strike":  "strike",
    }
    for src, dst in _aliases.items():
        if src in df.columns and dst not in df.columns:
            df[dst] = df[src]

    # 1. Volume Intensity
    df['vol_intensity'] = df['volume'].fillna(0).clip(lower=50)
    df['vol_score'] = np.minimum(100, (df['vol_intensity'] / 800) * 100)

    # 2. OI Freshness (volume >> OI = new smart money position)
    df['oi_fresh_ratio'] = df['vol_intensity'] / df['openInterest'].replace(0, 100).clip(lower=100)
    df['oi_score'] = np.minimum(100, df['oi_fresh_ratio'] * 35)

    # 3. Delta Conviction
    df['delta_abs'] = df['delta'].abs().clip(upper=0.99)
    df['delta_score'] = df['delta_abs'] * 105

    # 4. Moneyness Sweet Spot (peak at 5-8% OTM/ITM)
    df['moneyness_pct'] = (df['strike'] - spot_price) / spot_price
    df['abs_moneyness'] = df['moneyness_pct'].abs()
    df['moneyness_score'] = 100 * np.exp(-df['abs_moneyness'] / 0.065)

    # Composite Score (pesos optimizados 2024-2025)
    df['sm_flow_score'] = (
        0.30 * df['vol_score'] +
        0.28 * df['oi_score'] +
        0.25 * df['delta_score'] +
        0.17 * df['moneyness_score']
    ).round(1).clip(0, 100)

    # Bonus if already flagged as smart money hedge
    if 'is_smart_money_hedge' in df.columns:
        df.loc[df['is_smart_money_hedge'], 'sm_flow_score'] *= 1.12
        df['sm_flow_score'] = df['sm_flow_score'].clip(upper=100)

    return df


# ============================================================================
#                    INSTITUTIONAL FLOW SCORE (0-100)
# ============================================================================
def calculate_institutional_flow_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Institutional Conviction Score (0-100) basado EXACTAMENTE en la tabla de Delta del usuario
    + Gamma + Premium Notional + DTE (Expiration).

    Tabla de referencia:
        Delta 0.10-0.25  → Apuestas especulativas (baratas, OTM) — Bajo, mucho retail
        Delta 0.30-0.50  → Posición direccional real — Importante
        Delta 0.60-0.80  → Posición agresiva / institucional — Muy importante
        Delta 0.80-1.00  → Sustituto de acciones / cobertura — Institucional / hedging

    Reglas especiales:
        - Delta ~0.40-0.50 + gran prima → Alta probabilidad institucional (+18% bonus)
        - Delta 0.60-0.80 → Común en hedge funds, posiciones grandes direccionales
        - Evitar Delta <0.20 a menos que prima + repetición muy altas
    """
    if df.empty:
        return df
    df = df.copy()

    # ── DTE (Days To Expiration) ─────────────────────────────────────────
    today = pd.to_datetime('today').normalize()
    venc = pd.to_datetime(df.get('Vencimiento', pd.Series(dtype='str')), errors='coerce')
    df['DTE'] = (venc - today).dt.days.clip(lower=0).fillna(0).astype(int)

    df['abs_delta'] = pd.to_numeric(df.get('Delta', 0), errors='coerce').abs().fillna(0).clip(upper=1.0)

    # ── Delta Score según tabla EXACTA del usuario ───────────────────────
    conditions = [
        (df['abs_delta'] < 0.10),
        (df['abs_delta'] >= 0.10) & (df['abs_delta'] < 0.30),
        (df['abs_delta'] >= 0.30) & (df['abs_delta'] < 0.60),
        (df['abs_delta'] >= 0.60) & (df['abs_delta'] <= 0.80),
        (df['abs_delta'] > 0.80),
    ]
    choices = [15, 35, 75, 100, 82]
    df['delta_score_inst'] = np.select(conditions, choices, default=50).astype(float)

    # Bonus especial del usuario (Delta 0.40-0.52 + prima alta)
    prima = pd.to_numeric(df.get('Prima_Volumen', 0), errors='coerce').fillna(0)
    mask_bonus = (df['abs_delta'] >= 0.40) & (df['abs_delta'] <= 0.52) & (prima >= 100_000)
    df.loc[mask_bonus, 'delta_score_inst'] = (df.loc[mask_bonus, 'delta_score_inst'] * 1.18).clip(upper=100)

    # ── Gamma Score (institucional odia gamma alto → prefiere gamma bajo) ──
    gamma = pd.to_numeric(df.get('Gamma', 0), errors='coerce').fillna(0)
    df['gamma_score_inst'] = np.clip(100 - (gamma * 1400), 0, 100)

    # ── Premium Notional Score ───────────────────────────────────────────
    df['premium_score_inst'] = np.clip((prima / 450_000) * 100, 0, 100)

    # ── DTE Sweet Spot (ideal ~45 días) ──────────────────────────────────
    df['dte_score_inst'] = (100 * np.exp(-np.abs(df['DTE'] - 45) / 38)).clip(20, 100)

    # ── Composite Institutional Flow Score (Delta pesa más) ──────────────
    df['inst_flow_score'] = (
        0.42 * df['delta_score_inst'] +
        0.18 * df['gamma_score_inst'] +
        0.25 * df['premium_score_inst'] +
        0.15 * df['dte_score_inst']
    ).round(1).clip(0, 100)

    # ── Tier cualitativo ─────────────────────────────────────────────────
    df['inst_tier'] = pd.cut(
        df['inst_flow_score'],
        bins=[0, 55, 75, 88, 100],
        labels=['Retail', 'Mixed', 'Institutional', 'Whale'],
        include_lowest=True,
    ).astype(str)

    return df
