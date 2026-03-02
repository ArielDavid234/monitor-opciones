# -*- coding: utf-8 -*-
"""
Monte Carlo — Simulación de precios futuros con Geometric Brownian Motion.

Genera N trayectorias de precio basadas en la volatilidad implícita actual
y el drift estimado. Calcula intervalos de confianza y probabilidades de
que el precio termine arriba/abajo de cierto nivel.
"""
import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Parámetros por defecto  
DEFAULT_NUM_SIMS = 1_000
DEFAULT_DAYS = 30
TRADING_DAYS_YEAR = 252


def simular_monte_carlo(
    spot_price: float,
    iv: float,
    days: int = DEFAULT_DAYS,
    num_sims: int = DEFAULT_NUM_SIMS,
    drift: float = 0.0,
    seed: Optional[int] = 42,
) -> dict:
    """Ejecuta simulación Monte Carlo de precio usando GBM.

    Modelo: dS = μ·S·dt + σ·S·dW
    Discretizado: S(t+1) = S(t) × exp((μ - σ²/2)·dt + σ·√dt·Z)

    Args:
        spot_price: Precio actual del activo.
        iv: Volatilidad implícita anualizada en decimal (e.g. 0.25 = 25%).
        days: Número de días a simular.
        num_sims: Número de simulaciones.
        drift: Drift anualizado (e.g. rendimiento esperado del mercado).
                Si es 0, usa el modelo risk-neutral.
        seed: Semilla para reproducibilidad. None para aleatorio.

    Returns:
        dict con:
        - paths: ndarray de forma (num_sims, days+1) con todas las trayectorias
        - final_prices: ndarray de los precios finales
        - mean_path: ndarray con la trayectoria promedio
        - percentiles: dict con p5, p10, p25, p50, p75, p90, p95
        - prob_above: float — probabilidad de terminar arriba del spot
        - prob_below: float — probabilidad de terminar abajo del spot
        - expected_price: float — precio esperado (media)
        - max_price: float — precio máximo simulado
        - min_price: float — precio mínimo simulado
        - iv_used: float — IV usada
        - days: int — días simulados
    """
    if spot_price <= 0 or iv <= 0 or days <= 0:
        logger.warning(f"Parámetros inválidos: spot={spot_price}, iv={iv}, days={days}")
        return _empty_result(spot_price, iv, days)

    if seed is not None:
        rng = np.random.default_rng(seed)
    else:
        rng = np.random.default_rng()

    dt = 1 / TRADING_DAYS_YEAR
    sigma = iv
    mu = drift

    # Generar caminos de precios
    # Z ~ N(0,1) de forma (num_sims, days)
    Z = rng.standard_normal((num_sims, days))

    # Log-returns diarios
    log_returns = (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * Z

    # Acumular log-returns y convertir a precios
    log_price_paths = np.zeros((num_sims, days + 1))
    log_price_paths[:, 0] = np.log(spot_price)
    log_price_paths[:, 1:] = np.log(spot_price) + np.cumsum(log_returns, axis=1)
    paths = np.exp(log_price_paths)

    final_prices = paths[:, -1]

    # Estadísticas
    percentile_values = {
        "p5": float(np.percentile(final_prices, 5)),
        "p10": float(np.percentile(final_prices, 10)),
        "p25": float(np.percentile(final_prices, 25)),
        "p50": float(np.percentile(final_prices, 50)),
        "p75": float(np.percentile(final_prices, 75)),
        "p90": float(np.percentile(final_prices, 90)),
        "p95": float(np.percentile(final_prices, 95)),
    }

    result = {
        "paths": paths,
        "final_prices": final_prices,
        "mean_path": paths.mean(axis=0),
        "percentiles": percentile_values,
        "prob_above": float((final_prices > spot_price).mean() * 100),
        "prob_below": float((final_prices < spot_price).mean() * 100),
        "expected_price": float(final_prices.mean()),
        "max_price": float(final_prices.max()),
        "min_price": float(final_prices.min()),
        "iv_used": iv,
        "days": days,
    }

    logger.info(
        f"Monte Carlo: {num_sims} sims, {days}d, IV={iv*100:.1f}%, "
        f"E[S]=${result['expected_price']:,.2f}, "
        f"P(arriba)={result['prob_above']:.1f}%, "
        f"[P5=${percentile_values['p5']:,.2f}, P95=${percentile_values['p95']:,.2f}]"
    )

    return result


def _empty_result(spot: float, iv: float, days: int) -> dict:
    """Resultado vacío para parámetros inválidos."""
    return {
        "paths": np.array([[spot]]),
        "final_prices": np.array([spot]),
        "mean_path": np.array([spot]),
        "percentiles": {f"p{p}": spot for p in [5, 10, 25, 50, 75, 90, 95]},
        "prob_above": 50.0,
        "prob_below": 50.0,
        "expected_price": spot,
        "max_price": spot,
        "min_price": spot,
        "iv_used": iv,
        "days": days,
    }


# ============================================================================
#        MONTE CARLO — VALORACIÓN DE OPCIONES CON RIESGO AJUSTADO
# ============================================================================

def monte_carlo_option_pricing(
    S0: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str = "call",
    n_sims: int = 10_000,
    n_steps: int = 252,
    seed: int = 42,
) -> dict:
    """Monte Carlo para precio y riesgo ajustado de opción europea.

    Simula N trayectorias del subyacente usando GBM risk-neutral
    (drift = r) y calcula el payoff descontado de la opción.

    **Uso financiero:**
    - mc_price: valor teórico de la opción según MC (comparar con prima de mercado).
    - itm_probability: % de escenarios donde la opción termina ITM.
    - expected_payoff: payoff promedio sin descontar — si > prima pagada → edge positivo.
    - payoff_distribution: histograma para evaluar asimetría del riesgo.
    - max_drawdown_pct: peor caída del subyacente en cualquier path (riesgo extremo).

    Args:
        S0: Precio spot actual del subyacente.
        K: Strike de la opción.
        T: Tiempo al vencimiento en años (e.g. 30/365 = 0.082).
        r: Tasa libre de riesgo anualizada (e.g. 0.045).
        sigma: Volatilidad implícita anualizada en decimal (e.g. 0.25 = 25%).
        option_type: "call" o "put".
        n_sims: Número de simulaciones (default 10,000).
        n_steps: Pasos temporales (default 252 = días de trading por año).
        seed: Semilla para reproducibilidad.

    Returns:
        dict con métricas, payoffs, paths, parámetros e interpretación.
    """
    # ── Validación ───────────────────────────────────────────────
    otype = option_type.strip().lower()
    if otype not in ("call", "put"):
        return {"error": f"option_type inválido: '{option_type}'. Usa 'call' o 'put'."}

    if S0 <= 0 or K <= 0 or T <= 0:
        return {"error": f"Parámetros inválidos: S0={S0}, K={K}, T={T}"}

    if sigma <= 0:
        sigma = 0.20  # fallback conservador
        logger.warning(f"sigma ≤ 0, usando fallback 20%")

    # ── Simulación GBM (risk-neutral: drift = r) ────────────────
    rng = np.random.default_rng(seed)
    dt = T / n_steps

    Z = rng.standard_normal((n_sims, n_steps))
    log_returns = (r - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * Z

    log_paths = np.zeros((n_sims, n_steps + 1))
    log_paths[:, 0] = np.log(S0)
    log_paths[:, 1:] = np.log(S0) + np.cumsum(log_returns, axis=1)
    paths = np.exp(log_paths)

    final_prices = paths[:, -1]

    # ── Payoffs al vencimiento ───────────────────────────────────
    if otype == "call":
        payoffs = np.maximum(final_prices - K, 0)
    else:
        payoffs = np.maximum(K - final_prices, 0)

    # ── Precio MC (payoff medio descontado) ──────────────────────
    discount = np.exp(-r * T)
    mc_price = float(discount * np.mean(payoffs))

    # ── Métricas de riesgo ───────────────────────────────────────
    itm_mask = payoffs > 0
    itm_prob = float(np.mean(itm_mask) * 100)
    expected_payoff = float(np.mean(payoffs))
    median_payoff = float(np.median(payoffs))
    std_payoff = float(np.std(payoffs))

    # Percentiles del payoff
    payoff_pctls = {
        "p5": float(np.percentile(payoffs, 5)),
        "p25": float(np.percentile(payoffs, 25)),
        "p50": float(np.percentile(payoffs, 50)),
        "p75": float(np.percentile(payoffs, 75)),
        "p95": float(np.percentile(payoffs, 95)),
    }

    # Max drawdown del subyacente (peor caída intra-path)
    running_max = np.maximum.accumulate(paths, axis=1)
    drawdowns = (paths - running_max) / running_max
    max_dd = float(np.min(drawdowns)) * 100  # en %

    # Valor en riesgo (VaR) del payoff
    var_95 = float(np.percentile(payoffs, 5))  # P5 = VaR 95%
    cvar_95 = float(np.mean(payoffs[payoffs <= var_95])) if np.any(payoffs <= var_95) else 0.0

    # Break-even: precio del subyacente donde payoff = prima MC
    if otype == "call":
        breakeven = K + mc_price
    else:
        breakeven = K - mc_price

    # ── Interpretación financiera ────────────────────────────────
    moneyness = ((S0 - K) / K * 100) if otype == "call" else ((K - S0) / K * 100)

    if itm_prob >= 60:
        prob_label = "**alta probabilidad ITM**"
        prob_advice = "Escenario favorable para comprar"
    elif itm_prob >= 40:
        prob_label = "**probabilidad moderada ITM**"
        prob_advice = "Riesgo/beneficio equilibrado"
    else:
        prob_label = "**baja probabilidad ITM**"
        prob_advice = "Alto riesgo — prima probablemente se pierde"

    tipo_label = "CALL" if otype == "call" else "PUT"
    interpretation = (
        f"🎲 **{tipo_label} ${K:,.1f}** — Precio MC: **${mc_price:.2f}** | "
        f"Prob ITM: **{itm_prob:.1f}%** ({prob_label})\n\n"
        f"Payoff esperado: ${expected_payoff:.2f} ± ${std_payoff:.2f} | "
        f"Break-even: ${breakeven:,.2f}\n\n"
        f"💡 {prob_advice}. "
    )

    if mc_price > 0 and expected_payoff / mc_price > 1.5:
        interpretation += "Edge positivo: payoff esperado supera la prima teórica."
    elif itm_prob < 30:
        interpretation += "Considerar vender esta opción en lugar de comprarla (cobrar prima)."

    # ── Sample de paths para visualización ───────────────────────
    n_sample = min(200, n_sims)
    sample_idx = np.linspace(0, n_sims - 1, n_sample, dtype=int)

    result = {
        "mc_price": round(mc_price, 2),
        "itm_probability": round(itm_prob, 1),
        "expected_payoff": round(expected_payoff, 2),
        "median_payoff": round(median_payoff, 2),
        "std_payoff": round(std_payoff, 2),
        "payoff_percentiles": {k: round(v, 2) for k, v in payoff_pctls.items()},
        "max_drawdown_pct": round(max_dd, 2),
        "var_95": round(var_95, 2),
        "cvar_95": round(cvar_95, 2),
        "breakeven": round(breakeven, 2),
        "payoffs": payoffs,
        "paths_sample": paths[sample_idx],
        "mean_path": paths.mean(axis=0),
        "final_prices": final_prices,
        "params": {
            "S0": S0, "K": K, "T": T, "r": r, "sigma": sigma,
            "option_type": otype, "n_sims": n_sims, "n_steps": n_steps,
        },
        "interpretation": interpretation,
    }

    logger.info(
        f"MC Option: {otype.upper()} K=${K:.1f}, S0=${S0:.2f}, "
        f"σ={sigma*100:.1f}%, T={T:.3f}y → "
        f"Price=${mc_price:.2f}, P(ITM)={itm_prob:.1f}%, "
        f"E[payoff]=${expected_payoff:.2f}"
    )

    return result


def calcular_expected_move_mc(
    spot_price: float,
    iv: float,
    days: int = 30,
    confidence: float = 0.68,
    num_sims: int = 2_000,
) -> dict:
    """Calcula expected move con Monte Carlo.

    Args:
        spot_price: Precio actual.
        iv: IV anualizada en decimal.
        days: Horizonte temporal.
        confidence: Nivel de confianza (0.68 = 1σ, 0.95 = 2σ).
        num_sims: Número de simulaciones.

    Returns:
        dict: upper, lower, range, range_pct
    """
    mc = simular_monte_carlo(spot_price, iv, days, num_sims, seed=42)
    finals = mc["final_prices"]

    lower_pct = (1 - confidence) / 2 * 100
    upper_pct = (1 - (1 - confidence) / 2) * 100

    lower = float(np.percentile(finals, lower_pct))
    upper = float(np.percentile(finals, upper_pct))

    return {
        "upper": round(upper, 2),
        "lower": round(lower, 2),
        "range": round(upper - lower, 2),
        "range_pct": round((upper - lower) / spot_price * 100, 2),
        "confidence": confidence,
        "days": days,
    }
