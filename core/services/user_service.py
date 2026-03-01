# -*- coding: utf-8 -*-
"""
UserService — capa de servicio para gestión de usuarios, favoritos y watchlists.

Principios aplicados:
- Sin imports de Streamlit → 100 % testeable
- Recibe el objeto auth como dependencia inyectada (DI)
- Métodos atómicos y bien nombrados
- Logging de todas las operaciones críticas
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from core.entities import User, UserRole, UserStats

logger = logging.getLogger(__name__)


class UserService:
    """Gestión de datos del usuario: perfil, estadísticas, favoritos, watchlist.

    Recibe una instancia de SupabaseAuth como dependencia inyectada para
    que la capa de infraestructura sea intercambiable en tests.

    Ejemplo::

        from core.auth import SupabaseAuth
        svc = UserService(auth=SupabaseAuth())
        user = svc.get_current_user()
        stats = svc.get_stats(user.id)
    """

    def __init__(self, auth: Any) -> None:
        """
        Args:
            auth: instancia de SupabaseAuth (o cualquier objeto con la
                  misma interfaz de métodos).
        """
        self._auth = auth

    # ── Perfil ─────────────────────────────────────────────────────────

    def get_current_user(self) -> Optional[User]:
        """Devuelve el Usuario autenticado actual como entidad tipada."""
        raw = self._auth.get_current_user()
        if not raw:
            return None
        return User.from_auth_dict(raw)

    def update_display_name(self, user_id: str, new_name: str) -> bool:
        """Actualiza el nombre de visualización del usuario.

        Returns:
            True si la operación fue exitosa.
        """
        try:
            self._auth.update_user_profile({"name": new_name.strip()})
            logger.info("Nombre actualizado para user %s", user_id)
            return True
        except Exception as exc:
            logger.error("Error actualizando nombre: %s", exc)
            return False

    def request_password_reset(self, email: str) -> bool:
        """Envía email de reset de contraseña."""
        try:
            self._auth.send_password_reset(email)
            return True
        except Exception as exc:
            logger.error("Error enviando reset: %s", exc)
            return False

    # ── Estadísticas ───────────────────────────────────────────────────

    def get_stats(self, user_id: str) -> UserStats:
        """Carga estadísticas de uso del usuario desde Supabase."""
        raw = self._auth.load_user_data(user_id, "usage_stats") or {}
        return UserStats.from_dict(raw) if raw else UserStats()

    def increment_scan_count(self, user_id: str) -> None:
        """Incrementa contadores de scans: hoy + mes + total."""
        try:
            raw = self._auth.load_user_data(user_id, "usage_stats") or {}
            today = datetime.utcnow().strftime("%Y-%m-%d")
            month_key = datetime.utcnow().strftime("%Y-%m")

            # Reset diario
            if raw.get("scans_today_date") != today:
                raw["scans_today"] = 0
                raw["scans_today_date"] = today
            raw["scans_today"] = raw.get("scans_today", 0) + 1

            # Reset mensual
            if raw.get("scans_month_key") != month_key:
                raw["scans_month"] = 0
                raw["scans_month_key"] = month_key
            raw["scans_month"] = raw.get("scans_month", 0) + 1

            # Total acumulado (opcional, para historial)
            raw["scans_total"] = raw.get("scans_total", 0) + 1

            self._auth.save_user_data(user_id, "usage_stats", raw)
            logger.info(
                "Scan registrado para %s — hoy: %d, mes: %d, total: %d",
                user_id, raw["scans_today"], raw["scans_month"], raw["scans_total"],
            )
        except Exception as exc:
            logger.warning("Error incrementando scan_count: %s", exc)

    def record_login(self, user_id: str) -> None:
        """Registra un nuevo login en las estadísticas."""
        try:
            stats = self.get_stats(user_id)
            stats.logins_total += 1
            stats.last_login = datetime.utcnow()
            self._auth.save_user_data(user_id, "usage_stats", stats.to_dict())
        except Exception as exc:
            logger.warning("Error registrando login: %s", exc)

    def increment_report_count(self, user_id: str) -> None:
        """Incrementa el contador de reportes generados."""
        try:
            raw = self._auth.load_user_data(user_id, "usage_stats") or {}
            raw["reports_generated"] = raw.get("reports_generated", 0) + 1
            self._auth.save_user_data(user_id, "usage_stats", raw)
            logger.info("Reporte registrado para %s — total: %d", user_id, raw["reports_generated"])
        except Exception as exc:
            logger.warning("Error incrementando report_count: %s", exc)

    # ── Favoritos ──────────────────────────────────────────────────────

    def load_favorites(self, user_id: str) -> list[dict]:
        """Carga favoritos desde Supabase para el usuario."""
        try:
            data = self._auth.load_user_data(user_id, "favoritos")
            return data if isinstance(data, list) else []
        except Exception as exc:
            logger.warning("Error cargando favoritos: %s", exc)
            return []

    def save_favorites(self, user_id: str, favorites: list[dict]) -> bool:
        """Persiste la lista de favoritos en Supabase."""
        try:
            self._auth.save_user_data(user_id, "favoritos", favorites)
            return True
        except Exception as exc:
            logger.error("Error guardando favoritos: %s", exc)
            return False

    # ── Watchlist ──────────────────────────────────────────────────────

    def load_watchlist(self, user_id: str) -> list[dict]:
        """Carga watchlist desde Supabase para el usuario."""
        try:
            data = self._auth.load_user_data(user_id, "watchlist")
            return data if isinstance(data, list) else []
        except Exception as exc:
            logger.warning("Error cargando watchlist: %s", exc)
            return []

    def save_watchlist(self, user_id: str, watchlist: list[dict]) -> bool:
        """Persiste la watchlist en Supabase."""
        try:
            self._auth.save_user_data(user_id, "watchlist", watchlist)
            return True
        except Exception as exc:
            logger.error("Error guardando watchlist: %s", exc)
            return False
