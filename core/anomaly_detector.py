# -*- coding: utf-8 -*-
"""
Anomaly Detector — Detección de actividad inusual en opciones usando
IsolationForest (sklearn).

Detecta patrones fuera de lo normal: volumen absurdamente alto, ratios
prima/OI anómalos, IV extrema, etc. Asigna un score de anomalía de
0 (normal) a 100 (sumamente inusual).
"""
import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Feature columns used to train the anomaly detector
_FEATURE_COLS = [
    "Volumen",
    "OI",
    "Prima_Vol",
    "IV",
    "Delta",
    "vol_oi_ratio",     # computed
    "prima_per_contract",  # computed
    "iv_vs_median",     # computed
]


def _prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    """Prepara el DataFrame con features derivados para el detector."""
    fe = df.copy()

    # Volume / OI ratio — valores muy altos indican actividad inusual
    fe["vol_oi_ratio"] = np.where(
        fe["OI"] > 0,
        fe["Volumen"] / fe["OI"],
        0,
    )

    # Prima por contrato
    fe["prima_per_contract"] = np.where(
        fe["Volumen"] > 0,
        fe["Prima_Vol"] / fe["Volumen"],
        0,
    )

    # IV vs mediana del dataset
    iv_median = fe["IV"].median()
    fe["iv_vs_median"] = np.where(
        iv_median > 0,
        fe["IV"] / iv_median,
        1,
    )

    # Normalizar Delta a absoluto
    fe["Delta"] = fe["Delta"].abs()

    return fe


def detectar_anomalias(
    datos: list,
    contamination: float = 0.08,
    min_rows: int = 30,
) -> Optional[pd.DataFrame]:
    """Detecta opciones con actividad anómala usando IsolationForest.

    Args:
        datos: Lista de dicts del scanner (st.session_state.datos_completos).
        contamination: Fracción esperada de outliers (0.08 = 8%).
        min_rows: Mínimo de filas necesarias para entrenar el modelo.

    Returns:
        DataFrame con columns originales + 'anomaly_score' (0-100) +
        'is_anomaly' (bool), o None si no hay suficientes datos.
    """
    try:
        from sklearn.ensemble import IsolationForest
    except ImportError:
        logger.warning(
            "scikit-learn no instalado — anomaly detection deshabilitado. "
            "Instalar con: pip install scikit-learn"
        )
        return None

    if not datos or len(datos) < min_rows:
        logger.info(f"Datos insuficientes para anomaly detection ({len(datos) if datos else 0} < {min_rows})")
        return None

    df = pd.DataFrame(datos)

    # Verificar columnas requeridas
    required = {"Volumen", "OI", "Prima_Vol", "IV", "Delta"}
    if "Prima_Volumen" in df.columns and "Prima_Vol" not in df.columns:
        df = df.rename(columns={"Prima_Volumen": "Prima_Vol"})
    missing = required - set(df.columns)
    if missing:
        logger.warning(f"Columnas faltantes para anomaly detection: {missing}")
        return None

    df_fe = _prepare_features(df)

    # Seleccionar features disponibles
    available_feats = [c for c in _FEATURE_COLS if c in df_fe.columns]
    if len(available_feats) < 4:
        logger.warning(f"Features insuficientes: {available_feats}")
        return None

    X = df_fe[available_feats].fillna(0).values

    # Entrenar IsolationForest
    iso = IsolationForest(
        n_estimators=100,
        contamination=contamination,
        random_state=42,
        n_jobs=-1,
    )
    iso.fit(X)

    # score_samples devuelve valores negativos (más negativo = más anómalo)
    raw_scores = iso.score_samples(X)
    predictions = iso.predict(X)  # -1 = anomaly, 1 = normal

    # Convertir a escala 0-100 (100 = más anómalo)
    score_min = raw_scores.min()
    score_max = raw_scores.max()
    score_range = score_max - score_min
    if score_range > 0:
        # Invertir: raw más negativo → score más alto
        anomaly_scores = ((score_max - raw_scores) / score_range) * 100
    else:
        anomaly_scores = np.full(len(raw_scores), 50.0)

    df["anomaly_score"] = np.round(anomaly_scores, 1)
    df["is_anomaly"] = predictions == -1

    n_anomalies = df["is_anomaly"].sum()
    logger.info(
        f"Anomaly detection: {n_anomalies}/{len(df)} anomalías detectadas "
        f"(contamination={contamination})"
    )

    return df


def anomaly_badge(score: float, is_anomaly: bool) -> str:
    """Genera badge HTML para el score de anomalía.

    Args:
        score: Anomaly score (0-100).
        is_anomaly: True si fue clasificado como anomalía.

    Returns:
        HTML string del badge.
    """
    if is_anomaly and score >= 75:
        style = "background:rgba(239,68,68,0.7);color:#fff;font-weight:700;"
        label = f"🔴 {score:.0f}"
    elif is_anomaly:
        style = "background:rgba(245,158,11,0.6);color:#0f172a;font-weight:700;"
        label = f"🟡 {score:.0f}"
    elif score >= 60:
        style = "background:rgba(245,158,11,0.3);color:#f59e0b;"
        label = f"⚠ {score:.0f}"
    else:
        style = "background:rgba(148,163,184,0.15);color:#94a3b8;"
        label = f"{score:.0f}"

    return f'<span class="ok-badge" style="{style}">{label}</span>'
