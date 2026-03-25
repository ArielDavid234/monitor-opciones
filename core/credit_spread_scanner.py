# -*- coding: utf-8 -*-
"""
Credit Spread Scanner — core scanning pipeline.

Builds Bull Put and Bear Call spreads, scans tickers, and orchestrates
multi-ticker credit-spread scanning.
"""
from __future__ import annotations

import logging
import numpy as np
import pandas as pd
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore[assignment]

from config.constants import (
    RISK_FREE_RATE, DAYS_PER_YEAR,
    CS_WHITELIST, CS_MIN_CHAIN_OI, CS_MIN_IV_RANK,
    CS_DTE_MIN, CS_DTE_MAX, CS_DELTA_MIN, CS_DELTA_MAX,
    CS_ALLOWED_WIDTHS, CS_MIN_CREDIT_PCT, CS_MIN_DIST_PCT,
    CS_MIN_SOLD_OI, CS_MIN_SOLD_VOL, CS_MAX_BID_ASK_PCT,
    OPP_SCORE_MIN_SHOW,
)
from core.option_greeks import OptionGreeks, quick_probability_of_touch, calculate_probability_of_touch_precise
from core.backtester import compute_ev_real_adjusted, _surface_edge, compute_optimized_score
from core.scanner import (
    _cached_options_dates, _cached_option_chain, _cached_history,
    obtener_precio_actual, _safe_num,
)
from core.credit_spread_math import (
    _dte_from_expiry, _bsm_delta, _bsm_greeks,
    _pop_from_delta, _pop_from_breakeven,
    calculate_probability_of_touch, _pot_approx_2delta,
    _bid_ask_spread, _strike_distance_pct,
    _avg_daily_volume, _avg_chain_oi,
    _passes_underlying_filter, _passes_bid_ask_filter,
)
from core.credit_spread_scoring import (
    compute_income_score, compute_opportunity_score, opportunity_score_breakdown,
)
from core.credit_spread_indicators import (
    compute_iv_rank_percentile, compute_trend,
)
from core.credit_spread_alerts import _check_10_rules, generate_alerts

logger = logging.getLogger(__name__)

#  Construcción de spreads para una fecha de expiración
# ────────────────────────────────────────────────────────────────────────────

