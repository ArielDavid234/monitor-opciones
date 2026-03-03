# -*- coding: utf-8 -*-
"""
OptionsKing Analytics — Principio Central: Expected Value (EV).

El EV es la métrica más honesta en trading de opciones. Responde una
pregunta simple: "¿Tiene este spread edge matemático real?"

  EV = (POP × Crédito) − ((1 − POP) × Pérdida_Máxima)

Si EV > $0 → el spread es matemáticamente favorable a largo plazo.
Si EV < $0 → el spread destruye capital en expectativa.

Todas las fórmulas se expresan POR CONTRATO (× 100 acciones).

Uso típico:
    from core.optionkings_analytic import calculate_expected_value

    ev = calculate_expected_value(credit=1.50, pop=0.82, max_loss=3.50)
    # → {"ev_dollars": 76.5, "ev_percent": 21.9, "is_positive": True}
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


# ============================================================================
#   EXPECTED VALUE (EV) — Principio Central
# ============================================================================

def calculate_expected_value(
    credit: float,
    pop: float,
    max_loss: float,
) -> dict:
    """Calcula el Expected Value (EV) de un credit spread.

    Fórmula exacta (por contrato = × 100 acciones):

        crédito_$   = credit × 100
        pérdida_$   = max_loss × 100
        EV_$        = (POP × crédito_$) - ((1 - POP) × pérdida_$)
        EV_%        = (EV_$ / pérdida_$) × 100   # % del capital en riesgo

    Interpretación financiera:
        EV > $0  → el spread tiene edge matemático real. A largo plazo,
                   con suficientes trades, generas alfa positivo.
        EV < $0  → el spread destruye capital en expectativa.
                   NUNCA tomar este trade sin razón especial.
        EV = $0  → punto de equilibrio matemático. Sin edge.

    Ejemplo (Bull Put 1.50/3.50, POP 82%):
        EV = (0.82 × $150) − (0.18 × $350) = $123 − $63 = $60/contrato
        EV% = ($60 / $350) × 100 = 17.1%

    Args:
        credit:    Crédito neto recibido por acción (ej: 1.50).
        pop:       Probabilidad de ganancia en formato decimal 0–1 (ej: 0.82).
                   Corresponde a 1 - |delta| del strike vendido.
        max_loss:  Pérdida máxima por acción = width - credit (ej: 3.50).

    Returns:
        dict con:
        - ``ev_dollars`` (float): EV por contrato en dólares.
        - ``ev_percent`` (float): EV como % del capital en riesgo.
        - ``is_positive`` (bool): True si EV > 0 (spread con edge).
        - ``credit_dollars`` (float): Crédito por contrato.
        - ``max_loss_dollars`` (float): Pérdida máxima por contrato.
        - ``expected_profit`` (float): (POP × crédito_$).
        - ``expected_loss`` (float): ((1-POP) × pérdida_$).
    """
    # Validación básica
    if credit < 0 or max_loss <= 0 or not (0.0 <= pop <= 1.0):
        return {
            "ev_dollars": 0.0,
            "ev_percent": 0.0,
            "is_positive": False,
            "credit_dollars": 0.0,
            "max_loss_dollars": 0.0,
            "expected_profit": 0.0,
            "expected_loss": 0.0,
        }

    # Convertir a dólares por contrato (100 acciones)
    credit_dollars = round(credit * 100, 2)
    max_loss_dollars = round(max_loss * 100, 2)

    # Componentes del EV
    prob_loss = 1.0 - pop
    expected_profit = round(pop * credit_dollars, 2)
    expected_loss = round(prob_loss * max_loss_dollars, 2)

    ev_dollars = round(expected_profit - expected_loss, 2)
    ev_percent = round((ev_dollars / max_loss_dollars) * 100, 2) if max_loss_dollars > 0 else 0.0

    result = {
        "ev_dollars": ev_dollars,
        "ev_percent": ev_percent,
        "is_positive": ev_dollars > 0,
        "credit_dollars": credit_dollars,
        "max_loss_dollars": max_loss_dollars,
        "expected_profit": expected_profit,
        "expected_loss": expected_loss,
    }

    logger.debug(
        "EV calc: credit=$%.2f×100=$%.0f | max_loss=$%.2f×100=$%.0f | "
        "POP=%.1f%% → EV=$%.2f (%.1f%%)",
        credit, credit_dollars,
        max_loss, max_loss_dollars,
        pop * 100,
        ev_dollars, ev_percent,
    )

    return result


# ============================================================================
#   HELPER: ENRICH DATAFRAME CON COLUMNAS EV
# ============================================================================

def enrich_dataframe_with_ev(df) -> "pd.DataFrame":  # type: ignore[name-defined]
    """Agrega columnas 'EV $' y 'EV %' a un DataFrame de spreads.

    Vectoriza los cálculos de EV para todo el DataFrame de una sola pasada.
    Las columnas de entrada requeridas son:
        - ``'Crédito'``  — crédito neto por acción
        - ``'POP %'``   — probabilidad de ganancia en % (ej: 82.0)
        - ``'Riesgo Máx'`` — pérdida máxima por acción

    Args:
        df: DataFrame de spreads con las columnas indicadas.

    Returns:
        Copia del DataFrame con columnas ``'EV $'`` y ``'EV %'`` añadidas.
    """
    import pandas as pd

    df = df.copy()

    required = {"Crédito", "POP %", "Riesgo Máx"}
    missing = required - set(df.columns)
    if missing:
        logger.warning("enrich_dataframe_with_ev: faltan columnas %s", missing)
        df["EV $"] = 0.0
        df["EV %"] = 0.0
        return df

    # Operaciones vectorizadas — evita apply() fila por fila
    credit_d = df["Crédito"] * 100                    # crédito por contrato
    max_loss_d = df["Riesgo Máx"] * 100               # pérdida máxima por contrato
    pop = df["POP %"] / 100                           # prob decimal 0–1

    expected_profit = pop * credit_d
    expected_loss = (1 - pop) * max_loss_d
    ev = expected_profit - expected_loss

    df["EV $"] = ev.round(2)
    df["EV %"] = ((ev / max_loss_d) * 100).where(max_loss_d > 0, 0.0).round(2)

    return df


# ============================================================================
#   EV LABEL — etiqueta de texto para UI
# ============================================================================

def ev_label(ev_dollars: float) -> str:
    """Etiqueta de texto corta para mostrar el EV en la UI.

    Returns:
        Una string como 'Edge Fuerte ✅', 'Edge Débil ✅', 'Sin Edge ⚠️',
        o 'EV Negativo ❌'.
    """
    if ev_dollars >= 80:
        return "Edge Fuerte ✅"
    elif ev_dollars > 0:
        return "Edge Débil ✅"
    elif ev_dollars == 0:
        return "Sin Edge ⚠️"
    else:
        return "EV Negativo ❌"


# ============================================================================
#   MÉTRICAS COMPLETAS POR SPREAD — Aspecto 2 del PDF
# ============================================================================

def calculate_all_metrics(row: dict) -> dict:
    """Calcula TODAS las métricas de un spread individual (Aspecto 2 del PDF).

    Toma una fila del DataFrame de credit spreads y devuelve un dict con
    cada métrica calculada de forma exacta y documentada.

    Métricas calculadas:
        1. Crédito recibido (por contrato)
        2. Max Loss = (Width − Credit) × 100
        3. Breakeven (Bull Put: sold_strike − credit; Bear Call: sold_strike + credit)
        4. POP % (forwarded)
        5. Prob de Touch ≈ 2 × |Delta short strike| × 100
        6. EV ($) y EV (%) — via calculate_expected_value
        7. Volatility Edge = IV% − HV 20D (puntos porcentuales)
        8. Kelly Fraction (Half Kelly = EV/MaxLoss / 2)
        9. Risk of 3 Consecutive Losses (drawdown en $ para 1 contrato)
        10. Liquidez % = (Bid−Ask) / Crédito × 100

    Campos del row que debe contener:
        Crédito, Riesgo Máx, POP %, Delta Vendido, Strike Vendido,
        Strike Comprado, IV %, HV 20D (nuevo — agregado al escáner),
        DTE, Dist Strike %, Bid-Ask, Tipo, Retorno %
    """
    # ── Extraer valores del row ───────────────────────────────────────────
    credit      = float(row.get("Crédito", 0))
    max_loss_s  = float(row.get("Riesgo Máx", 0))   # per share
    pop_pct     = float(row.get("POP %", 0))
    pop         = pop_pct / 100.0
    delta       = float(row.get("Delta Vendido", 0))
    sold_strike = float(row.get("Strike Vendido", 0))
    iv_pct      = float(row.get("IV %", 0))         # IV del short strike en %
    hv_20d      = float(row.get("HV 20D", 0))       # HV 20D del subyacente en %
    dte         = int(row.get("DTE", 30))
    dist_pct    = float(row.get("Dist Strike %", 0))
    bid_ask     = float(row.get("Bid-Ask", 0))      # ask − bid del short (en $)
    tipo        = str(row.get("Tipo", "Bull Put"))
    retorno_pct = float(row.get("Retorno %", 0))
    iv_pctil    = float(row.get("IV Pctil", 0))     # IV Percentile (0–100)

    # ── 1 & 2 — Crédito y MaxLoss por contrato ───────────────────────────
    credit_dollars   = round(credit * 100, 2)
    max_loss_dollars = round(max_loss_s * 100, 2)

    # ── 3 — Breakeven ────────────────────────────────────────────────────
    if "Bull Put" in tipo:
        breakeven = round(sold_strike - credit, 2)
    else:   # Bear Call
        breakeven = round(sold_strike + credit, 2)

    # ── 5 — Probabilidad de Touch ≈ 2 × |Δ| × 100 ───────────────────────
    prob_touch_pct = round(min(2.0 * abs(delta) * 100.0, 100.0), 1)

    # ── 6 — Expected Value ───────────────────────────────────────────────
    ev_data = calculate_expected_value(credit, pop, max_loss_s)

    # ── 7 — Volatility Edge (puntos %) ───────────────────────────────────
    # > 0 → IV más cara que la HV histórica → prima inflada → ideal para vender
    # < 0 → IV más barata que HV → riesgo de vender barato
    vol_edge = round(iv_pct - hv_20d, 2)

    # ── 8 — Half Kelly Fraction ───────────────────────────────────────────
    # Kelly_full = EV / MaxLoss (como fracción de capital)
    # Half Kelly = Kelly_full / 2 → más conservador, reduce riesgo de ruina
    if max_loss_dollars > 0:
        kelly_full  = ev_data["ev_dollars"] / max_loss_dollars
        half_kelly  = round(kelly_full / 2.0, 4)
    else:
        half_kelly = 0.0

    # ── 9 — Risk of 3 Consecutive Losses ─────────────────────────────────
    # Escenario de drawdown: 3 pérdidas seguidas (poco probable pero posible)
    # P(3 losses) = (1 − POP)³   |   Drawdown = P × MaxLoss × contratos (1)
    prob_loss      = 1.0 - pop
    risk_3_losses  = round((prob_loss ** 3) * max_loss_dollars, 2)

    # ── 10 — Liquidez % (del crédito) ────────────────────────────────────
    # Spread bid-ask del short / crédito del spread
    # < 5%  → excelente liquidez (verde)
    # 5-10% → liquidez media     (amarillo)
    # > 10% → spread muy ancho   (rojo)
    liquidez_pct = round((bid_ask / credit) * 100.0, 1) if credit > 0 else 999.0

    return {
        # ── Básicos ──────────────────────────────────────────────────────
        "credit_dollars":      credit_dollars,
        "max_loss_dollars":    max_loss_dollars,
        "breakeven":           breakeven,
        "pop_pct":             pop_pct,
        "retorno_pct":         retorno_pct,
        # ── Métricas nuevas ───────────────────────────────────────────────
        "prob_touch_pct":      prob_touch_pct,
        "ev_dollars":          ev_data["ev_dollars"],
        "ev_percent":          ev_data["ev_percent"],
        "ev_is_positive":      ev_data["is_positive"],
        "expected_profit":     ev_data["expected_profit"],
        "expected_loss_amt":   ev_data["expected_loss"],
        "vol_edge":            vol_edge,
        "iv_pct":              iv_pct,
        "hv_20d":              hv_20d,
        "iv_pctil":            iv_pctil,
        "half_kelly":          half_kelly,
        "risk_3_losses":       risk_3_losses,
        "liquidez_pct":        liquidez_pct,
        # ── Contexto ─────────────────────────────────────────────────────
        "dte":                 dte,
        "dist_pct":            dist_pct,
    }


# ============================================================================
#   SCORE PROFESIONAL 0-100 — Aspecto 3 del PDF
# ============================================================================

def calculate_professional_score(metrics: dict) -> dict:
    """Score Profesional 0–100 para un credit spread (Aspecto 3 del PDF).

    Fórmula:
        Score = 30% EV_norm + 20% VolEdge_norm + 15% RR_norm
                + 15% Dist_norm + 10% DTE_norm + 10% Liq_norm

    100% matemático, sin subjetividad. Rangos de normalización fijos
    (no min-max del dataset) para que el score sea comparable entre sesiones.

    Normalización de cada componente (0–100):
        EV_norm       → EV de -$200 a +$200/contrato  (50 = breakeven)
        VolEdge_norm  → Vol Edge de -20% a +20% pp    (50 = IV = HV)
        RR_norm       → Retorno % de 0 a 40%
        Dist_norm     → Distancia óptima 5.5% ±9%     (pico en 5.5%)
        DTE_norm      → DTE óptimo 37d ±27d           (pico en 30-45)
        Liq_norm      → Liquidez bid-ask 0-10%        (0%=100, ≥10%=0)

    Returns:
        dict con:
        - ``score`` (float): Score final 0–100.
        - ``grade`` (str): 'A' (≥80), 'B' (≥65), 'C' (≥50), 'D' (<50).
        - ``grade_label`` (str): etiqueta en español.
        - componentes individuales: ev_c, vol_edge_c, rr_c, dist_c, dte_c, liq_c
    """
    # ── Extraer métricas ──────────────────────────────────────────────────
    ev_d      = metrics.get("ev_dollars", 0.0)
    vol_edge  = metrics.get("vol_edge", 0.0)
    retorno   = metrics.get("retorno_pct", 0.0)
    dist      = metrics.get("dist_pct", 0.0)
    dte       = metrics.get("dte", 37)
    liq_pct   = metrics.get("liquidez_pct", 10.0)

    # ── Normalizar 0–100 ─────────────────────────────────────────────────

    # 1. EV (30%): [-$200, +$200] → [0, 100]. $0 = 50 (punto de equilibrio).
    ev_c = max(0.0, min(100.0, (ev_d + 200.0) / 400.0 * 100.0))

    # 2. Volatility Edge (20%): [-20pp, +20pp] → [0, 100]. 0pp = 50.
    vol_edge_c = max(0.0, min(100.0, (vol_edge + 20.0) / 40.0 * 100.0))

    # 3. Risk/Reward (15%): Retorno% de 0 a 40%. >40% da 100.
    rr_c = max(0.0, min(100.0, retorno / 40.0 * 100.0))

    # 4. Distancia óptima del strike (15%):
    #    Pico en 5.5%, penalización lineal de 14 pts por cada punto porcentual.
    #    Muy cerca (<3%) = peligroso. Muy lejos (>12%) = poco crédito.
    dist_c = max(0.0, 100.0 - abs(dist - 5.5) * 14.0)

    # 5. DTE Ideal (10%): Pico en 37d. Penaliza ±3.5 pts por día fuera.
    #    DTE = 7 → ~70 pts abajo; DTE = 60 → ~80 pts abajo; DTE = 37 → 100.
    dte_c = max(0.0, 100.0 - abs(float(dte) - 37.0) * 3.5)

    # 6. Liquidez (10%): [0%, 10%] bid-ask/credit. 0% = 100, ≥10% = 0.
    liq_c = max(0.0, min(100.0, (10.0 - liq_pct) / 10.0 * 100.0))

    # ── Score ponderado ───────────────────────────────────────────────────
    score = (
        0.30 * ev_c +
        0.20 * vol_edge_c +
        0.15 * rr_c +
        0.15 * dist_c +
        0.10 * dte_c +
        0.10 * liq_c
    )
    score = round(score, 1)

    # ── Grade ─────────────────────────────────────────────────────────────
    if score >= 80:
        grade, grade_label, grade_color = "A", "Excelente — Edge Real", "#22c55e"
    elif score >= 65:
        grade, grade_label, grade_color = "B", "Buena — Edge Moderado", "#84cc16"
    elif score >= 50:
        grade, grade_label, grade_color = "C", "Aceptable — Edge Bajo", "#fbbf24"
    else:
        grade, grade_label, grade_color = "D", "Débil — Sin Edge Claro", "#ef4444"

    return {
        "score":       score,
        "grade":       grade,
        "grade_label": grade_label,
        "grade_color": grade_color,
        # Componentes individuales (útil para desglose)
        "ev_c":       round(ev_c, 1),
        "vol_edge_c": round(vol_edge_c, 1),
        "rr_c":       round(rr_c, 1),
        "dist_c":     round(dist_c, 1),
        "dte_c":      round(dte_c, 1),
        "liq_c":      round(liq_c, 1),
    }


# ============================================================================
#   FILTROS INTELIGENTES — auto-filter por criterios del PDF
# ============================================================================

def passes_smart_filters(
    row: dict,
    metrics: dict,
    account_size: float = 25_000.0,
    max_loss_pct_account: float = 0.05,
) -> tuple[bool, list[str]]:
    """Verifica si un spread pasa los filtros inteligentes del PDF.

    Filtros aplicados:
        1. EV > 0  (spread con edge positivo)
        2. IV Percentile > 50  (IV más cara que la mitad histórica)
        3. Liquidez < 5% del crédito  (spread bid-ask ajustado)
        4. Prob Touch < 35%  (no demasiado cerca del dinero)
        5. Max Loss < X% de la cuenta  (gestión del riesgo)

    Returns:
        Tuple de (pasa: bool, razones_rechazo: list[str])
    """
    rechazos: list[str] = []

    if not metrics.get("ev_is_positive", False):
        rechazos.append("EV ≤ $0 — sin edge matemático")

    iv_pctil = float(row.get("IV Pctil", 0))
    if iv_pctil <= 50:
        rechazos.append(f"IV Pctil {iv_pctil:.0f}% ≤ 50% — prima no inflada")

    liq = metrics.get("liquidez_pct", 999.0)
    if liq >= 5.0:
        rechazos.append(f"Liquidez {liq:.1f}% ≥ 5% del crédito")

    pt = metrics.get("prob_touch_pct", 100.0)
    if pt >= 35.0:
        rechazos.append(f"Prob Touch {pt:.1f}% ≥ 35% — strike demasiado cercano")

    ml = metrics.get("max_loss_dollars", 0.0)
    max_allowed = account_size * max_loss_pct_account
    if ml > max_allowed:
        rechazos.append(
            f"Max Loss ${ml:.0f} > {max_loss_pct_account*100:.0f}% cuenta (${max_allowed:.0f})"
        )

    return (len(rechazos) == 0, rechazos)


# ============================================================================
#   GESTIÓN DE CUENTA — Aspecto 5 del PDF
# ============================================================================

def calculate_account_management(
    metrics: dict,
    account_size: float,
    risk_pct: float,
) -> dict:
    """Calcula gestión de cuenta para un spread individual (Aspecto 5 del PDF).

    Devuelve:
        - Contratos recomendados según capital en riesgo
        - Riesgo real en $ y % de la cuenta
        - Drawdown en $ y % para 1, 2, 3 y 4 pérdidas consecutivas
        - Probabilidad estadística de cada racha de pérdidas

    Fórmulas:
        capital_riesgo      = account_size × (risk_pct / 100)
        contratos           = floor(capital_riesgo / max_loss_dollars)  [mín 1]
        riesgo_real_$       = contratos × max_loss_dollars
        riesgo_real_%       = riesgo_real_$ / account_size × 100
        drawdown_n_$        = contratos × max_loss_dollars × n
        prob_n_losses       = (1 − POP)ⁿ × 100

    Args:
        metrics:      dict de calculate_all_metrics(row).
        account_size: tamaño de la cuenta en $.
        risk_pct:     % de la cuenta a arriesgar por trade (ej 2.0 = 2%).
    """
    max_loss    = metrics.get("max_loss_dollars", 0.0)
    pop         = metrics.get("pop_pct", 80.0) / 100.0
    prob_loss   = max(0.0, 1.0 - pop)

    # ── Contratos recomendados ────────────────────────────────────────────
    capital_riesgo = account_size * (risk_pct / 100.0)
    if max_loss > 0:
        contratos = max(1, int(capital_riesgo // max_loss))
    else:
        contratos = 1

    # ── Riesgo real ───────────────────────────────────────────────────────
    riesgo_real_d   = round(contratos * max_loss, 2)
    riesgo_real_pct = round(riesgo_real_d / account_size * 100, 2) if account_size > 0 else 0.0

    # ── Drawdowns absolutos (si se dan n pérdidas consecutivas) ─────────
    dd_1 = round(max_loss * contratos,       2)
    dd_2 = round(max_loss * contratos * 2.0, 2)
    dd_3 = round(max_loss * contratos * 3.0, 2)
    dd_4 = round(max_loss * contratos * 4.0, 2)

    # ── Drawdowns como % de la cuenta ────────────────────────────────────
    _safe_acc = account_size if account_size > 0 else 1
    dd_1_pct = round(dd_1 / _safe_acc * 100, 2)
    dd_2_pct = round(dd_2 / _safe_acc * 100, 2)
    dd_3_pct = round(dd_3 / _safe_acc * 100, 2)
    dd_4_pct = round(dd_4 / _safe_acc * 100, 2)

    # ── Probabilidades de cada racha ──────────────────────────────────────
    prob_1 = round(prob_loss ** 1 * 100, 2)
    prob_2 = round(prob_loss ** 2 * 100, 2)
    prob_3 = round(prob_loss ** 3 * 100, 2)
    prob_4 = round(prob_loss ** 4 * 100, 2)

    return {
        "contratos":          contratos,
        "capital_riesgo":     round(capital_riesgo, 2),
        "riesgo_real_d":      riesgo_real_d,
        "riesgo_real_pct":    riesgo_real_pct,
        "max_loss_contract":  max_loss,
        # Drawdowns absolutos
        "dd_1":     dd_1,   "dd_1_pct": dd_1_pct,
        "dd_2":     dd_2,   "dd_2_pct": dd_2_pct,
        "dd_3":     dd_3,   "dd_3_pct": dd_3_pct,
        "dd_4":     dd_4,   "dd_4_pct": dd_4_pct,
        # Probabilidades
        "prob_1": prob_1,
        "prob_2": prob_2,
        "prob_3": prob_3,
        "prob_4": prob_4,
    }


# ============================================================================
#   FILTROS INTELIGENTES REACTIVOS — Aspecto 4 del PDF
# ============================================================================

def apply_intelligent_filters(
    spreads_data: list,
    account_size: float,
    risk_pct: float,
) -> list:
    """Re-aplica los 5 filtros inteligentes del PDF sobre una lista ya computada.

    Diseñado para reactivity: cada vez que el usuario cambia account_size o
    risk_pct en el sidebar, esta función se llama sin re-escanear la API.

    Los filtros (todos obligatorios):
        1. EV > $0
        2. IV Percentile > 50%
        3. Liquidez < 5% del crédito
        4. Prob Touch < 35%
        5. Max Loss < risk_pct% de la cuenta

    Args:
        spreads_data: lista de dicts con claves 'row', 'metrics', 'score'.
        account_size: tamaño de cuenta en $.
        risk_pct:     % de riesgo por trade (ej 2.0 = 2%).

    Returns:
        Misma lista con 'pasa' y 'rechazos' actualizados según los parámetros.
    """
    max_loss_pct_account = risk_pct / 100.0
    result = []
    for item in spreads_data:
        pasa, rechazos = passes_smart_filters(
            item["row"],
            item["metrics"],
            account_size=account_size,
            max_loss_pct_account=max_loss_pct_account,
        )
        result.append({**item, "pasa": pasa, "rechazos": rechazos})
    return result
