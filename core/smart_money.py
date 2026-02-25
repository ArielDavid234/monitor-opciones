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
