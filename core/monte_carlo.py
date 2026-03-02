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