def _build_spreads_for_expiry(
    ticker: str,
    spot: float,
    exp_date: str,
    min_pop: float,
    min_credit: float,
    ticker_meta: dict | None = None,
    allowed_type: str | None = None,
    strict: bool = False,
    strict_rules: dict | None = None,
) -> list[dict]:
    """Genera Bull Put Spreads y Bear Call Spreads para una expiración.

    Parameters
    ----------
    allowed_type : str | None
        Si se pasa "Bull Put" o "Bear Call", solo genera ese tipo (filtro 5).
    strict : bool
        Si True, aplica los 9 filtros obligatorios del pipeline.
    strict_rules : dict | None
        Reglas individuales activadas. Tiene prioridad sobre ``strict``.
    """
    _sr = strict_rules or {}
    dte = _dte_from_expiry(exp_date)
    if dte <= 0:
        return []

    # Filtro 3 — DTE estricto (solo en modo strict)
    if _sr.get("r3_dte", strict) and (dte < CS_DTE_MIN or dte > CS_DTE_MAX):
        return []

    try:
        chain = _cached_option_chain(ticker, exp_date)
    except Exception as exc:
        logger.warning("Error obteniendo cadena %s %s: %s", ticker, exp_date, exc)
        return []

    puts: pd.DataFrame = chain.get("puts", pd.DataFrame())
    calls: pd.DataFrame = chain.get("calls", pd.DataFrame())

    results: list[dict] = []

    # ── Bull Put Spreads ─────────────────────────────────────────────────
    if (allowed_type is None or allowed_type == "Bull Put") and not puts.empty and len(puts) >= 2:
        otm_puts = puts[
            (puts["strike"] < spot) &
            (puts["bid"].fillna(0) > 0)
        ].sort_values("strike", ascending=False).reset_index(drop=True)

        # ATM IV de puts para detección de skew — se calcula una vez por expiración
        _atm_iv_put = 0.0
        if "impliedVolatility" in puts.columns and not puts.empty:
            try:
                _atm_idx_put = (puts["strike"] - spot).abs().idxmin()
                _raw_atm_put = float(_safe_num(puts.at[_atm_idx_put, "impliedVolatility"], 0))
                _atm_iv_put = _raw_atm_put if _raw_atm_put > 0.01 else 0.0
            except Exception:
                _atm_iv_put = 0.0

        for i in range(len(otm_puts)):
            sold = otm_puts.iloc[i]
            sold_strike = float(sold["strike"])
            sold_bid = float(_safe_num(sold.get("bid", 0)))
            sold_ask = float(_safe_num(sold.get("ask", 0)))
            sold_iv = float(_safe_num(sold.get("impliedVolatility", 0), 0))
            sold_vol = int(_safe_num(sold.get("volume", 0)))
            sold_oi = int(_safe_num(sold.get("openInterest", 0)))

            # Delta preciso vía BSM
            sold_delta = _bsm_delta(spot, sold_strike, dte, sold_iv, "put")

            # Skew adjust: IV OTM puts > IV ATM → cola más pesada → PoT real mayor
            _skew_adj = 0.0
            if _atm_iv_put > 0.01 and sold_iv > _atm_iv_put:
                # Regla: cada 5pp de prima de IV sobre ATM → +1pp de PoT (máx 5pp)
                _skew_pct = (sold_iv - _atm_iv_put) / _atm_iv_put * 100.0
                _skew_adj = round(min(_skew_pct * 0.2, 5.0), 2)

            # Filtro 4 — Delta del short strike (strict)
            if _sr.get("r4_delta", strict):
                abs_d = abs(sold_delta)
                if abs_d < CS_DELTA_MIN or abs_d > CS_DELTA_MAX:
                    continue

            pop = _pop_from_delta(sold_delta)
            if pop < min_pop:
                continue

            # Filtro 8 — Distancia del strike (strict)
            dist_pct = _strike_distance_pct(spot, sold_strike)
            if _sr.get("r8_distance", strict) and dist_pct < CS_MIN_DIST_PCT:
                continue

            # Filtro 9a/9b — Liquidez del contrato vendido (strict)
            if _sr.get("r9_liquidity", strict) and (sold_oi < CS_MIN_SOLD_OI or sold_vol < CS_MIN_SOLD_VOL):
                continue

            # Filtro 9c — Bid-Ask (strict)
            if _sr.get("r9_liquidity", strict) and not _passes_bid_ask_filter(sold_bid, sold_ask):
                continue

            # Build a strike→row lookup for fast width matching
            _put_strikes = {float(r["strike"]): r for _, r in otm_puts.iterrows()}

            # In strict mode, only try allowed widths; otherwise try next 5 strikes
            if _sr.get("r6_width", strict):
                _target_widths = CS_ALLOWED_WIDTHS
            else:
                _target_widths = None  # fallback: iterate consecutive

            _bought_candidates: list[tuple[float, pd.Series]] = []
            if _target_widths:
                for w in _target_widths:
                    target_k = round(sold_strike - w, 2)
                    if target_k in _put_strikes:
                        _bought_candidates.append((target_k, _put_strikes[target_k]))
            else:
                for j in range(i + 1, min(i + 8, len(otm_puts))):
                    _b = otm_puts.iloc[j]
                    _bought_candidates.append((float(_b["strike"]), _b))

            for bought_strike, bought in _bought_candidates:
                bought_ask = float(_safe_num(bought.get("ask", 0)))

                if bought_ask <= 0:
                    continue

                # Mid-price credit: (bid+ask)/2 del vendido − (bid+ask)/2 del comprado
                # Las plataformas oficiales (TastyTrade, ToS) muestran el mid-price.
                _bought_bid_bp = float(_safe_num(bought.get("bid", 0)))
                _sold_mid_bp = (sold_bid + sold_ask) / 2.0 if sold_ask > 0 else sold_bid
                _bought_mid_bp = (_bought_bid_bp + bought_ask) / 2.0 if bought_ask > 0 else bought_ask
                credit = round(_sold_mid_bp - _bought_mid_bp, 2)
                if credit < min_credit:
                    continue

                width = round(sold_strike - bought_strike, 2)
                if width <= 0:
                    continue

                # Filtro 6 — Ancho del spread (strict)
                if _sr.get("r6_width", strict):
                    width_int = int(round(width))
                    if width_int not in CS_ALLOWED_WIDTHS:
                        continue

                # Filtro 7 — Crédito mínimo % del ancho (strict)
                if _sr.get("r7_credit_pct", strict) and credit < width * CS_MIN_CREDIT_PCT:
                    continue

                max_risk = round(width - credit, 2)
                if max_risk <= 0:
                    continue

                retorno_pct = round((credit / max_risk) * 100, 2)
                bought_vol = int(_safe_num(bought.get("volume", 0)))
                bought_oi = int(_safe_num(bought.get("openInterest", 0)))

                # ── Métricas Fase 1: PoT, Delta Comprado, Delta Neto ─────
                bought_iv = float(_safe_num(bought.get("impliedVolatility", sold_iv)) or sold_iv)
                bought_delta = _bsm_delta(spot, bought_strike, dte, bought_iv, "put")

                # PoT: BSM first-passage barrier + ajuste por skew de IV del strike
                pot_short = calculate_probability_of_touch_precise(
                    spot=spot, strike=sold_strike, dte=dte,
                    iv_short=sold_iv, option_type="put",
                    skew_adjust=_skew_adj, r=RISK_FREE_RATE,
                )
                pot_approx = _pot_approx_2delta(sold_delta)

                # Delta Neto: para Bull Put (short higher put, long lower put),
                # ambos deltas son negativos.  El spread neto es bullish (positivo).
                # Δ_spread = Δ_short + Δ_long (short = vendido, invertimos signo)
                #          = -Δ_short_put + Δ_long_put
                delta_neto = round(-sold_delta + bought_delta, 4)

                # POP basado en breakeven real del spread
                breakeven = round(sold_strike - credit, 2)
                pop_be = _pop_from_breakeven(spot, breakeven, dte, sold_iv, "put")
                pop = _pop_from_delta(sold_delta)  # mantener como referencia

                # ── Métricas Fase 2: Gamma, Theta, Liquidez ───────────────
                _g_sold = _bsm_greeks(spot, sold_strike, dte, sold_iv, "put")
                _g_bought = _bsm_greeks(spot, bought_strike, dte, bought_iv, "put")
                # Vendemos el short, compramos el long → gamma neto = -gamma_sold + gamma_bought
                gamma_neto = round(_g_bought["gamma"] - _g_sold["gamma"], 6)
                # Theta neto: short nos beneficia (+), long nos cuesta (-)
                theta_neto = round(-_g_sold["theta"] + _g_bought["theta"], 6)
                # Decay: usar mínimo entre 7 y DTE real para evitar proyectar
                # más días de los que quedan hasta el vencimiento.
                _decay_days = min(7, max(1, dte))
                decay_7d = round(theta_neto * _decay_days, 2)
                # Liquidity Score del short leg (0-100)
                _ba_mid = (sold_bid + sold_ask) / 2 if sold_ask > 0 else 0.01
                _ba_tight = (sold_ask - sold_bid) / _ba_mid if _ba_mid > 0 else 1.0
                liq_score = (
                    (40 if sold_oi > 1000 else sold_oi / 1000 * 40)
                    + (30 if sold_vol > 200 else sold_vol / 200 * 30)
                    + (30 if _ba_tight < 0.10 else max(0, 30 * (1 - _ba_tight)))
                )
                liq_score = round(min(100, max(0, liq_score)), 1)

                # ── Fase 3: EV Real Adjusted + Surface Edge ───────────────
                ev_real_adj = compute_ev_real_adjusted(
                    spot, sold_strike, dte, sold_iv, credit, max_risk, "put",
                    breakeven=breakeven,
                )
                surface_edge = _surface_edge(
                    spot, sold_strike, dte, sold_iv, round(pop * 100, 1), "put",
                )

                row = {
                    "Ticker": ticker,
                    "Tipo": "Bull Put",
                    "Spot": round(spot, 2),
                    "Strike Vendido": sold_strike,
                    "Strike Comprado": bought_strike,
                    "DTE": dte,
                    "Expiración": exp_date,
                    "Delta Vendido": round(sold_delta, 4),
                    "Delta Comprado": round(bought_delta, 4),
                    "Delta Neto": delta_neto,
                    "PoT Short": pot_short,
                    "PoT 2Δ Approx": pot_approx,
                    "PoT Skew Adj": _skew_adj,
                    "Gamma Neto": gamma_neto,
                    "Theta Neto": theta_neto,
                    "Decay 7d": decay_7d,
                    "Decay Days": _decay_days,
                    # POP basada en breakeven real del spread (más precisa que 1-|delta|)
                    # Las plataformas oficiales usan N(d2) con K=breakeven.
                    "POP %": round(pop_be * 100, 1),
                    "POP Delta %": round(pop * 100, 1),     # 1-|delta|, guardado como referencia
                    "POP Breakeven %": round(pop_be * 100, 1),
                    "Prob OTM %": round(pop * 100, 1),
                    "Crédito": credit,
                    "Riesgo Máx": max_risk,
                    "Retorno %": retorno_pct,
                    "IV Short %": round(sold_iv * 100, 1),
                    "IV Long %": round(bought_iv * 100, 1),
                    "IV %": round(sold_iv * 100, 1),
                    "Breakeven": breakeven,
                    "Dist Strike %": dist_pct,
                    "Vol Short": sold_vol,
                    "OI Short": sold_oi,
                    "Liq Score": liq_score,
                    "EV Real Adj": ev_real_adj,
                    "Surface Edge": surface_edge,
                    "Volumen": sold_vol + bought_vol,
                    "OI": sold_oi + bought_oi,
                    "Bid-Ask": _bid_ask_spread(sold_bid, sold_ask),
                    "Liquidez": sold_vol + sold_oi + bought_vol + bought_oi,
                }
                if ticker_meta:
                    row.update(ticker_meta)
                results.append(row)

    # ── Bear Call Spreads ────────────────────────────────────────────────
    if (allowed_type is None or allowed_type == "Bear Call") and not calls.empty and len(calls) >= 2:
        otm_calls = calls[
            (calls["strike"] > spot) &
            (calls["bid"].fillna(0) > 0)
        ].sort_values("strike", ascending=True).reset_index(drop=True)

        # ATM IV de calls para detección de skew — se calcula una vez por expiración
        _atm_iv_call = 0.0
        if "impliedVolatility" in calls.columns and not calls.empty:
            try:
                _atm_idx_call = (calls["strike"] - spot).abs().idxmin()
                _raw_atm_call = float(_safe_num(calls.at[_atm_idx_call, "impliedVolatility"], 0))
                _atm_iv_call = _raw_atm_call if _raw_atm_call > 0.01 else 0.0
            except Exception:
                _atm_iv_call = 0.0

        for i in range(len(otm_calls)):
            sold = otm_calls.iloc[i]
            sold_strike = float(sold["strike"])
            sold_bid = float(_safe_num(sold.get("bid", 0)))
            sold_ask = float(_safe_num(sold.get("ask", 0)))
            sold_iv = float(_safe_num(sold.get("impliedVolatility", 0), 0))
            sold_vol = int(_safe_num(sold.get("volume", 0)))
            sold_oi = int(_safe_num(sold.get("openInterest", 0)))

            # Delta preciso vía BSM
            sold_delta = _bsm_delta(spot, sold_strike, dte, sold_iv, "call")

            # Skew adjust para calls OTM (usualmente 0 en renta variable)
            _skew_adj_c = 0.0
            if _atm_iv_call > 0.01 and sold_iv > _atm_iv_call:
                _skew_pct_c = (sold_iv - _atm_iv_call) / _atm_iv_call * 100.0
                _skew_adj_c = round(min(_skew_pct_c * 0.2, 5.0), 2)

            # Filtro 4 — Delta del short strike (strict)
            if _sr.get("r4_delta", strict):
                abs_d = abs(sold_delta)
                if abs_d < CS_DELTA_MIN or abs_d > CS_DELTA_MAX:
                    continue

            pop = _pop_from_delta(sold_delta)
            if pop < min_pop:
                continue

            # Filtro 8 — Distancia del strike (strict)
            dist_pct = _strike_distance_pct(spot, sold_strike)
            if _sr.get("r8_distance", strict) and dist_pct < CS_MIN_DIST_PCT:
                continue

            # Filtro 9a/9b — Liquidez del contrato vendido (strict)
            if _sr.get("r9_liquidity", strict) and (sold_oi < CS_MIN_SOLD_OI or sold_vol < CS_MIN_SOLD_VOL):
                continue

            # Filtro 9c — Bid-Ask (strict)
            if _sr.get("r9_liquidity", strict) and not _passes_bid_ask_filter(sold_bid, sold_ask):
                continue

            # Build a strike→row lookup for fast width matching
            _call_strikes = {float(r["strike"]): r for _, r in otm_calls.iterrows()}

            if _sr.get("r6_width", strict):
                _target_widths_c = CS_ALLOWED_WIDTHS
            else:
                _target_widths_c = None

            _bought_candidates_c: list[tuple[float, pd.Series]] = []
            if _target_widths_c:
                for w in _target_widths_c:
                    target_k = round(sold_strike + w, 2)
                    if target_k in _call_strikes:
                        _bought_candidates_c.append((target_k, _call_strikes[target_k]))
            else:
                for j in range(i + 1, min(i + 8, len(otm_calls))):
                    _b = otm_calls.iloc[j]
                    _bought_candidates_c.append((float(_b["strike"]), _b))

            for bought_strike, bought in _bought_candidates_c:
                bought_ask = float(_safe_num(bought.get("ask", 0)))

                if bought_ask <= 0:
                    continue

                # Mid-price credit: (bid+ask)/2 del vendido − (bid+ask)/2 del comprado
                _bought_bid_bc = float(_safe_num(bought.get("bid", 0)))
                _sold_mid_bc = (sold_bid + sold_ask) / 2.0 if sold_ask > 0 else sold_bid
                _bought_mid_bc = (_bought_bid_bc + bought_ask) / 2.0 if bought_ask > 0 else bought_ask
                credit = round(_sold_mid_bc - _bought_mid_bc, 2)
                if credit < min_credit:
                    continue

                width = round(bought_strike - sold_strike, 2)
                if width <= 0:
                    continue

                # Filtro 6 — Ancho del spread (strict)
                if _sr.get("r6_width", strict):
                    width_int = int(round(width))
                    if width_int not in CS_ALLOWED_WIDTHS:
                        continue

                # Filtro 7 — Crédito mínimo % del ancho (strict)
                if _sr.get("r7_credit_pct", strict) and credit < width * CS_MIN_CREDIT_PCT:
                    continue

                max_risk = round(width - credit, 2)
                if max_risk <= 0:
                    continue

                retorno_pct = round((credit / max_risk) * 100, 2)
                bought_vol = int(_safe_num(bought.get("volume", 0)))
                bought_oi = int(_safe_num(bought.get("openInterest", 0)))

                # ── Métricas Fase 1: PoT, Delta Comprado, Delta Neto ─────
                bought_ivbc = float(_safe_num(bought.get("impliedVolatility", sold_iv)) or sold_iv)
                bought_delta_bc = _bsm_delta(spot, bought_strike, dte, bought_ivbc, "call")

                # PoT: BSM first-passage barrier + ajuste por skew de IV del strike
                pot_short_bc = calculate_probability_of_touch_precise(
                    spot=spot, strike=sold_strike, dte=dte,
                    iv_short=sold_iv, option_type="call",
                    skew_adjust=_skew_adj_c, r=RISK_FREE_RATE,
                )
                pot_approx_bc = _pot_approx_2delta(sold_delta)

                # Delta Neto: para Bear Call (short lower call, long higher call),
                # ambos deltas son positivos.  El spread neto es bearish (negativo).
                # Δ_spread = -Δ_short_call + Δ_long_call
                delta_neto_bc = round(-sold_delta + bought_delta_bc, 4)

                # POP basado en breakeven real del spread
                breakeven_bc = round(sold_strike + credit, 2)
                pop_be_bc = _pop_from_breakeven(spot, breakeven_bc, dte, sold_iv, "call")
                pop_bc = _pop_from_delta(sold_delta)  # referencia

                # ── Métricas Fase 2: Gamma, Theta, Liquidez ───────────────
                _gc_sold = _bsm_greeks(spot, sold_strike, dte, sold_iv, "call")
                _gc_bought = _bsm_greeks(spot, bought_strike, dte, bought_ivbc, "call")
                gamma_neto_bc = round(_gc_bought["gamma"] - _gc_sold["gamma"], 6)
                theta_neto_bc = round(-_gc_sold["theta"] + _gc_bought["theta"], 6)
                _decay_days_bc = min(7, max(1, dte))
                decay_7d_bc = round(theta_neto_bc * _decay_days_bc, 2)
                _ba_mid_c = (sold_bid + sold_ask) / 2 if sold_ask > 0 else 0.01
                _ba_tight_c = (sold_ask - sold_bid) / _ba_mid_c if _ba_mid_c > 0 else 1.0
                liq_score_bc = (
                    (40 if sold_oi > 1000 else sold_oi / 1000 * 40)
                    + (30 if sold_vol > 200 else sold_vol / 200 * 30)
                    + (30 if _ba_tight_c < 0.10 else max(0, 30 * (1 - _ba_tight_c)))
                )
                liq_score_bc = round(min(100, max(0, liq_score_bc)), 1)

                # ── Fase 3: EV Real Adjusted + Surface Edge ───────────────
                ev_real_adj_bc = compute_ev_real_adjusted(
                    spot, sold_strike, dte, sold_iv, credit, max_risk, "call",
                    breakeven=breakeven_bc,
                )
                surface_edge_bc = _surface_edge(
                    spot, sold_strike, dte, sold_iv, round(pop_bc * 100, 1), "call",
                )

                row = {
                    "Ticker": ticker,
                    "Tipo": "Bear Call",
                    "Spot": round(spot, 2),
                    "Strike Vendido": sold_strike,
                    "Strike Comprado": bought_strike,
                    "DTE": dte,
                    "Expiración": exp_date,
                    "Delta Vendido": round(sold_delta, 4),
                    "Delta Comprado": round(bought_delta_bc, 4),
                    "Delta Neto": delta_neto_bc,
                    "PoT Short": pot_short_bc,
                    "PoT 2Δ Approx": pot_approx_bc,
                    "PoT Skew Adj": _skew_adj_c,
                    "Gamma Neto": gamma_neto_bc,
                    "Theta Neto": theta_neto_bc,
                    "Decay 7d": decay_7d_bc,
                    "Decay Days": _decay_days_bc,
                    "POP %": round(pop_be_bc * 100, 1),
                    "POP Delta %": round(pop_bc * 100, 1),
                    "POP Breakeven %": round(pop_be_bc * 100, 1),
                    "Prob OTM %": round(pop_bc * 100, 1),
                    "Crédito": credit,
                    "Riesgo Máx": max_risk,
                    "Retorno %": retorno_pct,
                    "IV Short %": round(sold_iv * 100, 1),
                    "IV Long %": round(bought_ivbc * 100, 1),
                    "IV %": round(sold_iv * 100, 1),
                    "Breakeven": breakeven_bc,
                    "Dist Strike %": dist_pct,
                    "Vol Short": sold_vol,
                    "OI Short": sold_oi,
                    "Liq Score": liq_score_bc,
                    "EV Real Adj": ev_real_adj_bc,
                    "Surface Edge": surface_edge_bc,
                    "Volumen": sold_vol + bought_vol,
                    "OI": sold_oi + bought_oi,
                    "Bid-Ask": _bid_ask_spread(sold_bid, sold_ask),
                    "Liquidez": sold_vol + sold_oi + bought_vol + bought_oi,
                }
                if ticker_meta:
                    row.update(ticker_meta)
                # Debug para validación vs plataforma B (spread ejemplo IWM Bear Call)
                if ticker.upper() == "IWM" and 24 <= dte <= 30:
                    logger.debug(
                        "[IWM DEBUG] Bear Call K=%s/%.0f DTE=%d | "
                        "IV_short=%.1f%% IV_ATM=%.1f%% SkewAdj=+%.2fpp | "
                        "PoT=%.1f%% PoT_2Δ=%.1f%% | "
                        "BE=%.2f POP_BE=%.1f%% EV_Real=%.1f%%",
                        sold_strike, bought_strike, dte,
                        sold_iv * 100, _atm_iv_call * 100, _skew_adj_c,
                        pot_short_bc, pot_approx_bc,
                        breakeven_bc, pop_be_bc * 100, ev_real_adj_bc,
                    )
                results.append(row)

    return results


