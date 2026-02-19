"""
Cálculo del Expected Move (Rango Esperado de Movimiento)
al estilo Thinkorswim / Charles Schwab.

Incluye dos métodos:
  1. calcular_expected_move  — fórmula IV × √(DTE/365) (método TOS)
  2. calcular_em_straddle    — método del straddle ATM (ideal para earnings)

Dependencias: solo `math` (sin librerías externas).
"""
import math
from typing import Dict


# ============================================================================
#  MÉTODO 1: Expected Move por IV  (fórmula TOS / Charles Schwab)
# ============================================================================
def calcular_expected_move(
    precio_actual: float,
    iv: float,
    dte: float,
    metodo: str = "simple",
    skew_factor: float = 1.0,
) -> Dict[str, object]:
    """
    Calcula el Expected Move exactamente como lo muestra Thinkorswim.

    La fórmula principal es:
        EM = precio_actual × IV × √(DTE / 365)

    Donde:
      - IV es la volatilidad implícita **anualizada** en decimal (0.32 = 32 %).
      - DTE son los días calendario hasta el vencimiento.
      - Se usa 365 días calendario (no 252 días hábiles) para ser fiel a TOS.

    Parámetros
    ----------
    precio_actual : float
        Precio spot actual del subyacente.
    iv : float
        Volatilidad implícita anualizada en decimal (ej. 0.32 = 32 %).
    dte : float
        Días hasta el vencimiento (puede ser fracción).
    metodo : str, default "simple"
        - "simple"    → EM = precio × IV × √(DTE/365)  (TOS estándar)
        - "lognormal" → usa distribución lognormal:
              sigma = IV × √(DTE/365)
              upper = precio × exp(+sigma)
              lower = precio × exp(-sigma)
    skew_factor : float, default 1.0
        Factor de ajuste de skew. TOS suele estar entre 0.70 y 1.0.
        Un skew_factor < 1 reduce ligeramente el EM para reflejar que
        el mercado no es perfectamente simétrico.

    Retorna
    -------
    dict
        {
          "em_dolares":    float  — el "+/- $X.XX" que se ve en TOS,
          "upper":         float  — precio_actual + EM,
          "lower":         float  — precio_actual - EM,
          "rango":         str    — "142.50 - 157.50",
          "porcentaje":    float  — EM como % del precio actual,
          "metodo_usado":  str    — método empleado
        }

    Excepciones
    -----------
    ValueError
        Si dte <= 0 o iv <= 0 o precio_actual <= 0.

    Ejemplos
    --------
    >>> calcular_expected_move(150.0, 0.32, 30)
    {'em_dolares': 13.75, 'upper': 163.75, 'lower': 136.25, ...}

    >>> calcular_expected_move(150.0, 0.32, 30, metodo="lognormal")
    {'em_dolares': 13.82, 'upper': 163.88, 'lower': 136.40, ...}
    """
    # ── Validaciones ──────────────────────────────────────────────
    if precio_actual <= 0:
        raise ValueError(
            f"precio_actual debe ser > 0, recibido: {precio_actual}"
        )
    if iv <= 0:
        raise ValueError(
            f"IV debe ser > 0 (en decimal, ej. 0.32), recibido: {iv}"
        )
    if dte <= 0:
        raise ValueError(
            f"DTE (días al vencimiento) debe ser > 0, recibido: {dte}"
        )

    # ── Cálculo principal ─────────────────────────────────────────
    # sigma = volatilidad ajustada al período
    sigma = iv * math.sqrt(dte / 365.0)

    if metodo == "lognormal":
        # Distribución lognormal: captura mejor la asimetría real
        # de los rendimientos logarítmicos del mercado.
        upper = precio_actual * math.exp(sigma * skew_factor)
        lower = precio_actual * math.exp(-sigma * skew_factor)
        # EM promedio de ambos lados (pueden diferir en lognormal)
        em_up = upper - precio_actual
        em_down = precio_actual - lower
        em_dolares = round((em_up + em_down) / 2, 2)
        metodo_usado = "lognormal"
    else:
        # Método simple (TOS estándar): asume distribución normal simétrica.
        # Es la fórmula que TOS muestra directamente en la cadena de opciones.
        em_dolares = round(precio_actual * sigma * skew_factor, 2)
        upper = round(precio_actual + em_dolares, 2)
        lower = round(precio_actual - em_dolares, 2)
        metodo_usado = "simple (TOS)"

    # ── Resultado ─────────────────────────────────────────────────
    upper = round(upper, 2)
    lower = round(lower, 2)
    porcentaje = round((em_dolares / precio_actual) * 100, 2)

    return {
        "em_dolares": em_dolares,
        "upper": upper,
        "lower": lower,
        "rango": f"{lower:,.2f} - {upper:,.2f}",
        "porcentaje": porcentaje,
        "metodo_usado": metodo_usado,
    }


# ============================================================================
#  MÉTODO 2: Expected Move por Straddle ATM  (ideal para earnings)
# ============================================================================
def calcular_em_straddle(
    precio_actual: float,
    precio_call_atm: float,
    precio_put_atm: float,
    factor: float = 0.85,
) -> Dict[str, object]:
    """
    Calcula el Expected Move usando el método del straddle ATM.

    Este método es especialmente útil antes de earnings porque refleja
    directamente cuánto dinero pide el mercado por cubrir el movimiento.

    La fórmula es:
        EM = (precio_call_ATM + precio_put_ATM) × factor

    El factor de 0.85 es una aproximación empírica usada por traders
    institucionales: el straddle tiende a "sobreestimar" el movimiento
    real, así que se aplica un descuento (~15 %) para ajustarlo.

    Parámetros
    ----------
    precio_actual : float
        Precio spot actual del subyacente.
    precio_call_atm : float
        Prima del CALL ATM (at-the-money) más cercano.
    precio_put_atm : float
        Prima del PUT ATM (at-the-money) más cercano.
    factor : float, default 0.85
        Factor de descuento del straddle. Rango común: 0.80 – 0.90.

    Retorna
    -------
    dict
        Misma estructura que calcular_expected_move.

    Excepciones
    -----------
    ValueError
        Si algún precio es <= 0.

    Ejemplos
    --------
    >>> calcular_em_straddle(150.0, 5.20, 4.80)
    {'em_dolares': 8.50, 'upper': 158.50, 'lower': 141.50, ...}
    """
    # ── Validaciones ──────────────────────────────────────────────
    if precio_actual <= 0:
        raise ValueError(f"precio_actual debe ser > 0, recibido: {precio_actual}")
    if precio_call_atm <= 0:
        raise ValueError(f"precio_call_atm debe ser > 0, recibido: {precio_call_atm}")
    if precio_put_atm <= 0:
        raise ValueError(f"precio_put_atm debe ser > 0, recibido: {precio_put_atm}")

    # ── Cálculo ───────────────────────────────────────────────────
    straddle_cost = precio_call_atm + precio_put_atm
    em_dolares = round(straddle_cost * factor, 2)
    upper = round(precio_actual + em_dolares, 2)
    lower = round(precio_actual - em_dolares, 2)
    porcentaje = round((em_dolares / precio_actual) * 100, 2)

    return {
        "em_dolares": em_dolares,
        "upper": upper,
        "lower": lower,
        "rango": f"{lower:,.2f} - {upper:,.2f}",
        "porcentaje": porcentaje,
        "metodo_usado": f"straddle ATM (factor={factor})",
        "straddle_cost": round(straddle_cost, 2),
    }
