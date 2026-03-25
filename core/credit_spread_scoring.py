# -*- coding: utf-8 -*-
"""Credit Spread — Income Score, Opportunity Score, and breakdowns."""
from __future__ import annotations

import logging

from config.constants import (
    INCOME_SCORE_IV_RANK_MIN, INCOME_SCORE_IV_PCTIL_MIN,
    INCOME_SCORE_DELTA_MAX, INCOME_SCORE_VOL_MIN,
    INCOME_SCORE_OI_MIN, INCOME_SCORE_DIST_PCT_MIN,
    INCOME_SCORE_LABEL_ALTA, INCOME_SCORE_LABEL_BUENA,
    OPP_SCORE_IV_RANK_MIN, OPP_SCORE_DELTA_MIN, OPP_SCORE_DELTA_MAX,
    OPP_SCORE_CREDIT_WIDTH_PCT, OPP_SCORE_DIST_PCT_MIN,
    OPP_SCORE_VOL_MIN, OPP_SCORE_OI_MIN, OPP_SCORE_BA_CREDIT_PCT,
    OPP_SCORE_MIN_SHOW,
)

logger = logging.getLogger(__name__)

#  Income Score — puntuación única de cada spread (0–100)
# ────────────────────────────────────────────────────────────────────────────

def compute_income_score(row: dict) -> tuple[float, str]:
    """Calcula el Income Score (0–100) para un spread individual.

    Componentes (20 pts cada uno, total máximo 100):
      1. IV alto: IV Rank > 40 ó IV Percentile > 60
      2. Delta bajo: |delta vendido| ≤ 0.20
      3. Liquidez: volumen > 100 y OI > 200
      4. Tendencia alineada: Bull Put + Alcista ó Bear Call + Bajista
      5. Distancia del strike: dist_pct > 5.0 %

    Umbrales configurables en config/constants.py.

    Returns
    -------
    tuple[float, str]
        (score redondeado a 1 decimal, etiqueta en español)
    """
    score = 0.0

    # 1. IV alto
    iv_rank = row.get("IV Rank", 0) or 0
    iv_pctil = row.get("IV Pctil", 0) or 0
    if iv_rank > INCOME_SCORE_IV_RANK_MIN or iv_pctil > INCOME_SCORE_IV_PCTIL_MIN:
        score += 20

    # 2. Delta bajo
    delta = abs(row.get("Delta Vendido", 1.0) or 1.0)
    if delta <= INCOME_SCORE_DELTA_MAX:
        score += 20

    # 3. Liquidez
    vol = row.get("Volumen", 0) or 0
    oi = row.get("OI", 0) or 0
    if vol > INCOME_SCORE_VOL_MIN and oi > INCOME_SCORE_OI_MIN:
        score += 20

    # 4. Tendencia alineada con tipo de spread
    tipo = row.get("Tipo", "")
    tendencia = row.get("Tendencia", "Neutral")
    if (tipo == "Bull Put" and tendencia == "Alcista") or \
       (tipo == "Bear Call" and tendencia == "Bajista"):
        score += 20

    # 5. Distancia del strike
    dist_pct = row.get("Dist Strike %", 0) or 0
    if dist_pct > INCOME_SCORE_DIST_PCT_MIN:
        score += 20

    score = round(min(max(score, 0), 100), 1)

    # Etiqueta
    if score >= INCOME_SCORE_LABEL_ALTA:
        label = "Alta probabilidad"
    elif score >= INCOME_SCORE_LABEL_BUENA:
        label = "Buena"
    else:
        label = "Evitar"

    return score, label


# ────────────────────────────────────────────────────────────────────────────
#  Score de Oportunidad (0–100) — scoring propio de cada spread
# ────────────────────────────────────────────────────────────────────────────

