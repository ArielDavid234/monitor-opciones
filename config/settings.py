# -*- coding: utf-8 -*-
"""
Configuración centralizada del proyecto con Pydantic Settings.

Todas las variables de entorno y secrets se leen aquí una sola vez.
El resto del código importa desde este módulo — nunca lee st.secrets
directamente (excepto en infrastructure/auth/).

Capas del sistema:
  config/   → settings + constants (este módulo)
  core/     → dominio puro (entities, services, repository ABCs)
  infra/    → Supabase, Redis, yfinance, Barchart
  present./ → UI Streamlit (cero lógica de negocio)
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic v2 compatible — graceful fallback to plain dataclass if unavailable
# ---------------------------------------------------------------------------
try:
    from pydantic import Field
    from pydantic_settings import BaseSettings  # pydantic-settings ≥ 2.0

    class AppSettings(BaseSettings):
        """Configuración de la aplicación leída de variables de entorno / secrets."""

        # ── Supabase ───────────────────────────────────────────────────────
        supabase_url: str = Field(default="", alias="SUPABASE_URL")
        supabase_anon_key: str = Field(default="", alias="SUPABASE_ANON_KEY")

        # ── Redis (opcional) ───────────────────────────────────────────────
        redis_url: Optional[str] = Field(default=None, alias="REDIS_URL")

        # ── Cache ──────────────────────────────────────────────────────────
        cache_ttl_seconds: int = Field(default=720, alias="CACHE_TTL")
        cache_max_memory_entries: int = Field(default=512, alias="CACHE_MAX_ENTRIES")

        # ── Scanner ────────────────────────────────────────────────────────
        scanner_max_expirations: int = Field(default=12, alias="SCANNER_MAX_EXP")
        scanner_auto_refresh_secs: int = Field(default=600, alias="AUTO_REFRESH")

        # ── Data providers ─────────────────────────────────────────────────
        data_provider: str = Field(default="databento", alias="DATA_PROVIDER")
        databento_api_key: str = Field(default="", alias="DATABENTO_API_KEY")
        chain_fetch_max_workers: int = Field(default=6, alias="CHAIN_FETCH_MAX_WORKERS")
        databento_quota_total_per_min: int = Field(default=240, alias="DATABENTO_QUOTA_TOTAL_PER_MIN")
        databento_quota_reserved_live_scanning: int = Field(
            default=160,
            alias="DATABENTO_QUOTA_RESERVED_LIVE_SCANNING",
        )
        databento_quota_background: int = Field(default=80, alias="DATABENTO_QUOTA_BACKGROUND")
        databento_quota_high_watermark: float = Field(default=0.85, alias="DATABENTO_QUOTA_HIGH_WATERMARK")
        scan_summary_every_n: int = Field(default=10, alias="SCAN_SUMMARY_EVERY_N")
        scan_alert_p90_ms: int = Field(default=60000, alias="SCAN_ALERT_P90_MS")
        scan_alert_429_5m: int = Field(default=25, alias="SCAN_ALERT_429_5M")
        scan_alert_cache_hit_ratio_min: float = Field(default=0.35, alias="SCAN_ALERT_CACHE_HIT_RATIO_MIN")
        snapshot_pipeline_enabled: bool = Field(default=True, alias="SNAPSHOT_PIPELINE_ENABLED")
        snapshot_warm_start_enabled: bool = Field(default=False, alias="SNAPSHOT_WARM_START_ENABLED")
        snapshot_warm_start_tickers: str = Field(default="SPY,QQQ,AAPL", alias="SNAPSHOT_WARM_START_TICKERS")
        snapshot_hot_interval_sec: int = Field(default=45, alias="SNAPSHOT_HOT_INTERVAL_SEC")
        snapshot_normal_interval_sec: int = Field(default=180, alias="SNAPSHOT_NORMAL_INTERVAL_SEC")
        snapshot_inactive_interval_sec: int = Field(default=600, alias="SNAPSHOT_INACTIVE_INTERVAL_SEC")
        snapshot_batch_size: int = Field(default=2, alias="SNAPSHOT_BATCH_SIZE")
        snapshot_degrade_usage_ratio: float = Field(default=0.9, alias="SNAPSHOT_DEGRADE_USAGE_RATIO")
        snapshot_price_fresh_sec: int = Field(default=60, alias="SNAPSHOT_PRICE_FRESH_SEC")
        snapshot_exp_fresh_sec: int = Field(default=300, alias="SNAPSHOT_EXP_FRESH_SEC")
        snapshot_chain_fresh_sec: int = Field(default=240, alias="SNAPSHOT_CHAIN_FRESH_SEC")
        snapshot_chain_min_ttl_sec: int = Field(default=60, alias="SNAPSHOT_CHAIN_MIN_TTL_SEC")
        snapshot_chain_max_ttl_sec: int = Field(default=900, alias="SNAPSHOT_CHAIN_MAX_TTL_SEC")
        snapshot_hard_ttl_sec: int = Field(default=1800, alias="SNAPSHOT_HARD_TTL_SEC")
        cross_user_dedupe_window_sec: int = Field(default=45, alias="CROSS_USER_DEDUPE_WINDOW_SEC")
        market_cache_version: str = Field(default="v1", alias="MARKET_CACHE_VERSION")
        market_schema_version: str = Field(default="v1", alias="MARKET_SCHEMA_VERSION")
        snapshot_schema_version: str = Field(default="v1", alias="SNAPSHOT_SCHEMA_VERSION")
        provider_circuit_failure_threshold: int = Field(default=5, alias="PROVIDER_CIRCUIT_FAILURE_THRESHOLD")
        provider_circuit_recovery_timeout_sec: int = Field(default=90, alias="PROVIDER_CIRCUIT_RECOVERY_TIMEOUT_SEC")
        provider_circuit_half_open_max_probe: int = Field(default=2, alias="PROVIDER_CIRCUIT_HALF_OPEN_MAX_PROBE")
        log_retention_days: int = Field(default=30, alias="LOG_RETENTION_DAYS")
        log_anonymize_user_ids: bool = Field(default=True, alias="LOG_ANONYMIZE_USER_IDS")
        error_budget_max_error_rate_pct_7d: float = Field(default=2.0, alias="ERROR_BUDGET_MAX_ERROR_RATE_PCT_7D")
        change_freeze_enabled: bool = Field(default=True, alias="CHANGE_FREEZE_ENABLED")
        cost_provider_call_usd: float = Field(default=0.0025, alias="COST_PROVIDER_CALL_USD")
        cost_cpu_second_usd: float = Field(default=0.0008, alias="COST_CPU_SECOND_USD")
        cost_cache_miss_usd: float = Field(default=0.0004, alias="COST_CACHE_MISS_USD")
        plan_price_free_monthly_usd: float = Field(default=0.0, alias="PLAN_PRICE_FREE_MONTHLY_USD")
        plan_price_pro_monthly_usd: float = Field(default=49.0, alias="PLAN_PRICE_PRO_MONTHLY_USD")
        plan_price_enterprise_monthly_usd: float = Field(default=299.0, alias="PLAN_PRICE_ENTERPRISE_MONTHLY_USD")
        intelligence_score_weight_liquidity: float = Field(default=0.20, alias="INTELLIGENCE_SCORE_WEIGHT_LIQUIDITY")
        intelligence_score_weight_bid_ask: float = Field(default=0.15, alias="INTELLIGENCE_SCORE_WEIGHT_BID_ASK")
        intelligence_score_weight_relative_iv: float = Field(default=0.15, alias="INTELLIGENCE_SCORE_WEIGHT_RELATIVE_IV")
        intelligence_score_weight_oi_volume: float = Field(default=0.20, alias="INTELLIGENCE_SCORE_WEIGHT_OI_VOLUME")
        intelligence_score_weight_strike_distance: float = Field(default=0.15, alias="INTELLIGENCE_SCORE_WEIGHT_STRIKE_DISTANCE")
        intelligence_score_weight_estimated_risk: float = Field(default=0.15, alias="INTELLIGENCE_SCORE_WEIGHT_ESTIMATED_RISK")
        feature_flag_advanced_score: bool = Field(default=True, alias="FEATURE_FLAG_ADVANCED_SCORE")
        feature_flag_explainability: bool = Field(default=True, alias="FEATURE_FLAG_EXPLAINABILITY")
        feature_flag_smart_alerts: bool = Field(default=True, alias="FEATURE_FLAG_SMART_ALERTS")
        feature_flag_auto_reports: bool = Field(default=True, alias="FEATURE_FLAG_AUTO_REPORTS")
        feature_rollout_advanced_score_pct: int = Field(default=100, alias="FEATURE_ROLLOUT_ADVANCED_SCORE_PCT")
        feature_rollout_explainability_pct: int = Field(default=100, alias="FEATURE_ROLLOUT_EXPLAINABILITY_PCT")
        feature_rollout_smart_alerts_pct: int = Field(default=100, alias="FEATURE_ROLLOUT_SMART_ALERTS_PCT")
        feature_rollout_auto_reports_pct: int = Field(default=100, alias="FEATURE_ROLLOUT_AUTO_REPORTS_PCT")
        smart_alert_min_score_default: int = Field(default=70, alias="SMART_ALERT_MIN_SCORE_DEFAULT")
        smart_alert_dte_min_default: int = Field(default=21, alias="SMART_ALERT_DTE_MIN_DEFAULT")
        smart_alert_dte_max_default: int = Field(default=50, alias="SMART_ALERT_DTE_MAX_DEFAULT")
        smart_alert_max_spread_default: float = Field(default=0.20, alias="SMART_ALERT_MAX_SPREAD_DEFAULT")
        smart_alert_min_premium_default: float = Field(default=0.30, alias="SMART_ALERT_MIN_PREMIUM_DEFAULT")

        # ── App ───────────────────────────────────────────────────────────
        app_title: str = "OPTIONSKING Analytics"
        app_icon: str = "\U0001f451"  # 👑
        log_level: str = Field(default="INFO", alias="LOG_LEVEL")
        debug: bool = Field(default=False, alias="DEBUG")

        class Config:
            env_file = ".env"
            env_file_encoding = "utf-8"
            populate_by_name = True

except ImportError:  # pydantic-settings no instalado → fallback
    import os  # noqa: F401
    from dataclasses import dataclass

    @dataclass
    class AppSettings:  # type: ignore[no-redef]
        """Fallback simple sin validación Pydantic."""

        supabase_url: str = ""
        supabase_anon_key: str = ""
        redis_url: Optional[str] = None
        cache_ttl_seconds: int = 720
        cache_max_memory_entries: int = 512
        scanner_max_expirations: int = 12
        scanner_auto_refresh_secs: int = 600
        data_provider: str = "databento"
        databento_api_key: str = ""
        chain_fetch_max_workers: int = 6
        databento_quota_total_per_min: int = 240
        databento_quota_reserved_live_scanning: int = 160
        databento_quota_background: int = 80
        databento_quota_high_watermark: float = 0.85
        scan_summary_every_n: int = 10
        scan_alert_p90_ms: int = 60000
        scan_alert_429_5m: int = 25
        scan_alert_cache_hit_ratio_min: float = 0.35
        snapshot_pipeline_enabled: bool = True
        snapshot_warm_start_enabled: bool = False
        snapshot_warm_start_tickers: str = "SPY,QQQ,AAPL"
        snapshot_hot_interval_sec: int = 45
        snapshot_normal_interval_sec: int = 180
        snapshot_inactive_interval_sec: int = 600
        snapshot_batch_size: int = 2
        snapshot_degrade_usage_ratio: float = 0.9
        snapshot_price_fresh_sec: int = 60
        snapshot_exp_fresh_sec: int = 300
        snapshot_chain_fresh_sec: int = 240
        snapshot_chain_min_ttl_sec: int = 60
        snapshot_chain_max_ttl_sec: int = 900
        snapshot_hard_ttl_sec: int = 1800
        cross_user_dedupe_window_sec: int = 45
        market_cache_version: str = "v1"
        market_schema_version: str = "v1"
        snapshot_schema_version: str = "v1"
        provider_circuit_failure_threshold: int = 5
        provider_circuit_recovery_timeout_sec: int = 90
        provider_circuit_half_open_max_probe: int = 2
        log_retention_days: int = 30
        log_anonymize_user_ids: bool = True
        error_budget_max_error_rate_pct_7d: float = 2.0
        change_freeze_enabled: bool = True
        cost_provider_call_usd: float = 0.0025
        cost_cpu_second_usd: float = 0.0008
        cost_cache_miss_usd: float = 0.0004
        plan_price_free_monthly_usd: float = 0.0
        plan_price_pro_monthly_usd: float = 49.0
        plan_price_enterprise_monthly_usd: float = 299.0
        intelligence_score_weight_liquidity: float = 0.20
        intelligence_score_weight_bid_ask: float = 0.15
        intelligence_score_weight_relative_iv: float = 0.15
        intelligence_score_weight_oi_volume: float = 0.20
        intelligence_score_weight_strike_distance: float = 0.15
        intelligence_score_weight_estimated_risk: float = 0.15
        feature_flag_advanced_score: bool = True
        feature_flag_explainability: bool = True
        feature_flag_smart_alerts: bool = True
        feature_flag_auto_reports: bool = True
        feature_rollout_advanced_score_pct: int = 100
        feature_rollout_explainability_pct: int = 100
        feature_rollout_smart_alerts_pct: int = 100
        feature_rollout_auto_reports_pct: int = 100
        smart_alert_min_score_default: int = 70
        smart_alert_dte_min_default: int = 21
        smart_alert_dte_max_default: int = 50
        smart_alert_max_spread_default: float = 0.20
        smart_alert_min_premium_default: float = 0.30
        app_title: str = "OPTIONSKING Analytics"
        app_icon: str = "\U0001f451"
        log_level: str = "INFO"
        debug: bool = False


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Instancia única de configuración (singleton vía lru_cache).

    Usar así en cualquier módulo::

        from config.settings import get_settings
        cfg = get_settings()
        print(cfg.app_title)
    """
    return AppSettings()


# Re-export conveniente
__all__ = ["AppSettings", "get_settings"]
