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
