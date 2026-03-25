# -*- coding: utf-8 -*-
"""
OKA Sentiment Index v2 — Motor Analítico.

Rediseño completo basado en flujo direccional institucional real:
    1. Clasificación de agresión (aggressive buy / sell / neutral)
    2. Filtros institucionales (premium, volumen, tamaño, sweep)
    3. Delta-Weighted Premium como métrica base
    4. Directional Flow separation (bullish vs bearish)
    5. OKA Index = 50 + (NetFlow / TotalFlow) × 50

Phase 2 opcional: Gamma Weighting para ajuste de convexidad.

Fuente de datos primaria: yfinance (cadena de opciones).
Fallback: mock data (para demos sin API key).

Uso típico:
    from core.oka_sentiment_v2 import compute_oka_index

    result = compute_oka_index("SPY", gamma_weighting=False)
    # → {"oka_index": 66.2, "bullish_flow": 4_200_000, ...}
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta

from core.option_greeks import quick_delta, quick_gamma
from infrastructure.data.yahoo_finance_client import (
    fetch_options_dates,
    fetch_single_chain,
    obtener_precio_actual,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#   CONSTANTES INSTITUCIONALES
# ---------------------------------------------------------------------------
_MIN_PREMIUM_USD        = 50_000   # Filtro 1: premium mínimo $50k
_PERCENTILE_75_FALLBACK = 5        # Fallback si no hay suficientes trades

# ---------------------------------------------------------------------------
#   STEP 1 — AGGRESSION CLASSIFICATION
# ---------------------------------------------------------------------------

def classify_aggression(price: float, bid: float, ask: float) -> str:
    """Clasifica la agresión de un trade según su relación precio/spread.

    Args:
        price: precio de ejecución del trade.
        bid:   precio bid del momento del trade.
        ask:   precio ask del momento del trade.

    Returns:
        'aggressive_buy'  si price >= ask  (comprador empuja el ask)
        'aggressive_sell' si price <= bid  (vendedor aprieta el bid)
        'neutral'         en cualquier otro caso
    """
    if ask > 0 and price >= ask:
        return "aggressive_buy"
    if bid >= 0 and price <= bid and bid > 0:
        return "aggressive_sell"
    return "neutral"


# ---------------------------------------------------------------------------
#   STEP 2 — INSTITUTIONAL FILTERS
# ---------------------------------------------------------------------------

def apply_institutional_filters(
    trades: list[dict],
    percentile_75_size: float | None = None,
) -> list[dict]:
    """Aplica los 4 filtros institucionales obligatorios del PDF.

    Filtros (todos deben cumplirse):
        F1. Premium (price × volume × 100) >= $50,000
        F2. Volume > Open Interest del strike
        F3. Trade size > percentil 75 del volumen diario total
        F4. sweep_flag = True (si el campo existe en el trade)

    Args:
        trades:             lista de dicts con campos del trade.
        percentile_75_size: umbral pre-calculado del percentil 75.
                            Si es None, se calcula sobre los trades recibidos.

    Returns:
        Lista filtrada con solo los trades que pasan todos los filtros.
    """
    if not trades:
        return []

    # Calcular percentil 75 si no se proporcionó
    sizes = [float(t.get("size", t.get("volume", 1))) for t in trades]
    if percentile_75_size is None:
        sorted_sizes = sorted(sizes)
        idx_75 = int(len(sorted_sizes) * 0.75)
        percentile_75_size = sorted_sizes[idx_75] if sorted_sizes else _PERCENTILE_75_FALLBACK

    filtered: list[dict] = []
    for trade in trades:
        price  = float(trade.get("price",          0) or 0)
        volume = float(trade.get("size", trade.get("volume", 0)) or 0)
        oi     = float(trade.get("open_interest",  0) or 0)
        sweep  = trade.get("sweep_flag", None)

        # F1: Premium mínimo $50k
        premium = price * volume * 100
        if premium < _MIN_PREMIUM_USD:
            continue

        # F2: Volumen > Open Interest (si OI disponible; si no, skip)
        if oi > 0 and volume <= oi:
            continue

        # F3: Tamaño > percentil 75
        if volume <= percentile_75_size:
            continue

        # F4: Sweep flag — solo filtrar si el campo existe
        if sweep is not None and not sweep:
            continue

        filtered.append(trade)

    return filtered


# ---------------------------------------------------------------------------
#   STEP 3 — PREMIUM CALCULATION
# ---------------------------------------------------------------------------

def calculate_premium(price: float, volume: float) -> float:
    """Calcula el premium total del trade.

    Premium = price × volume × 100

    Args:
        price:  precio de la opción por contrato.
        volume: número de contratos.

    Returns:
        Premium en dólares.
    """
    return price * volume * 100


# ---------------------------------------------------------------------------
#   STEP 4 — DELTA WEIGHTED PREMIUM
# ---------------------------------------------------------------------------

def calculate_delta_weighted_premium(
    premium: float,
    delta: float,
    gamma: float = 0.0,
    gamma_weighting: bool = False,
) -> float:
    """Calcula el Delta-Weighted Premium (y opcionalmente Gamma-Adjusted).

    Modo estándar   (Phase 1): DeltaWeightedPremium = premium × |delta|
    Modo gamma      (Phase 2): GammaAdjusted        = premium × |delta| × gamma

    Args:
        premium:          premium en dólares (price × volume × 100).
        delta:            delta de la opción (float entre -1 y 1).
        gamma:            gamma de la opción (solo usado en Phase 2).
        gamma_weighting:  si True, aplica el ajuste gamma.

    Returns:
        DWP en dólares.
    """
    base = premium * abs(delta)
    if gamma_weighting and gamma > 0:
        return base * gamma
    return base


# ---------------------------------------------------------------------------
#   DELTA / GAMMA — delegated to core.option_greeks (single source of truth)
# ---------------------------------------------------------------------------
# quick_delta and quick_gamma are imported at the top from core.option_greeks.
# They provide the same safe fall-back behaviour that the old _approx_delta
# and _approx_gamma had (0.5/-0.5 and 0.0 on invalid inputs).

_approx_delta = quick_delta
_approx_gamma = quick_gamma


# ---------------------------------------------------------------------------
#   STEP 5 — DIRECTIONAL CLASSIFICATION
# ---------------------------------------------------------------------------

def classify_direction(trade: dict) -> str:
    """Determina la dirección del flujo de un trade institucional.

    Reglas (del PDF):
        BullishFlow: Call aggressive buy  | Put aggressive sell
        BearishFlow: Put aggressive buy   | Call aggressive sell

    Args:
        trade: dict con claves 'option_type' ('call'/'put'),
               'aggression' ('aggressive_buy'/'aggressive_sell'/'neutral').

    Returns:
        'bullish' | 'bearish' | 'neutral'
    """
    opt_type   = str(trade.get("option_type", "")).lower()
    aggression = str(trade.get("aggression", ""))

    is_call = opt_type.startswith("c")
    is_put  = opt_type.startswith("p")

    if is_call and aggression == "aggressive_buy":
        return "bullish"
    if is_put  and aggression == "aggressive_sell":
        return "bullish"
    if is_put  and aggression == "aggressive_buy":
        return "bearish"
    if is_call and aggression == "aggressive_sell":
        return "bearish"
    return "neutral"


# ---------------------------------------------------------------------------
#   STEP 6 — OKA INDEX FORMULA
# ---------------------------------------------------------------------------

def calculate_oka_index(bullish_flow: float, bearish_flow: float) -> float:
    """Calcula el OKA Sentiment Index v2.

    Fórmula:
        NetFlow   = BullishFlow − BearishFlow
        TotalFlow = BullishFlow + BearishFlow
        OKA_Index = 50 + (NetFlow / TotalFlow) × 50

    Si TotalFlow = 0 → devuelve 50 (neutral).

    Args:
        bullish_flow: flujo alcista total ($).
        bearish_flow: flujo bajista total ($).

    Returns:
        OKA Index en rango [0, 100].
    """
    total = bullish_flow + bearish_flow
    if total <= 0:
        return 50.0
    net   = bullish_flow - bearish_flow
    index = 50.0 + (net / total) * 50.0
    return max(0.0, min(100.0, index))


def interpret_oka_index(index: float) -> dict:
    """Devuelve etiqueta, descripción y color para un valor del OKA Index.

    Rangos del PDF:
        0–30  Bearish Extreme  (rojo oscuro)
        30–45 Bearish          (rojo)
        45–55 Neutral          (gris)
        55–70 Bullish          (verde)
        70–100 Bullish Extreme (verde oscuro)

    Returns:
        dict con 'label', 'description', 'color', 'emoji'.
    """
    if index < 30:
        return {
            "label": "Bearish Extreme",
            "description": "Flujo institucional bajista extremo. Presión vendedora dominante.",
            "color": "#7f1d1d",
            "text_color": "#fca5a5",
            "emoji": "🔴",
        }
    if index < 45:
        return {
            "label": "Bearish",
            "description": "Flujo institucional mayormente bajista. Cautela recomendada.",
            "color": "#dc2626",
            "text_color": "#f87171",
            "emoji": "🟠",
        }
    if index <= 55:
        return {
            "label": "Neutral",
            "description": "Flujo institucional mixto. Sin señal direccional clara.",
            "color": "#475569",
            "text_color": "#94a3b8",
            "emoji": "⚪",
        }
    if index <= 70:
        return {
            "label": "Bullish",
            "description": "Flujo institucional mayormente alcista. Presión compradora activa.",
            "color": "#16a34a",
            "text_color": "#86efac",
            "emoji": "🟢",
        }
    return {
        "label": "Bullish Extreme",
        "description": "Flujo institucional alcista extremo. Fuerte acumulación institucional.",
        "color": "#14532d",
        "text_color": "#4ade80",
        "emoji": "🚀",
    }


# ---------------------------------------------------------------------------
#   DATA FETCHING — proveedor con fallback mock
# ---------------------------------------------------------------------------

def _fetch_option_flow(
    symbol: str,
    lookback_minutes: int = 60,
) -> list[dict]:
    """Construye flujo sintético desde cadenas de opciones para el índice OKA.

    Convierte opciones con volumen en una lista de trades normalizados
    compatible con el pipeline institucional existente.
    """
    trades: list[dict] = []
    try:
        expirations = list(fetch_options_dates(symbol))[:2]
    except Exception as exc:
        logger.error("Error obteniendo expiraciones: %s", exc)
        return trades

    if not expirations:
        return trades

    spot, _ = obtener_precio_actual(symbol)
    spot_price = float(spot or 0)

    for exp in expirations:
        try:
            _, chain_data, err = fetch_single_chain(symbol, exp)
            if err or not chain_data:
                continue

            exp_date = datetime.strptime(exp, "%Y-%m-%d")
            dte = max((exp_date - datetime.now()).days, 1)

            for option_type, key in (("call", "calls"), ("put", "puts")):
                df = chain_data.get(key)
                if df is None or getattr(df, "empty", True):
                    continue

                for _, row in df.iterrows():
                    strike = float(row.get("strike", 0) or 0)
                    volume = float(row.get("volume", 0) or 0)
                    oi = float(row.get("openInterest", 0) or 0)
                    bid = float(row.get("bid", 0) or 0)
                    ask = float(row.get("ask", 0) or 0)
                    price = float(row.get("lastPrice", 0) or 0)
                    if price <= 0:
                        price = ask if ask > 0 else bid
                    iv = float(row.get("impliedVolatility", 0) or 0)
                    if iv > 1:
                        iv /= 100.0

                    if strike <= 0 or volume <= 0 or price <= 0:
                        continue

                    base_spot = spot_price if spot_price > 0 else strike
                    T = max(dte / 365.0, 1 / 365.0)
                    delta = _approx_delta(base_spot, strike, T, iv or 0.25, option_type)
                    gamma_val = _approx_gamma(base_spot, strike, T, iv or 0.25)

                    trades.append(
                        {
                            "symbol": f"{symbol.upper()}_{exp}_{strike:.0f}{option_type[0].upper()}",
                            "ticker": symbol.upper(),
                            "option_type": option_type,
                            "strike": strike,
                            "expiration": exp,
                            "price": round(price, 2),
                            "size": volume,
                            "volume": volume,
                            "open_interest": oi,
                            "bid": round(bid, 2),
                            "ask": round(ask if ask > 0 else price, 2),
                            "delta": round(float(delta), 4),
                            "gamma": round(float(gamma_val), 6),
                            "iv": round(float(iv or 0.25), 4),
                            "sweep_flag": None,
                            "spot": base_spot,
                            "dte": dte,
                        }
                    )
        except Exception as exc:
            logger.warning("Error construyendo flujo para %s %s: %s", symbol, exp, exc)
            continue

    return trades


def _generate_mock_trades(symbol: str, n: int = 100) -> list[dict]:
    """Genera trades mock realistas para demo sin API key.

    Produce una mezcla de flujo institucional (~55 %) y ruido retail (~45 %)
    para que los filtros institucionales dejen pasar suficientes trades y la
    demo muestre un OKA Index dinámico.
    """
    import random
    rng = random.Random(int(time.time()) // 30)   # cambia cada 30s (demo live)

    spot_prices = {
        "SPY": 597, "QQQ": 520, "IWM": 210, "NVDA": 135, "TSLA": 345,
        "AAPL": 215, "AMD": 120, "MSFT": 445, "AMZN": 210, "META": 640,
        "GOOGL": 175, "NFLX": 1050, "BA": 195, "GLD": 300,
    }
    spot = float(spot_prices.get(symbol.upper(), 400))

    trades: list[dict] = []
    for i in range(n):
        # ── Decide si es trade institucional (~55 %) o retail ─────────
        is_institutional = rng.random() < 0.55

        is_call  = rng.random() > 0.45
        opt_type = "call" if is_call else "put"

        if is_institutional:
            # ATM / NTM strikes, alto volumen, sweep frecuente
            offset  = rng.uniform(-0.03, 0.03)
            strike  = round(spot * (1 + offset) / 5) * 5
            dte     = rng.choice([7, 14, 21, 30, 45])
            iv      = rng.uniform(0.18, 0.40)
            volume  = rng.choice([300, 500, 800, 1000, 1500, 2000, 3000, 5000])
            # Volumen inusual: OI menor que volumen  (señal institucional)
            oi      = rng.randint(max(1, int(volume * 0.10)), int(volume * 0.85))
            is_sweep = rng.random() < 0.70      # 70 % sweeps
        else:
            # Retail: OTM, bajo volumen, poco sweep
            offset  = rng.uniform(-0.08, 0.08)
            strike  = round(spot * (1 + offset) / 5) * 5
            dte     = rng.choice([7, 14, 21, 30, 45, 60])
            iv      = rng.uniform(0.20, 0.55)
            volume  = rng.choice([5, 10, 25, 50, 100, 200])
            oi      = rng.randint(int(volume * 1), int(volume * 8))
            is_sweep = rng.random() < 0.15      # 15 % sweeps

        T         = dte / 365.0
        delta_val = _approx_delta(spot, strike, T, iv, opt_type)
        gamma_val = _approx_gamma(spot, strike, T, iv)

        # Precio más realista: base = |delta| × spot × factor
        base_price = max(0.10, abs(delta_val) * spot * rng.uniform(0.012, 0.04))
        spread     = base_price * rng.uniform(0.02, 0.08)
        bid        = max(0.05, base_price - spread / 2)
        ask        = base_price + spread / 2

        # 60 % de trades son agresivos (buy o sell)
        aggr_rnd = rng.random()
        if aggr_rnd < 0.35:
            price = ask + rng.uniform(0, 0.03)   # aggressive buy
        elif aggr_rnd < 0.60:
            price = max(0.01, bid - rng.uniform(0, 0.03))   # aggressive sell
        else:
            price = (bid + ask) / 2               # neutral

        exp_date = (datetime.now() + timedelta(days=dte)).strftime("%Y-%m-%d")

        trades.append({
            "symbol":        f"{symbol.upper()}_{exp_date}_{strike:.0f}{opt_type[0].upper()}",
            "ticker":        symbol.upper(),
            "option_type":   opt_type,
            "strike":        strike,
            "expiration":    exp_date,
            "price":         round(price, 2),
            "size":          volume,
            "volume":        volume,
            "open_interest": oi,
            "bid":           round(bid, 2),
            "ask":           round(ask, 2),
            "delta":         round(delta_val, 4),
            "gamma":         round(gamma_val, 6),
            "iv":            round(iv, 4),
            "sweep_flag":    is_sweep,
            "spot":          spot,
            "dte":           dte,
        })

    return trades


# ---------------------------------------------------------------------------
#   PIPELINE PRINCIPAL — compute_oka_index
# ---------------------------------------------------------------------------

def compute_oka_index(
    symbol: str,
    gamma_weighting: bool = False,
    lookback_minutes: int = 60,
    use_mock: bool | None = None,
) -> dict:
    """Pipeline completo del OKA Sentiment Index v2.

    Pasos:
        1. Fetch trades (proveedor o mock)
        2. Enriquecer con greeks si faltan
        3. Classify aggression
        4. Apply institutional filters
        5. Calculate premium + DWP
        6. Classify direction
        7. Compute OKA Index

    Args:
        symbol:           ticker subyacente (ej 'SPY').
        gamma_weighting:  Phase 2 — usar GammaAdjusted en vez de DWP.
        lookback_minutes: ventana temporal en minutos (default 60).
        use_mock:         forzar mock (True) / real (False) / auto (None).

    Returns:
        dict con:
            oka_index          — float 0-100
            bullish_flow       — $ flujo alcista total
            bearish_flow       — $ flujo bajista total
            net_flow           — $ flujo neto
            total_flow         — $ flujo total
            interpretation     — dict con label, description, color, emoji
            institutional_trades — lista de trades que pasaron filtros
            total_raw_trades   — número de trades crudos analizados
            total_institutional — número de trades institucionales
            timestamp          — str ISO del momento de cálculo
            gamma_weighting    — bool (Phase 2 activo o no)
            symbol             — str ticker
    """
    # ── 1. Fetch ──────────────────────────────────────────────────────────
    _use_mock = bool(use_mock) if use_mock is not None else False

    if _use_mock:
        raw_trades = _generate_mock_trades(symbol, n=120)
    else:
        raw_trades = _fetch_option_flow(symbol, lookback_minutes)
        if not raw_trades:
            raw_trades = _generate_mock_trades(symbol, n=120)

    total_raw = len(raw_trades)

    # ── 2. Enriquecer con greeks si faltan ────────────────────────────────
    for t in raw_trades:
        if t.get("delta") is None:
            spot = float(t.get("spot", 550))
            T    = max(float(t.get("dte", 30)) / 365.0, 1 / 365.0)
            iv   = float(t.get("iv", 0.25) or 0.25)
            t["delta"] = _approx_delta(spot, t["strike"], T, iv, t["option_type"])
        if t.get("gamma") is None:
            spot = float(t.get("spot", 550))
            T    = max(float(t.get("dte", 30)) / 365.0, 1 / 365.0)
            iv   = float(t.get("iv", 0.25) or 0.25)
            t["gamma"] = _approx_gamma(spot, t["strike"], T, iv)

    # ── 3. Classify aggression ────────────────────────────────────────────
    for t in raw_trades:
        t["aggression"] = classify_aggression(
            float(t.get("price", 0) or 0),
            float(t.get("bid",   0) or 0),
            float(t.get("ask",   0) or 0),
        )

    # ── 4. Institutional filters ──────────────────────────────────────────
    inst_trades = apply_institutional_filters(raw_trades)
    total_inst  = len(inst_trades)

    # ── 5. Premium + DWP ─────────────────────────────────────────────────
    bullish_flow = 0.0
    bearish_flow = 0.0

    for t in inst_trades:
        price   = float(t.get("price",  0) or 0)
        volume  = float(t.get("size", t.get("volume", 0)) or 0)
        delta   = float(t.get("delta", 0) or 0)
        gamma_t = float(t.get("gamma", 0) or 0)

        premium = calculate_premium(price, volume)
        dwp     = calculate_delta_weighted_premium(
            premium, delta, gamma_t, gamma_weighting=gamma_weighting
        )

        t["premium"]        = round(premium, 2)
        t["delta_weighted"] = round(dwp, 2)

        # ── 6. Direction ─────────────────────────────────────────────────
        direction = classify_direction(t)
        t["direction"] = direction

        if direction == "bullish":
            bullish_flow += dwp
        elif direction == "bearish":
            bearish_flow += dwp

    # ── 7. OKA Index ──────────────────────────────────────────────────────
    oka_idx        = calculate_oka_index(bullish_flow, bearish_flow)
    interpretation = interpret_oka_index(oka_idx)
    net_flow       = bullish_flow - bearish_flow
    total_flow     = bullish_flow + bearish_flow

    # Ordenar por premium desc para mostrar los más grandes primero
    inst_trades_sorted = sorted(inst_trades, key=lambda x: x.get("delta_weighted", 0), reverse=True)

    return {
        "oka_index":            round(oka_idx, 2),
        "bullish_flow":         bullish_flow,
        "bearish_flow":         bearish_flow,
        "net_flow":             net_flow,
        "total_flow":           total_flow,
        "interpretation":       interpretation,
        "institutional_trades": inst_trades_sorted[:50],  # top 50
        "total_raw_trades":     total_raw,
        "total_institutional":  total_inst,
        "timestamp":            datetime.now().isoformat(timespec="seconds"),
        "gamma_weighting":      gamma_weighting,
        "symbol":               symbol.upper(),
    }
