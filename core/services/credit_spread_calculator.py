# -*- coding: utf-8 -*-
"""
Public BSM calculation API for credit spread analysis.

Thin public facade over CoreOptionGreeks and the scanner's precision helpers.
Intended for UI layers and other services that need BSM metrics without
importing the full scanner internals.

All functions are pure (no I/O, no side-effects) and safe to call from any layer.
"""
from __future__ import annotations

from scipy.stats import norm as _norm

from config.constants import RISK_FREE_RATE, DAYS_PER_YEAR
from core.option_greeks import (
    OptionGreeks,
    calculate_probability_of_touch_precise,
)


# ──────────────────────────────────────────────────────────────────────────────
#  Delta / Greeks
# ──────────────────────────────────────────────────────────────────────────────

def bsm_delta(
    spot: float,
    strike: float,
    dte: int,
    iv: float,
    option_type: str = "put",
) -> float:
    """BSM delta for a single option leg.

    Args:
        spot:        Current underlying price.
        strike:      Option strike price.
        dte:         Days to expiration.
        iv:          Implied volatility (decimal, e.g. 0.25 = 25 %).
        option_type: ``"put"`` or ``"call"``.

    Returns:
        Delta as a float (negative for puts, positive for calls).
    """
    T = max(dte, 1) / DAYS_PER_YEAR
    sigma = iv if iv > 0.01 else 0.25
    try:
        greeks = OptionGreeks(S=spot, K=strike, T=T, r=RISK_FREE_RATE, sigma=sigma)
        return float(greeks.delta().get(option_type, 0.0))
    except Exception:
        return 0.0


def bsm_greeks(
    spot: float,
    strike: float,
    dte: int,
    iv: float,
    option_type: str = "put",
) -> dict[str, float]:
    """BSM gamma and theta for a single option leg.

    Args:
        spot, strike, dte, iv, option_type: same as :func:`bsm_delta`.

    Returns:
        Dict with keys ``"gamma"`` and ``"theta"`` (per-day).
    """
    T = max(dte, 1) / DAYS_PER_YEAR
    sigma = iv if iv > 0.01 else 0.25
    try:
        g = OptionGreeks(S=spot, K=strike, T=T, r=RISK_FREE_RATE, sigma=sigma)
        return {
            "gamma": g.gamma(),
            "theta": g.theta().get(option_type, 0.0),
        }
    except Exception:
        return {"gamma": 0.0, "theta": 0.0}


# ──────────────────────────────────────────────────────────────────────────────
#  Probability of Profit
# ──────────────────────────────────────────────────────────────────────────────

def pop_from_delta(delta: float) -> float:
    """POP estimate = 1 − |delta| (tastytrade approximation).

    Quick heuristic; prefer :func:`pop_from_breakeven` for precision.
    """
    return round(1.0 - abs(delta), 4)


def pop_from_breakeven(
    spot: float,
    breakeven: float,
    dte: int,
    iv: float,
    option_type: str = "put",
) -> float:
    """POP based on the spread's real breakeven (BSM with K = breakeven).

    Bull Put:  POP = P(S_T > breakeven) = N(d2),  K = strike_sold − credit
    Bear Call: POP = P(S_T < breakeven) = N(−d2), K = strike_sold + credit

    More precise than 1−|Δ| because it accounts for the actual premium collected.

    Returns:
        Probability as a decimal (0.0 – 1.0).
    """
    T = max(dte, 1) / DAYS_PER_YEAR
    sigma = iv if iv > 0.01 else 0.25
    try:
        g = OptionGreeks(S=spot, K=breakeven, T=T, r=RISK_FREE_RATE, sigma=sigma)
        d2 = g._d2
        if option_type == "put":
            return float(_norm.cdf(d2))   # P(S_T > breakeven)
        return float(_norm.cdf(-d2))      # P(S_T < breakeven)
    except Exception:
        return 0.70


# ──────────────────────────────────────────────────────────────────────────────
#  Probability of Touch
# ──────────────────────────────────────────────────────────────────────────────

def probability_of_touch(
    spot: float,
    strike: float,
    dte: int,
    iv: float,
    option_type: str = "put",
    skew_adjust: float = 0.0,
    r: float = RISK_FREE_RATE,
) -> float:
    """Probability of Touch (BSM first-passage barrier) with skew adjustment.

    Delegates to :func:`~core.option_greeks.calculate_probability_of_touch_precise`
    which uses the exact first-passage-time formula rather than the 2×|Δ|
    tastytrade approximation.

    Args:
        spot:         Current underlying price.
        strike:       Sold strike price.
        dte:          Days to expiration.
        iv:           Implied volatility of the short strike (decimal).
        option_type:  ``"put"`` or ``"call"``.
        skew_adjust:  Additional skew penalty in pp (0.0 – 5.0).
        r:            Risk-free rate (decimal). Defaults to :data:`RISK_FREE_RATE`.

    Returns:
        Probability of touch in percent (0.0 – 99.0).
    """
    return calculate_probability_of_touch_precise(
        spot=spot,
        strike=strike,
        dte=dte,
        iv_short=iv,
        option_type=option_type,
        skew_adjust=skew_adjust,
        r=r,
    )


# ──────────────────────────────────────────────────────────────────────────────
#  Expected Value
# ──────────────────────────────────────────────────────────────────────────────

def ev_adjusted(credit: float, risk: float, pop_breakeven: float) -> float:
    """Expected value adjusted for the spread's real breakeven probability.

    EV = credit × P(win) − (risk − credit) × P(loss)
    Returned as a percentage of max risk.

    Args:
        credit:        Net credit received (dollars per spread).
        risk:          Max risk = width − credit (dollars per spread).
        pop_breakeven: Probability of profit at breakeven (decimal 0–1).

    Returns:
        EV as a percentage of max risk (e.g. +8.5 means +8.5 % edge).
    """
    if risk <= 0:
        return 0.0
    ev = credit * pop_breakeven - (risk - credit) * (1.0 - pop_breakeven)
    return round(ev / risk * 100.0, 2)


# ──────────────────────────────────────────────────────────────────────────────
#  Utility helpers
# ──────────────────────────────────────────────────────────────────────────────

def strike_distance_pct(spot: float, strike: float) -> float:
    """Percentage distance between the underlying price and the sold strike."""
    if spot <= 0:
        return 0.0
    return round(abs(spot - strike) / spot * 100, 2)


def bid_ask_spread(bid: float, ask: float) -> float:
    """Raw bid-ask spread in dollars."""
    if ask > 0 and bid >= 0:
        return round(ask - bid, 2)
    return 0.0


def bid_ask_pct(bid: float, ask: float) -> float:
    """Bid-ask spread as a percentage of mid price.

    Returns 0.0 if prices are invalid.
    """
    if ask <= 0 or bid < 0:
        return 0.0
    mid = (bid + ask) / 2.0
    if mid <= 0:
        return 0.0
    return round((ask - bid) / mid * 100.0, 2)
