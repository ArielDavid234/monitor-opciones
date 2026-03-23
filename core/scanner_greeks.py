"""Funciones de calculo de greeks extraidas de core.scanner."""

from __future__ import annotations

import numpy as np
import pandas as pd

try:
    import scipy.stats  # noqa: F401

    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False


def _safe_num(value, default=0):
    """Retorna el valor si no es NaN/None, o el default."""
    return value if pd.notna(value) else default


def _calcular_greeks(S, K, T, r_rate, sigma, tipo="call"):
    """Calcula Delta, Gamma, Theta y Rho usando OptionGreeks (BSM).
    Retorna dict {"Delta": .., "Gamma": .., "Theta": .., "Rho": ..} o Nones.
    """
    if not _HAS_SCIPY:
        return {"Delta": None, "Gamma": None, "Theta": None, "Rho": None}
    try:
        if S <= 0 or K <= 0 or T <= 0 or sigma <= 0:
            return {"Delta": None, "Gamma": None, "Theta": None, "Rho": None}

        d1 = (np.log(S / K) + (r_rate + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        if tipo.lower() == "call":
            delta = scipy.stats.norm.cdf(d1)
            theta = (
                -(S * scipy.stats.norm.pdf(d1) * sigma) / (2 * np.sqrt(T))
                - r_rate * K * np.exp(-r_rate * T) * scipy.stats.norm.cdf(d2)
            ) / 365
            rho = (K * T * np.exp(-r_rate * T) * scipy.stats.norm.cdf(d2)) / 100
        else:
            delta = scipy.stats.norm.cdf(d1) - 1
            theta = (
                -(S * scipy.stats.norm.pdf(d1) * sigma) / (2 * np.sqrt(T))
                + r_rate * K * np.exp(-r_rate * T) * scipy.stats.norm.cdf(-d2)
            ) / 365
            rho = (-K * T * np.exp(-r_rate * T) * scipy.stats.norm.cdf(-d2)) / 100

        gamma = scipy.stats.norm.pdf(d1) / (S * sigma * np.sqrt(T))
        return {"Delta": delta, "Gamma": gamma, "Theta": theta, "Rho": rho}
    except Exception:
        return {"Delta": None, "Gamma": None, "Theta": None, "Rho": None}


def _calcular_greeks_batch(S, K_arr, T_arr, r_rate, sigma_arr, tipo_arr):
    """Versión vectorizada para arrays. Devuelve dict de arrays Delta/Gamma/Theta/Rho."""
    if not _HAS_SCIPY:
        n = len(K_arr)
        nan = np.full(n, np.nan)
        return {"Delta": nan, "Gamma": nan, "Theta": nan, "Rho": nan}

    K = np.asarray(K_arr, dtype=float)
    T = np.asarray(T_arr, dtype=float)
    sigma = np.asarray(sigma_arr, dtype=float)
    tipos = np.asarray(tipo_arr, dtype=object)

    n = len(K)
    nan = np.full(n, np.nan)
    valid = (S > 0) & (K > 0) & (T > 0) & (sigma > 0)
    if not np.any(valid):
        return {"Delta": nan, "Gamma": nan, "Theta": nan, "Rho": nan}

    d1 = np.full(n, np.nan)
    d2 = np.full(n, np.nan)
    d1[valid] = (
        (np.log(S / K[valid]) + (r_rate + 0.5 * sigma[valid] ** 2) * T[valid])
        / (sigma[valid] * np.sqrt(T[valid]))
    )
    d2[valid] = d1[valid] - sigma[valid] * np.sqrt(T[valid])

    delta = np.full(n, np.nan)
    gamma = np.full(n, np.nan)
    theta = np.full(n, np.nan)
    rho = np.full(n, np.nan)

    calls = valid & np.char.startswith(np.char.lower(tipos.astype(str)), "call")
    puts = valid & ~calls

    if np.any(calls):
        d1c = d1[calls]
        d2c = d2[calls]
        Tc = T[calls]
        Kc = K[calls]
        sigc = sigma[calls]

        delta[calls] = scipy.stats.norm.cdf(d1c)
        theta[calls] = (
            -(S * scipy.stats.norm.pdf(d1c) * sigc) / (2 * np.sqrt(Tc))
            - r_rate * Kc * np.exp(-r_rate * Tc) * scipy.stats.norm.cdf(d2c)
        ) / 365
        rho[calls] = (Kc * Tc * np.exp(-r_rate * Tc) * scipy.stats.norm.cdf(d2c)) / 100
        gamma[calls] = scipy.stats.norm.pdf(d1c) / (S * sigc * np.sqrt(Tc))

    if np.any(puts):
        d1p = d1[puts]
        d2p = d2[puts]
        Tp = T[puts]
        Kp = K[puts]
        sigp = sigma[puts]

        delta[puts] = scipy.stats.norm.cdf(d1p) - 1
        theta[puts] = (
            -(S * scipy.stats.norm.pdf(d1p) * sigp) / (2 * np.sqrt(Tp))
            + r_rate * Kp * np.exp(-r_rate * Tp) * scipy.stats.norm.cdf(-d2p)
        ) / 365
        rho[puts] = (-Kp * Tp * np.exp(-r_rate * Tp) * scipy.stats.norm.cdf(-d2p)) / 100
        gamma[puts] = scipy.stats.norm.pdf(d1p) / (S * sigp * np.sqrt(Tp))

    return {"Delta": delta, "Gamma": gamma, "Theta": theta, "Rho": rho}


def _clasificar_lado(ask, bid, ultimo):
    """Clasifica lado de ejecución: Ask/Bid/Mid/N/A."""
    ask = _safe_num(ask)
    bid = _safe_num(bid)
    ultimo = _safe_num(ultimo)

    if ask == 0 and bid == 0:
        return "N/A"
    if ask > 0 and ultimo >= ask:
        return "Ask"
    if bid > 0 and ultimo <= bid:
        return "Bid"
    if bid > 0 and ask > 0 and bid < ultimo < ask:
        return "Mid"
    return "N/A"
