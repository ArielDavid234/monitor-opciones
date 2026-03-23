from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class AdaptiveUserProfile:
    risk_preference: str
    horizon_preference: str
    behavior_style: str


class AdaptivePersonalizationEngine:
    PROFILE_KEY = "autonomy_adaptive_profile"

    def infer_profile(self, auth: Any, user_id: str, events: list[dict[str, Any]] | None = None) -> AdaptiveUserProfile:
        rows = events if isinstance(events, list) else auth.load_user_data(user_id, "product_events")
        rows = rows if isinstance(rows, list) else []

        decision_scores: list[float] = []
        horizons: list[float] = []
        for row in rows:
            if row.get("event") != "scan_decision_made":
                continue
            meta = row.get("metadata", {}) or {}
            decision_scores.append(float(meta.get("score", 0.0) or 0.0))
            horizons.append(float(meta.get("dte", 0.0) or 0.0))

        avg_score = sum(decision_scores) / max(len(decision_scores), 1)
        avg_dte = sum(horizons) / max(len(horizons), 1)

        if avg_score >= 80 and avg_dte >= 30:
            risk = "Conservadora"
        elif avg_score >= 68:
            risk = "Balanceada"
        else:
            risk = "Agresiva"

        if avg_dte >= 40:
            horizon = "swing"
        elif avg_dte >= 21:
            horizon = "tactico"
        else:
            horizon = "corto_plazo"

        behavior = "disciplinado" if len(decision_scores) >= 5 else "exploratorio"

        profile = AdaptiveUserProfile(
            risk_preference=risk,
            horizon_preference=horizon,
            behavior_style=behavior,
        )
        auth.save_user_data(user_id, self.PROFILE_KEY, profile.__dict__)
        return profile

    def load_profile(self, auth: Any, user_id: str) -> AdaptiveUserProfile:
        row = auth.load_user_data(user_id, self.PROFILE_KEY)
        if not isinstance(row, dict):
            return AdaptiveUserProfile("Balanceada", "tactico", "exploratorio")
        try:
            return AdaptiveUserProfile(**row)
        except Exception:
            return AdaptiveUserProfile("Balanceada", "tactico", "exploratorio")

    def personalize_ranking(self, df: pd.DataFrame, profile: AdaptiveUserProfile) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame() if df is None else df

        out = df.copy()
        score_col = "Score Unificado" if "Score Unificado" in out.columns else "Score Oportunidad"
        if score_col not in out.columns:
            return out

        out["_personal_factor"] = 1.0
        if profile.risk_preference == "Conservadora":
            if "Perfil Riesgo" in out.columns:
                out.loc[out["Perfil Riesgo"] == "Conservadora", "_personal_factor"] += 0.08
                out.loc[out["Perfil Riesgo"] == "Agresiva", "_personal_factor"] -= 0.08
        elif profile.risk_preference == "Agresiva":
            if "Perfil Riesgo" in out.columns:
                out.loc[out["Perfil Riesgo"] == "Agresiva", "_personal_factor"] += 0.06

        if "DTE" in out.columns:
            if profile.horizon_preference == "corto_plazo":
                out.loc[pd.to_numeric(out["DTE"], errors="coerce").fillna(0) <= 21, "_personal_factor"] += 0.05
            elif profile.horizon_preference == "swing":
                out.loc[pd.to_numeric(out["DTE"], errors="coerce").fillna(0) >= 35, "_personal_factor"] += 0.05

        out["Score Personalizado"] = pd.to_numeric(out[score_col], errors="coerce").fillna(0.0) * out["_personal_factor"]
        out = out.sort_values(["Score Personalizado", score_col], ascending=[False, False]).drop(columns=["_personal_factor"]).reset_index(drop=True)
        return out