# ────────────────────────────────────────────────────────────────────────────
#  Escaneo de un ticker completo (todas las expiraciones válidas)
# ────────────────────────────────────────────────────────────────────────────

def _scan_single_ticker(
    ticker: str,
    min_pop: float,
    max_dte: int,
    min_credit: float,
    strict: bool = False,
    strict_rules: dict | None = None,
) -> tuple[list[dict], dict]:
    """Escanea todas las expiraciones válidas de un ticker.

    Parameters
    ----------
    strict : bool
        Si True, aplica pipeline completo de 9 filtros.
    strict_rules : dict | None
        Reglas individuales activadas. Tiene prioridad sobre ``strict``.

    Returns
    -------
    tuple[list[dict], dict]
        (lista de spreads, metadata del ticker — IV rank, trend, etc.)
    """
    _sr = strict_rules or {}
    spot, err = obtener_precio_actual(ticker)
    if not spot:
        logger.warning("Sin precio para %s: %s", ticker, err)
        return [], {}

    # Calcular indicadores a nivel de ticker (una sola vez).
    # Primero obtenemos el ATM IV de la primera expiración disponible para que
    # compute_iv_rank_percentile use la IV implícita real en vez del HV20.
    _atm_iv_for_rank: float = 0.0
    try:
        _early_dates = _cached_options_dates(ticker)
        if _early_dates:
            _early_chain = _cached_option_chain(ticker, _early_dates[0])
            _early_puts = _early_chain.get("puts", pd.DataFrame())
            if not _early_puts.empty and "impliedVolatility" in _early_puts.columns:
                _atm_idx_r = (_early_puts["strike"] - spot).abs().idxmin()
                _raw_atm_r = float(_safe_num(_early_puts.at[_atm_idx_r, "impliedVolatility"], 0))
                _atm_iv_for_rank = _raw_atm_r if _raw_atm_r > 0.01 else 0.0
    except Exception:
        _atm_iv_for_rank = 0.0

    iv_info = compute_iv_rank_percentile(ticker, current_atm_iv=_atm_iv_for_rank)
    trend_info = compute_trend(ticker)

    combined_meta = {"ticker": ticker, **iv_info, **trend_info}

    # ── Filtro 1 — Underlying (strict) ───────────────────────────────────
    if _sr.get("r1_whitelist", strict):
        ok, reason = _passes_underlying_filter(ticker, spot)
        if not ok:
            logger.info("[STRICT] %s descartado — %s", ticker, reason)
            return [], combined_meta

    # ── Filtro 2 — IV Rank mínimo (strict) ───────────────────────────────
    # Nota: ya no descarta el ticker completo — solo registra advertencia.
    # El IV Rank se incluye en los resultados para que el usuario decida.
    if _sr.get("r2_iv_rank", strict) and iv_info["iv_rank"] < CS_MIN_IV_RANK:
        logger.info(
            "[STRICT-WARN] %s IV Rank %.1f < %d — se continúa igualmente",
            ticker, iv_info["iv_rank"], CS_MIN_IV_RANK,
        )

    # ── Filtro 5 — Dirección / Tendencia (strict) ────────────────────────
    allowed_type: str | None = None
    if _sr.get("r5_trend", strict):
        trend = trend_info["trend"]
        if trend == "Alcista":
            allowed_type = "Bull Put"
        elif trend == "Bajista":
            allowed_type = "Bear Call"
        else:
            # Neutral → no mostrar trades
            logger.info("[STRICT] %s descartado — tendencia Neutral", ticker)
            return [], combined_meta

    ticker_meta = {
        "IV Rank": iv_info["iv_rank"],
        "IV Pctil": iv_info["iv_percentile"],
        "HV 20D": iv_info.get("hv_current", iv_info["iv_current"]),  # HV anualizada 20D
        "IV ATM": iv_info["iv_current"],  # IV ATM real (o HV20 si no hay cadena)
        "Tendencia": trend_info["trend"],
    }

    try:
        exp_dates = _cached_options_dates(ticker)
    except Exception as exc:
        logger.warning("Sin fechas de expiración para %s: %s", ticker, exc)
        return [], combined_meta

    all_spreads: list[dict] = []

    # Filtrar expirations válidas y capear a 6 para evitar rate-limiting
    valid_exps = [e for e in exp_dates if 0 < _dte_from_expiry(e) <= max_dte]

    # Cuando R3 (DTE estricto) está activo, pre-filtrar expirations al rango
    # CS_DTE_MIN–CS_DTE_MAX *antes* de aplicar el cap de 6.  Sin esto, las 6
    # primeras pueden ser DTEs cortos que R3 rechazará al 100 %.
    if _sr.get("r3_dte", strict):
        valid_exps = [
            e for e in valid_exps
            if CS_DTE_MIN <= _dte_from_expiry(e) <= CS_DTE_MAX
        ]

    if len(valid_exps) > 6:
        valid_exps = valid_exps[:6]  # 6 expirations más cercanas

    import time as _t_mod
    for _ei, exp_date in enumerate(valid_exps):
        if _ei > 0:
            _t_mod.sleep(0.5)  # anti-rate-limit entre expiraciones
        spreads = _build_spreads_for_expiry(
            ticker, spot, exp_date, min_pop, min_credit, ticker_meta,
            allowed_type=allowed_type,
            strict=strict,
            strict_rules=_sr,
        )
        all_spreads.extend(spreads)

    return all_spreads, combined_meta


