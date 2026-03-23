from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd


@dataclass(frozen=True)
class IntelligenceWeights:
    liquidity: float = 0.20
    bid_ask: float = 0.15
    relative_iv: float = 0.15
    oi_volume: float = 0.20
    strike_distance: float = 0.15
    estimated_risk: float = 0.15

    def normalized(self) -> "IntelligenceWeights":
        total = (
            self.liquidity
            + self.bid_ask
            + self.relative_iv
            + self.oi_volume
            + self.strike_distance
            + self.estimated_risk
        )
        if total <= 0:
            return IntelligenceWeights()
        return IntelligenceWeights(
            liquidity=self.liquidity / total,
            bid_ask=self.bid_ask / total,
            relative_iv=self.relative_iv / total,
            oi_volume=self.oi_volume / total,
            strike_distance=self.strike_distance / total,
            estimated_risk=self.estimated_risk / total,
        )


def _num(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        value = row.get(key, default)
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, float(value)))


def _scale(value: float, low: float, high: float) -> float:
    if high <= low:
        return 50.0
    return _clamp(((value - low) / (high - low)) * 100.0)


def _inverse_scale(value: float, low: float, high: float) -> float:
    return 100.0 - _scale(value, low, high)


def _component_scores(row: dict[str, Any]) -> dict[str, float]:
    liquidity = _num(row, "Liq Score", 50.0)
    if liquidity <= 0:
        vol = _num(row, "Volumen", 0.0)
        oi = _num(row, "OI", 0.0)
        liquidity = 0.55 * _scale(oi, 100.0, 3000.0) + 0.45 * _scale(vol, 50.0, 2000.0)

    bid_ask = _num(row, "Bid-Ask", 0.0)
    credit = max(_num(row, "Crédito", 0.0), 0.01)
    bid_ask_ratio = bid_ask / credit
    bid_ask_score = _inverse_scale(bid_ask_ratio, 0.05, 0.35)

    relative_iv = _num(row, "IV Rank", 0.0)
    if relative_iv <= 0:
        iv_short = _num(row, "IV %", _num(row, "IV Short %", 0.0))
        hv = _num(row, "HV 20D", _num(row, "HV 20d", 0.0))
        rel = (iv_short / hv) if hv > 0 else 1.0
        relative_iv = _scale(rel, 0.8, 1.5)

    oi = _num(row, "OI", 0.0)
    vol = _num(row, "Volumen", 0.0)
    oi_volume = 0.55 * _scale(oi, 100.0, 5000.0) + 0.45 * _scale(vol, 50.0, 3000.0)

    strike_distance = _num(row, "Dist Strike %", 0.0)
    strike_distance_score = _scale(strike_distance, 1.0, 8.0)

    risk = _num(row, "Riesgo Máx", 0.0)
    risk_credit_ratio = (risk / credit) if credit > 0 else 10.0
    estimated_risk_score = _inverse_scale(risk_credit_ratio, 2.0, 8.0)

    return {
        "liquidity": _clamp(liquidity),
        "bid_ask": _clamp(bid_ask_score),
        "relative_iv": _clamp(relative_iv),
        "oi_volume": _clamp(oi_volume),
        "strike_distance": _clamp(strike_distance_score),
        "estimated_risk": _clamp(estimated_risk_score),
    }


def classify_risk_profile(row: dict[str, Any], component_scores: dict[str, float] | None = None) -> str:
    comp = component_scores or _component_scores(row)
    pop = _num(row, "POP %", 0.0)
    delta = abs(_num(row, "Delta Vendido", 0.0))
    dte = _num(row, "DTE", 0.0)
    credit = _num(row, "Crédito", 0.0)
    width = abs(_num(row, "Strike Vendido", 0.0) - _num(row, "Strike Comprado", 0.0))
    credit_ratio = (credit / width) if width > 0 else 0.0
    risk_score = comp.get("estimated_risk", 50.0)

    if pop >= 75.0 and delta <= 0.16 and dte <= 45.0 and risk_score >= 65.0:
        return "Conservadora"
    if pop < 68.0 or delta > 0.20 or credit_ratio >= 0.22 or risk_score < 45.0:
        return "Agresiva"
    return "Balanceada"


