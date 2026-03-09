# -*- coding: utf-8 -*-
"""
Backtester — Simulación histórica de credit spreads.

Usa datos de precios del subyacente (yfinance) para responder:
  ¿Cuántos spreads con estas características hubieran ganado en los últimos
  30-90 días?

Métricas que produce:
  - Win Rate (%), Avg Profit ($), Profit Factor ($/$ riesgo)
  - Edge real: WR - (1 - POP teórico)

Los resultados se cachean en session_state para no recalcular en cada render.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from config.constants import RISK_FREE_RATE, DAYS_PER_YEAR
from core.option_greeks import OptionGreeks

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
#  Resultado del backtest
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class BacktestResult:
    """Resultados compactos del backtest para un conjunto de spreads."""
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0          # 0-100
    avg_profit: float = 0.0        # $ promedio por trade
    profit_factor: float = 0.0     # gross_profit / gross_loss
    edge: float = 0.0              # WR real - POP teórico (pp)
    optimized_weights: dict = field(default_factory=dict)


# ────────────────────────────────────────────────────────────────────────────
#  Helper: probabilidad de expirar OTM usando IV del strike (BSM real)
# ────────────────────────────────────────────────────────────────────────────

def _prob_otm_bsm(
    spot: float,
    strike: float,
    dte: int,
    iv: float,
    option_type: str = "put",
) -> float:
    """Probabilidad de que el strike expire OTM (BSM real con IV del strike).

    Para puts:  P(S_T > K) = N(d2)
    Para calls: P(S_T < K) = N(-d2)

    Usa la IV específica del strike (no genérica) para reflejar la surface.
    """
    T = max(dte, 1) / DAYS_PER_YEAR
    sigma = iv if iv > 0.01 else 0.25
    try:
        g = OptionGreeks(S=spot, K=strike, T=T, r=RISK_FREE_RATE, sigma=sigma)
        # d2 ya está pre-calculado
        from scipy.stats import norm
        d2 = g._d2
        if option_type == "put":
            return float(norm.cdf(d2))     # P(S_T > K)
        return float(norm.cdf(-d2))        # P(S_T < K)
    except Exception:
        return 0.70  # fallback conservador


def _surface_edge(
    spot: float,
    strike: float,
    dte: int,
    iv_strike: float,
    pop_calculated: float,
    option_type: str = "put",
) -> float:
    """Calcula el edge entre la probabilidad de la surface vs la POP genérica.

    surface_edge = (prob_surface - pop_genérica) * 100

    Positivo → la surface indica MEJOR probabilidad de la que usamos.
    Negativo → penalización por skew/smile distorsionado.
    """
    prob_surface = _prob_otm_bsm(spot, strike, dte, iv_strike, option_type)
    return round((prob_surface - pop_calculated / 100.0) * 100.0, 2)


# ────────────────────────────────────────────────────────────────────────────
#  Helper: EV Real ajustado con IV del strike individual
# ────────────────────────────────────────────────────────────────────────────

def compute_ev_real_adjusted(
    spot: float,
    strike: float,
    dte: int,
    iv_strike: float,
    credit: float,
    max_risk: float,
    option_type: str = "put",
    breakeven: float | None = None,
) -> float:
    """EV ajustado usando la probabilidad derivada de la IV del strike corto.

    Si se proporciona ``breakeven``, la probabilidad se calcula sobre el
    breakeven real del spread (short_strike − crédito para Bull Put,
    short_strike + crédito para Bear Call), alineándose con plataformas
    institucionales como TOS / TastyTrade:

        EV = P(S_T > breakeven) × crédito − P(S_T ≤ breakeven) × riesgo

    Sin breakeven (modo legacy), usa P(S_T > strike) como antes.
    ev_real_adj = EV / riesgo × 100
    """
    if max_risk <= 0 or credit <= 0:
        return 0.0
    # Usar breakeven como K si está disponible — más preciso que el strike
    k_prob = breakeven if (breakeven is not None and breakeven > 0) else strike
    prob_otm = _prob_otm_bsm(spot, k_prob, dte, iv_strike, option_type)
    ev = prob_otm * credit - (1.0 - prob_otm) * max_risk
    return round(ev / max_risk * 100.0, 2)


# ────────────────────────────────────────────────────────────────────────────
#  Backtester principal
# ────────────────────────────────────────────────────────────────────────────

class Backtester:
    """Simulador de P&L histórico para credit spreads.

    Usa precios pasados del subyacente para determinar si un spread
    hubiera expirado ITM o OTM en los últimos N días.
    """

    def __init__(self, lookback_days: int = 60) -> None:
        self.lookback_days = lookback_days

    def run(
        self,
        ticker: str,
        spreads: list[dict],
        hist_df: Optional[pd.DataFrame] = None,
    ) -> BacktestResult:
        """Ejecuta el backtest sobre una lista de spreads.

        Parameters
        ----------
        ticker : str
            Ticker del subyacente.
        spreads : list[dict]
            Lista de dicts con al menos:
                Tipo, Strike Vendido, Strike Comprado, DTE, Crédito, Riesgo Máx, POP %
        hist_df : pd.DataFrame, optional
            DataFrame de precios históricos (Close). Si no se pasa, se descarga.

        Returns
        -------
        BacktestResult con métricas agregadas.
        """
        if not spreads:
            return BacktestResult()

        # Obtener precios históricos
        if hist_df is None:
            hist_df = self._get_history(ticker)
        if hist_df is None or hist_df.empty or len(hist_df) < 5:
            logger.warning("Backtester: sin datos históricos para %s", ticker)
            return BacktestResult()

        closes = hist_df["Close"].values
        n_data = len(closes)

        wins = 0
        losses = 0
        gross_profit = 0.0
        gross_loss = 0.0
        pop_sum = 0.0

        for sp in spreads:
            tipo = sp.get("Tipo", "Bull Put")
            sold_k = sp.get("Strike Vendido", 0)
            credit = sp.get("Crédito", 0)
            risk = sp.get("Riesgo Máx", 0)
            pop = sp.get("POP %", 70)
            dte = max(sp.get("DTE", 30), 1)

            if sold_k <= 0 or credit <= 0 or risk <= 0:
                continue

            pop_sum += pop

            # Simular: cuántas veces el spot hubiera estado por encima (put)
            # o debajo (call) del strike vendido después de DTE días
            step = max(1, dte // 2)  # simular cada DTE/2 días para más puntos
            sim_wins = 0
            sim_total = 0

            for start_idx in range(0, max(1, n_data - dte), step):
                end_idx = min(start_idx + dte, n_data - 1)
                price_at_expiry = closes[end_idx]

                if tipo == "Bull Put":
                    # Gana si spot > strike vendido
                    won = price_at_expiry > sold_k
                else:
                    # Bear Call: gana si spot < strike vendido
                    won = price_at_expiry < sold_k

                sim_total += 1
                if won:
                    sim_wins += 1

            if sim_total == 0:
                continue

            trade_wr = sim_wins / sim_total
            if trade_wr >= 0.5:
                wins += 1
                gross_profit += credit * 100  # por contrato
            else:
                losses += 1
                gross_loss += risk * 100

        total = wins + losses
        if total == 0:
            return BacktestResult()

        wr = wins / total * 100.0
        avg_pop = pop_sum / total if total else 70.0
        pf = gross_profit / max(gross_loss, 0.01)
        avg_p = (gross_profit - gross_loss) / total

        return BacktestResult(
            total_trades=total,
            wins=wins,
            losses=losses,
            win_rate=round(wr, 1),
            avg_profit=round(avg_p, 2),
            profit_factor=round(pf, 2),
            edge=round(wr - avg_pop, 1),
            optimized_weights=self._optimize_weights(wr),
        )

    def _optimize_weights(self, historical_wr: float) -> dict:
        """Retorna pesos optimizados basados en el win rate histórico.

        Estrategia:
          - WR >= 75%: más peso a income/theta (agresivo)
          - WR >= 65%: balanceado
          - WR <  65%: priorizar riesgo (PoT, EV, gamma)
        Todos los dicts tienen 10 componentes y suman 1.00.
        """
        if historical_wr >= 75:
            # Estrategia agresiva — sigue priorizando PoT y EV Real
            return {
                "income": 0.12, "opp": 0.10, "anti_pot": 0.20,
                "pop_be": 0.06, "anti_dn": 0.04, "ev_real": 0.20,
                "anti_gamma": 0.05, "liq": 0.10, "theta": 0.07, "surface_edge": 0.06,
            }
        elif historical_wr >= 65:
            # Estrategia balanceada
            return {
                "income": 0.12, "opp": 0.10, "anti_pot": 0.20,
                "pop_be": 0.07, "anti_dn": 0.05, "ev_real": 0.20,
                "anti_gamma": 0.06, "liq": 0.10, "theta": 0.06, "surface_edge": 0.04,
            }
        else:
            # Estrategia conservadora — más peso a PoT y EV Real
            return {
                "income": 0.10, "opp": 0.09, "anti_pot": 0.22,
                "pop_be": 0.08, "anti_dn": 0.06, "ev_real": 0.20,
                "anti_gamma": 0.08, "liq": 0.10, "theta": 0.04, "surface_edge": 0.03,
            }

    def _get_history(self, ticker: str) -> Optional[pd.DataFrame]:
        """Descarga historial de precios para el backtest."""
        try:
            from core.scanner import _cached_history
            period = "3mo" if self.lookback_days <= 90 else "6mo"
            return _cached_history(ticker, period)
        except Exception as exc:
            logger.warning("Backtester._get_history(%s): %s", ticker, exc)
            return None


# ────────────────────────────────────────────────────────────────────────────
#  Score Optimizado Final (Fase 3)
# ────────────────────────────────────────────────────────────────────────────

def compute_optimized_score(
    row: dict,
    weights: Optional[dict] = None,
) -> float:
    """Score Final Optimizado — combina Fase 1 + Fase 2 + Fase 3.

    Fórmula:
        optimized = Σ (peso_i × componente_i) × 100

    Componentes (10):
        1.  Income Score (normalizado 0-1)
        2.  Opportunity Score (normalizado 0-1)
        3.  Anti-PoT (1 - PoT/100)          ← peso 20%: métrica clave
        4.  POP Breakeven % / 100           ← NUEVO: prob BSM real de ganar
        5.  Anti-Delta Neto (1 - |ΔN|)
        6.  EV Real Adjusted / 15           ← peso 20%: métrica clave
        7.  Anti-Gamma (1 - |Γ|×10)
        8.  Liquidity Score / 100
        9.  Theta Decay 7d / 10
        10. Surface Edge / 20               (puede ser negativo)

    Pesos calibrados para alinearse con plataformas institucionales:
    anti_pot y ev_real priorizados al 20% c/u.  Suma de pesos = 1.00.
    Se ajustan dinámicamente si el backtester devuelve WR histórico.
    """
    if weights is None:
        # Pesos institucionales: priorizan PoT y EV Real (suma = 1.00)
        weights = {
            "income": 0.12, "opp": 0.10, "anti_pot": 0.20,
            "pop_be": 0.06, "anti_dn": 0.05, "ev_real": 0.20,
            "anti_gamma": 0.06, "liq": 0.10, "theta": 0.06, "surface_edge": 0.05,
        }

    inc    = (row.get("Income Score", 0) or 0) / 100.0
    opp    = (row.get("Score Oportunidad", 0) or 0) / 100.0
    pot    = (row.get("PoT Short", 50) or 50) / 100.0
    pop_be = (row.get("POP Breakeven %", row.get("POP %", 70)) or 70) / 100.0
    dn     = abs(row.get("Delta Neto", 0) or 0)
    ev_r   = (row.get("EV Real Adj", 0) or 0)
    gn     = abs(row.get("Gamma Neto", 0) or 0)
    liq    = (row.get("Liq Score", 0) or 0) / 100.0
    d7     = (row.get("Decay 7d", 0) or 0)
    se     = (row.get("Surface Edge", 0) or 0)

    raw = (
        weights.get("income",       0.12) * inc
        + weights.get("opp",        0.10) * opp
        + weights.get("anti_pot",   0.20) * max(0.0, 1.0 - pot)
        + weights.get("pop_be",     0.06) * pop_be
        + weights.get("anti_dn",    0.05) * max(0.0, 1.0 - dn)
        + weights.get("ev_real",    0.20) * min(1.0, max(0.0, ev_r / 15.0))
        + weights.get("anti_gamma", 0.06) * max(0.0, 1.0 - gn * 10.0)
        + weights.get("liq",        0.10) * liq
        + weights.get("theta",      0.06) * min(1.0, max(0.0, d7 / 10.0))
        + weights.get("surface_edge", 0.05) * min(1.0, max(-0.5, se / 20.0))
    )
    return round(raw * 100.0, 1)