# ────────────────────────────────────────────────────────────────────────────
#  Datos rápidos de mercado (background updater)
# ────────────────────────────────────────────────────────────────────────────

def get_fast_market_data(tickers: list[str]) -> dict[str, dict]:
    """Obtiene datos ligeros de mercado para un batch de tickers.

    Para cada ticker recopila:
      - spot (precio actual)
      - iv_rank, iv_percentile (rango/percentil de IV)
      - trend (tendencia: Alcista/Bajista/Neutral)
      - expirations (lista de expiraciones disponibles)
      - updated_at (timestamp de actualización)

    Respeta rate limiter + circuit breaker globales de yfinance.
    Usa sleep aleatorio entre llamadas para evitar bans.

    Args:
        tickers: lista de símbolos (ej. ["AAPL", "MSFT", "NVDA"]).

    Returns:
        dict[str, dict] — {ticker: {spot, iv_rank, ...}} para los que
        se obtuvieron datos exitosamente.
    """
    import time as _time
    from random import uniform as _uniform
    from utils.retry_utils import cb_yfinance

    results: dict[str, dict] = {}

    for ticker in tickers:
        try:
            # Respetar circuit breaker
            if cb_yfinance.is_open:
                logger.warning("get_fast_market_data: circuit breaker abierto — abortando batch")
                break

            # Precio actual (usa cache TTL interno de 5 min)
            spot, err = obtener_precio_actual(ticker)
            if not spot:
                logger.debug("get_fast_market_data: sin precio para %s: %s", ticker, err)
                continue

            # IV rank + percentile + tendencia
            # Nota: NO se fetcha _cached_options_dates aquí — descargar la cadena
            # de opciones de 100 tickers en background agota el rate-limit de Yahoo
            # Finance y bloquea los scans activos del usuario.
            iv_info = compute_iv_rank_percentile(ticker)
            trend_info = compute_trend(ticker)

            results[ticker] = {
                "spot": round(spot, 2),
                "iv_rank": iv_info.get("iv_rank", 0),
                "iv_percentile": iv_info.get("iv_percentile", 0),
                "trend": trend_info.get("trend", "Neutral"),
                "updated_at": _time.time(),
            }

            cb_yfinance.record_success()

            # Sleep anti-ban entre tickers
            _time.sleep(_uniform(1.8, 2.5))

        except Exception as exc:
            cb_yfinance.record_failure()
            logger.warning("get_fast_market_data: error en %s — %s", ticker, exc)
            # Continuar con el siguiente ticker
            _time.sleep(_uniform(2.0, 3.5))

    logger.info("get_fast_market_data: %d/%d tickers OK", len(results), len(tickers))
    return results


