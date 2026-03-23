# -*- coding: utf-8 -*-
"""
CreditSpreadService — capa de servicio para el scanner de venta de prima.

Principios aplicados:
- Cero imports de Streamlit (100 % testeable sin UI)
- Recibe parámetros explícitos, devuelve entidades tipadas
- Delega I/O a la capa de infraestructura (scanner.py / cache.py)
- Toda la lógica de negocio vive aquí; la página sólo llama este servicio
- Compatible con async (todos los métodos se pueden envolver con ``asyncio``)
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

import pandas as pd

from config.constants import (
    ALERT_DEFAULT_ACCOUNT_SIZE,
    CS_WHITELIST,
    OPP_SCORE_MIN_SHOW,
)
from config.settings import get_settings
from core.credit_spread_scanner import (
    scan_credit_spreads as _scan,
    generate_alerts as _gen_alerts,
    opportunity_score_breakdown as _score_breakdown,
    compute_income_score as _income_score,
    compute_opportunity_score as _opp_score,
    calculate_probability_of_touch,          # Fase 1 — PoT
)
from core.intelligence_layer import (
    IntelligenceWeights,
    dispatch_smart_alerts,
    enrich_scanner_dataframe,
    filter_smart_alerts,
)
from core.autonomy.personalization import AdaptivePersonalizationEngine
from core.autonomy.safety import SafetyGuardrails
from core.autonomy.shadow import ShadowDeploymentEngine
from infrastructure.platform.business_value import is_feature_enabled_for_user

logger = logging.getLogger(__name__)

_personalization = AdaptivePersonalizationEngine()
_safety = SafetyGuardrails()
_shadow = ShadowDeploymentEngine()


class CreditSpreadService:
    """Orquesta el escaneo de credit spreads y la generación de alertas.

    Esta clase es el **único punto de acceso** de la capa de presentación
    al scanner.  Encapsula los parámetros por defecto y normaliza
    la interfaz de salida.

    Ejemplo de uso en una página::

        svc = CreditSpreadService()
        df, indicators = svc.scan(tickers=["SPY", "QQQ"], strict=True)
        alerts = svc.get_alerts(df, account_size=10_000)
    """

    # ── Whitelist accesible para la UI ─────────────────────────────────
    WHITELIST: list[str] = list(CS_WHITELIST)

    def scan(
        self,
        tickers: list[str],
        min_pop: float = 0.70,
        max_dte: int = 45,
        min_credit: float = 0.30,
        strict: bool = True,
        strict_rules: dict | None = None,
        account_size: float = ALERT_DEFAULT_ACCOUNT_SIZE,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        user_plan: str = "free",
        user_id: str = "",
        user_cohort: int | None = None,
        auth: Any | None = None,
    ) -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
        """Ejecuta el scanner completo y devuelve DataFrame + indicadores por ticker.

        Args:
            tickers: lista de símbolos a escanear.
            min_pop: probabilidad mínima de ganancia (0-1).
            max_dte: máximo de DTE.
            min_credit: crédito mínimo en USD.
            strict: si True, aplica los 9 filtros del pipeline.
            strict_rules: reglas individuales activadas (prioridad sobre strict).
            account_size: tamaño de cuenta para cálculo de riesgo.
            progress_callback: fn(ticker, idx, total) para reportar progreso.

        Returns:
            (df, ticker_indicators):
                df — DataFrame con todas las oportunidades encontradas.
                ticker_indicators — dict {ticker: {iv_rank, trend, price, …}}.
        """
        logger.info(
            "CreditSpreadService.scan — tickers=%s, strict=%s, pop>=%.0f%%",
            tickers, strict, min_pop * 100,
        )
        df, ticker_indicators = _scan(
            tickers=tickers,
            min_pop=min_pop,
            max_dte=max_dte,
            min_credit=min_credit,
            progress_callback=progress_callback,
            strict=strict,
            strict_rules=strict_rules,
        )

        if df is not None and not df.empty and is_feature_enabled_for_user(
            feature_name="advanced_score",
            plan=user_plan,
            user_id=user_id,
            cohort=user_cohort,
        ):
            cfg = get_settings()
            weights = IntelligenceWeights(
                liquidity=float(cfg.intelligence_score_weight_liquidity),
                bid_ask=float(cfg.intelligence_score_weight_bid_ask),
                relative_iv=float(cfg.intelligence_score_weight_relative_iv),
                oi_volume=float(cfg.intelligence_score_weight_oi_volume),
                strike_distance=float(cfg.intelligence_score_weight_strike_distance),
                estimated_risk=float(cfg.intelligence_score_weight_estimated_risk),
            )
            df = enrich_scanner_dataframe(df, weights=weights)

            if not is_feature_enabled_for_user(
                feature_name="explainability",
                plan=user_plan,
                user_id=user_id,
                cohort=user_cohort,
            ):
                for col in [
                    "Explicacion Ejecutiva",
                    "Senales Positivas",
                    "Senales Negativas",
                    "Riesgos Clave",
                ]:
                    if col in df.columns:
                        df = df.drop(columns=[col])

            if auth is not None and user_id:
                profile = _personalization.infer_profile(auth, user_id)
                df = _personalization.personalize_ranking(df, profile)

            # Shadow execution in parallel against current ordering as quality/cost/latency guardrail preview.
            shadow_cmp = _shadow.compare(
                current_fn=lambda x: x.sort_values("Score Oportunidad", ascending=False)
                if "Score Oportunidad" in x.columns else x,
                candidate_fn=lambda x: x.sort_values(
                    ["Score Unificado", "Score Oportunidad"], ascending=[False, False]
                ) if "Score Unificado" in x.columns else x,
                df=df,
                cost_current_usd=0.001,
                cost_candidate_usd=0.0016,
            )
            ticker_indicators["_shadow"] = {
                "quality_delta": shadow_cmp.quality_delta,
                "latency_delta_ms": shadow_cmp.latency_delta_ms,
                "cost_delta_usd": shadow_cmp.cost_delta_usd,
                "promoted": shadow_cmp.promoted,
                "reason": shadow_cmp.reason,
            }

        return df, ticker_indicators

    def get_alerts(
        self,
        df: pd.DataFrame,
        account_size: float = ALERT_DEFAULT_ACCOUNT_SIZE,
        strict_rules: dict | None = None,
        user_plan: str = "free",
        user_id: str = "",
        user_cohort: int | None = None,
        alert_preferences: dict[str, Any] | None = None,
        external_hook: Optional[Callable[[list[dict[str, Any]]], Any]] = None,
        auth: Any | None = None,
    ) -> pd.DataFrame:
        """Aplica las reglas de seguridad y devuelve las alertas accionables.

        Las reglas respetan strict_rules: las desactivadas se saltan.
        La Regla 8 (riesgo de cuenta) siempre se verifica.
        """
        if df is None or df.empty:
            return pd.DataFrame()
        alerts = _gen_alerts(df, account_size=account_size, strict_rules=strict_rules)

        if alerts is None or alerts.empty:
            return pd.DataFrame()

        if is_feature_enabled_for_user(
            feature_name="smart_alerts",
            plan=user_plan,
            user_id=user_id,
            cohort=user_cohort,
        ):
            cfg = get_settings()
            prefs = {
                "min_score": cfg.smart_alert_min_score_default,
                "dte_min": cfg.smart_alert_dte_min_default,
                "dte_max": cfg.smart_alert_dte_max_default,
                "max_spread": cfg.smart_alert_max_spread_default,
                "min_premium": cfg.smart_alert_min_premium_default,
            }
            if alert_preferences:
                prefs.update(alert_preferences)
            alerts = filter_smart_alerts(alerts, preferences=prefs)
            dispatch_smart_alerts(alerts, external_hook=external_hook)

        alerts = _safety.enforce(alerts)

        if auth is not None and user_id and not alerts.empty:
            profile = _personalization.load_profile(auth, user_id)
            alerts = _personalization.personalize_ranking(alerts, profile)

        return alerts

    def score_breakdown(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        """Devuelve el desglose de puntaje para un spread específico.

        Útil para el panel educativo / hover card de la tabla de resultados.

        Args:
            row: dict con los datos de un spread (como sale del DataFrame).

        Returns:
            Lista de dicts con criterio, detalle, puntos, maximo, cumple.
        """
        return _score_breakdown(row)

    def compute_scores(self, row: dict[str, Any]) -> dict[str, Any]:
        """Calcula ambos scores (Income + Oportunidad) para un spread.

        Args:
            row: dict con los datos de un spread.

        Returns:
            dict con income_score, income_label, opp_score, opp_label.
        """
        inc_score, inc_label = _income_score(row)
        opp_score, opp_label = _opp_score(row)
        return {
            "income_score": inc_score,
            "income_label": inc_label,
            "opp_score": opp_score,
            "opp_label": opp_label,
        }

    @staticmethod
    def filter_by_score(
        df: pd.DataFrame,
        min_score: int = OPP_SCORE_MIN_SHOW,
    ) -> pd.DataFrame:
        """Filtra el DataFrame de resultados por Score de Oportunidad mínimo.

        Args:
            df: DataFrame de resultados del scanner.
            min_score: score mínimo para incluir (default: 60).

        Returns:
            DataFrame filtrado (copia).
        """
        if df is None or df.empty:
            return pd.DataFrame()
        col = "Score Oportunidad"
        if col not in df.columns:
            return df
        return df[df[col] >= min_score].copy()