def build_explainability(row: dict[str, Any], component_scores: dict[str, float], unified_score: float) -> dict[str, Any]:
    positives: list[str] = []
    negatives: list[str] = []
    risks: list[str] = []

    pop = _num(row, "POP %", 0.0)
    dte = _num(row, "DTE", 0.0)
    bid_ask = _num(row, "Bid-Ask", 0.0)
    credit = max(_num(row, "Crédito", 0.0), 0.01)
    spread_pct = (bid_ask / credit) * 100.0

    if component_scores["liquidity"] >= 70:
        positives.append("Liquidez alta facilita entradas y salidas con menor friccion")
    elif component_scores["liquidity"] < 45:
        negatives.append("Liquidez baja puede complicar ejecucion o ajustes")

    if component_scores["bid_ask"] >= 70:
        positives.append("Bid/ask eficiente reduce costo oculto de ejecucion")
    elif component_scores["bid_ask"] < 45:
        negatives.append("Spread bid/ask amplio erosiona parte de la prima")

    if component_scores["relative_iv"] >= 65:
        positives.append("Volatilidad relativa favorece captura de prima")
    elif component_scores["relative_iv"] < 40:
        negatives.append("Volatilidad relativa baja limita edge estadistico")

    if component_scores["strike_distance"] >= 65:
        positives.append("Distancia al strike aporta colchon ante movimientos moderados")
    elif component_scores["strike_distance"] < 40:
        risks.append("Strike cercano aumenta probabilidad de presion temprana")

    if component_scores["estimated_risk"] < 45:
        risks.append("Relacion riesgo/premio exigente para gestion conservadora")

    if pop < 68:
        risks.append("POP bajo para criterios defensivos")
    if dte < 18:
        risks.append("DTE corto reduce margen de maniobra")
    if spread_pct > 20:
        risks.append("Bid/ask superior a 20% del credito")

    if unified_score >= 80:
        summary = "Setup de alta calidad para priorizar en ejecucion." 
    elif unified_score >= 65:
        summary = "Setup aceptable con puntos fuertes claros y riesgos controlables."
    else:
        summary = "Setup tactico: requiere seleccion cuidadosa y gestion activa."

    return {
        "summary": summary,
        "positives": positives[:3],
        "negatives": negatives[:3],
        "risks": risks[:3],
    }


def compute_unified_score(row: dict[str, Any], weights: IntelligenceWeights | None = None) -> tuple[float, dict[str, float], str, dict[str, Any]]:
    norm_w = (weights or IntelligenceWeights()).normalized()
    components = _component_scores(row)
    unified = (
        components["liquidity"] * norm_w.liquidity
        + components["bid_ask"] * norm_w.bid_ask
        + components["relative_iv"] * norm_w.relative_iv
        + components["oi_volume"] * norm_w.oi_volume
        + components["strike_distance"] * norm_w.strike_distance
        + components["estimated_risk"] * norm_w.estimated_risk
    )
    score = round(_clamp(unified), 1)
    profile = classify_risk_profile(row, components)
    explain = build_explainability(row, components, score)
    return score, components, profile, explain


def enrich_scanner_dataframe(df: pd.DataFrame, weights: IntelligenceWeights | None = None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame() if df is None else df

    out = df.copy()
    unified_scores: list[float] = []
    profiles: list[str] = []
    summaries: list[str] = []
    pos_signals: list[str] = []
    neg_signals: list[str] = []
    risk_signals: list[str] = []

    for row in out.to_dict("records"):
        score, components, profile, explain = compute_unified_score(row, weights=weights)
        unified_scores.append(score)
        profiles.append(profile)
        summaries.append(str(explain.get("summary", "")))
        pos_signals.append(" | ".join(explain.get("positives", [])))
        neg_signals.append(" | ".join(explain.get("negatives", [])))
        risk_signals.append(" | ".join(explain.get("risks", [])))

    out["Score Unificado"] = unified_scores
    out["Perfil Riesgo"] = profiles
    out["Explicacion Ejecutiva"] = summaries
    out["Senales Positivas"] = pos_signals
    out["Senales Negativas"] = neg_signals
    out["Riesgos Clave"] = risk_signals

    out = out.sort_values(
        ["Score Unificado", "Score Final", "Score Oportunidad"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    return out


def filter_smart_alerts(df: pd.DataFrame, preferences: dict[str, Any] | None = None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    prefs = preferences or {}

    min_score = float(prefs.get("min_score", 70.0))
    dte_min = int(prefs.get("dte_min", 21))
    dte_max = int(prefs.get("dte_max", 50))
    max_spread = float(prefs.get("max_spread", 0.20))
    min_premium = float(prefs.get("min_premium", 0.30))

    out = df.copy()
    score_col = "Score Unificado" if "Score Unificado" in out.columns else "Score Oportunidad"
    mask = (
        (out[score_col] >= min_score)
        & (out["DTE"] >= dte_min)
        & (out["DTE"] <= dte_max)
        & (out["Crédito"] >= min_premium)
    )

    if "Bid-Ask" in out.columns:
        mask = mask & (out["Bid-Ask"] <= max_spread)

    out = out[mask].copy()
    if out.empty:
        return out

    out["Alerta Inteligente"] = "Cumple score, DTE, spread max y prima minima"
    out = out.sort_values(score_col, ascending=False).reset_index(drop=True)
    return out


def dispatch_smart_alerts(
    alerts_df: pd.DataFrame,
    external_hook: Callable[[list[dict[str, Any]]], Any] | None = None,
) -> dict[str, Any]:
    if alerts_df is None or alerts_df.empty:
        return {"delivered": 0, "external_status": "skipped"}

    payload = alerts_df.to_dict("records")
    status = "skipped"
    if external_hook is not None:
        try:
            external_hook(payload)
            status = "ok"
        except Exception:
            status = "failed"
    return {"delivered": len(payload), "external_status": status}