# ────────────────────────────────────────────────────────────────────────────
#  Función pública principal
# ────────────────────────────────────────────────────────────────────────────

def scan_credit_spreads(
    tickers: list[str],
    min_pop: float = 0.70,
    max_dte: int = 45,
    min_credit: float = 0.30,
    progress_callback=None,
    strict: bool = False,
    strict_rules: dict | None = None,
) -> tuple[pd.DataFrame, dict[str, dict]]:
    """Escanea múltiples tickers buscando Credit Spreads óptimos.

    Parameters
    ----------
    tickers : list[str]
        Lista de símbolos a escanear.
    min_pop : float
        Probabilidad mínima de ganancia (0-1). Default 0.70.
    max_dte : int
        Máximo de días hasta vencimiento. Default 45.
    min_credit : float
        Crédito mínimo por spread en USD. Default 0.30.
    progress_callback : callable, optional
        Función(ticker, idx, total) para reportar progreso.
    strict : bool
        Si True, aplica los 9 filtros obligatorios del pipeline.
        En modo strict, solo se escanean tickers de la whitelist.
    strict_rules : dict | None
        Reglas individuales activadas. Tiene prioridad sobre ``strict``.

    Returns
    -------
    tuple[pd.DataFrame, dict[str, dict]]
        (DataFrame de oportunidades ordenado por Income Score,
         dict {ticker: {iv_rank, iv_percentile, trend, ...}} por ticker)
    """
    _sr = strict_rules or {}
    all_results: list[dict] = []
    ticker_indicators: dict[str, dict] = {}

    # Nunca recortar los tickers elegidos por el usuario contra la whitelist:
    # el usuario seleccionó explícitamente esos tickers en la UI.
    # R1 sigue validando precio>$20 y volumen>1M individualmente en
    # _passes_underlying_filter — ese filtro no se toca.
    clean_tickers = [t.strip().upper() for t in tickers if t.strip()]
    total = len(clean_tickers)

    import time as _time

    for idx, ticker in enumerate(clean_tickers):
        if progress_callback:
            progress_callback(ticker, idx, total)
        # Delay anti-rate-limit entre tickers (salvo el primero)
        if idx > 0:
            _time.sleep(1.2)
        try:
            spreads, t_meta = _scan_single_ticker(
                ticker, min_pop, max_dte, min_credit,
                strict=strict, strict_rules=_sr,
            )
            all_results.extend(spreads)
            if t_meta:
                ticker_indicators[ticker] = t_meta
        except KeyboardInterrupt:
            # curl_cffi raises spurious KeyboardInterrupt from buffer_callback
            logger.error("KeyboardInterrupt (curl_cffi) escaneando %s — continuando", ticker)
        except Exception as exc:
            logger.error("Error escaneando %s: %s", ticker, exc)

    if not all_results:
        return pd.DataFrame(), ticker_indicators

    df = pd.DataFrame(all_results)

    # ── Income Score por cada spread ─────────────────────────────────
    scores, labels = zip(*[
        compute_income_score(row) for row in all_results
    ])
    df["Income Score"] = list(scores)
    df["Calidad"] = list(labels)

    # ── Score de Oportunidad por cada spread ──────────────────────────
    opp_scores, opp_labels = zip(*[
        compute_opportunity_score(row) for row in all_results
    ])
    df["Score Oportunidad"] = list(opp_scores)
    df["Nivel"] = list(opp_labels)

    # Nota: ya no se filtra por OPP_SCORE_MIN_SHOW — las reglas estrictas
    # (R1-R9) ya garantizan calidad. El score se muestra al usuario.
    if df.empty:
        return pd.DataFrame(), ticker_indicators

    # ── EV Ajustado por capital en riesgo (Fase 1) ────────────────────
    def _ev_ajustado(row: dict) -> float:
        """EV como % del capital en riesgo, usando POP breakeven BSM.

        Usa la probabilidad de superar el breakeven real del spread
        (POP Breakeven %) en vez de la aproximación 1-|Δ|, alineándose
        con plataformas institucionales como TOS / TastyTrade.

        EV = P(S_T > breakeven) × crédito − P(S_T ≤ breakeven) × riesgo
        ev_ajustado = EV / riesgo_máx × 100
        """
        credit_ = row.get("Crédito", 0) or 0
        risk_ = row.get("Riesgo Máx", 0) or 0
        # Usar POP breakeven BSM — más preciso que 1-|Δ|
        pop_ = (row.get("POP Breakeven %", row.get("POP %", 70)) or 70) / 100.0
        if risk_ <= 0:
            return 0.0
        ev = credit_ * pop_ - risk_ * (1.0 - pop_)
        return round(ev / risk_ * 100.0, 2)

    df["EV Ajustado"] = [
        _ev_ajustado(r) for r in df.to_dict("records")
    ]

    # ── Score Final Optimizado (Fase 3) ────────────────────────────────
    # Usa EV Real Adj + Surface Edge + pesos optimizables por backtesting.
    # compute_optimized_score vive en core/backtester.py
    df["Score Final"] = [
        compute_optimized_score(r) for r in df.to_dict("records")
    ]

    # Ordenar por Score Final > Score Oportunidad > Income Score > Retorno
    df = df.sort_values(
        ["Score Final", "Score Oportunidad", "Income Score", "Retorno %"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)

    return df, ticker_indicators


# ────────────────────────────────────────────────────────────────────────────
#  Sistema de Alertas — 10 reglas obligatorias sequenciales
# ────────────────────────────────────────────────────────────────────────────

