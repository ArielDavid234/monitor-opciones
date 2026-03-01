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
    from dataclasses import dataclass, field

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