def compute_opportunity_score(row: dict) -> tuple[float, str]:
    """Score de Oportunidad (0–100) para un spread individual.

    Componentes (20 pts cada uno):
      1. IV Rank > 40
      2. Delta en sweet spot (0.12–0.18)
      3. Crédito ≥ 20 % del ancho del spread
      4. Distancia al strike > 4 %
      5. Liquidez alta (vol > 100, OI > 500, B-A ≤ 10 % del crédito)

    Returns: (score, label)
    """
    score = 0.0

    # 1. IV Rank alto
    iv_rank = row.get("IV Rank", 0) or 0
    if iv_rank > OPP_SCORE_IV_RANK_MIN:
        score += 20

    # 2. Delta sweet spot
    delta = abs(row.get("Delta Vendido", 0) or 0)
    if OPP_SCORE_DELTA_MIN <= delta <= OPP_SCORE_DELTA_MAX:
        score += 20

    # 3. Crédito vs ancho
    width = abs(
        (row.get("Strike Vendido", 0) or 0) - (row.get("Strike Comprado", 0) or 0)
    )
    credit = row.get("Crédito", 0) or 0
    if width > 0 and credit >= OPP_SCORE_CREDIT_WIDTH_PCT * width:
        score += 20

    # 4. Distancia del strike
    dist_pct = row.get("Dist Strike %", 0) or 0
    if dist_pct > OPP_SCORE_DIST_PCT_MIN:
        score += 20

    # 5. Liquidez alta
    vol = row.get("Volumen", 0) or 0
    oi = row.get("OI", 0) or 0
    ba = row.get("Bid-Ask", 0) or 0
    ba_ratio = ba / max(credit, 0.01)
    if vol > OPP_SCORE_VOL_MIN and oi > OPP_SCORE_OI_MIN and ba_ratio <= OPP_SCORE_BA_CREDIT_PCT:
        score += 20

    score = round(min(max(score, 0), 100), 1)

    if score >= 80:
        label = "Excelente"
    elif score >= OPP_SCORE_MIN_SHOW:
        label = "Buena"
    else:
        label = "Baja"

    return score, label


def opportunity_score_breakdown(row: dict) -> list[dict]:
    """Desglose detallado del Score de Oportunidad para una fila.

    Devuelve una lista de dicts con criterio, detalle, puntos, máximo, cumple.
    Útil para mostrar al usuario qué criterios cumplió cada spread.
    """
    breakdown: list[dict] = []

    # 1. IV Rank
    ivr = row.get("IV Rank", 0) or 0
    p = ivr > OPP_SCORE_IV_RANK_MIN
    breakdown.append({
        "criterio": "IV Rank > 40",
        "detalle": f"IV Rank actual: {ivr:.0f}%",
        "puntos": 20 if p else 0, "maximo": 20, "cumple": p,
    })

    # 2. Delta sweet spot
    delta = abs(row.get("Delta Vendido", 0) or 0)
    p = OPP_SCORE_DELTA_MIN <= delta <= OPP_SCORE_DELTA_MAX
    breakdown.append({
        "criterio": "Delta 0.12 – 0.18 (sweet spot)",
        "detalle": f"|Δ| = {delta:.3f}",
        "puntos": 20 if p else 0, "maximo": 20, "cumple": p,
    })

    # 3. Crédito vs ancho
    width = abs(
        (row.get("Strike Vendido", 0) or 0) - (row.get("Strike Comprado", 0) or 0)
    )
    credit = row.get("Crédito", 0) or 0
    ratio = credit / width * 100 if width > 0 else 0
    p = width > 0 and credit >= OPP_SCORE_CREDIT_WIDTH_PCT * width
    breakdown.append({
        "criterio": f"Crédito ≥ {OPP_SCORE_CREDIT_WIDTH_PCT*100:.0f}% del ancho",
        "detalle": f"${credit:.2f} / ${width:.0f} = {ratio:.0f}%",
        "puntos": 20 if p else 0, "maximo": 20, "cumple": p,
    })

    # 4. Distancia
    dist = row.get("Dist Strike %", 0) or 0
    p = dist > OPP_SCORE_DIST_PCT_MIN
    breakdown.append({
        "criterio": "Distancia > 4%",
        "detalle": f"Distancia: {dist:.1f}%",
        "puntos": 20 if p else 0, "maximo": 20, "cumple": p,
    })

    # 5. Liquidez
    vol = row.get("Volumen", 0) or 0
    oi = row.get("OI", 0) or 0
    ba = row.get("Bid-Ask", 0) or 0
    ba_pct = ba / max(credit, 0.01) * 100
    cv = vol > OPP_SCORE_VOL_MIN
    co = oi > OPP_SCORE_OI_MIN
    cb = (ba_pct / 100) <= OPP_SCORE_BA_CREDIT_PCT
    p = cv and co and cb
    breakdown.append({
        "criterio": "Liquidez (Vol>100, OI>500, B-A≤10%)",
        "detalle": f"Vol:{vol:,} · OI:{oi:,} · B-A:{ba_pct:.0f}% crédito",
        "puntos": 20 if p else 0, "maximo": 20, "cumple": p,
    })

    return breakdown


# ────────────────────────────────────────────────────────────────────────────
#  IV Rank & IV Percentile  — delegado a core.iv_rank (fuente canónica)
# ────────────────────────────────────────────────────────────────────────────
