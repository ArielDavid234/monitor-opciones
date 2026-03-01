# -*- coding: utf-8 -*-
"""
SupabaseRepository — implementación concreta del repositorio de datos de usuario.

Abstrae todas las llamadas a Supabase en un solo lugar, siguiendo el
patrón Repository para que la capa de servicios sea agnóstica al backend.

Cumple el contrato de ``core.protocols.UserRepository``.

Si en el futuro se cambia Supabase por otro proveedor, sólo hay que reemplazar
esta clase sin tocar ninguna página ni servicio.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from core.protocols import AuthProvider

logger = logging.getLogger(__name__)


class SupabaseRepository:
    """Repositorio de datos de usuario sobre Supabase.

    Implementa el protocolo ``UserRepository`` de ``core.protocols``.
    Wraps the low-level SupabaseAuth client methods and exposes
    a clean, strongly-typed interface for the service layer.

    Todos los métodos son sync para mantener compatibilidad con Streamlit;
    están preparados para ser convertidos a async cuando el runtime lo permita.
    """

    def __init__(self, auth: "AuthProvider") -> None:
        """
        Args:
            auth: instancia que cumpla el protocolo ``AuthProvider``
                  (normalmente ``core.auth.SupabaseAuth``).
        """
        self._auth = auth

    # ── User data (genérico llave-valor) ───────────────────────────────

    def load(self, user_id: str, key: str) -> Optional[Any]:
        """Lee un valor del almacén de datos de usuario en Supabase.

        Args:
            user_id: UUID del usuario.
            key: clave del dato (p.ej. "favoritos", "watchlist", "usage_stats").

        Returns:
            El valor almacenado, o None si no existe / hay error.
        """
        try:
            return self._auth.load_user_data(user_id, key)
        except Exception as exc:
            logger.error("SupabaseRepository.load(%s, %s): %s", user_id, key, exc)
            return None

    def save(self, user_id: str, key: str, value: Any) -> bool:
        """Escribe un valor en el almacén de datos de usuario en Supabase.

        Args:
            user_id: UUID del usuario.
            key: clave del dato.
            value: valor serializable (dict, list, str, int…).

        Returns:
            True si la escritura fue exitosa.
        """
        try:
            self._auth.save_user_data(user_id, key, value)
            logger.debug("SupabaseRepository.save(%s, %s) OK", user_id, key)
            return True
        except Exception as exc:
            logger.error("SupabaseRepository.save(%s, %s): %s", user_id, key, exc)
            return False

    # ── Convenience methods ────────────────────────────────────────────

    def load_list(self, user_id: str, key: str) -> list[Any]:
        """Igual que ``load()`` pero garantiza devolver list (nunca None)."""
        data = self.load(user_id, key)
        return data if isinstance(data, list) else []

    def load_dict(self, user_id: str, key: str) -> dict[str, Any]:
        """Igual que ``load()`` pero garantiza devolver dict (nunca None)."""
        data = self.load(user_id, key)
        return data if isinstance(data, dict) else {}

    # ── Admin ──────────────────────────────────────────────────────────

    def list_users(self) -> list[dict[str, Any]]:
        """Devuelve todos los perfiles de usuario (sólo admin).

        Returns:
            Lista de dicts con {id, name, role, is_active, created_at}.
        """
        try:
            if hasattr(self._auth, "fetch_all_profiles"):
                return self._auth.fetch_all_profiles() or []
            return []
        except Exception as exc:
            logger.error("SupabaseRepository.list_users(): %s", exc)
            return []

    def update_user_role(self, user_id: str, role: str) -> bool:
        """Cambia el rol de un usuario (sólo admin).

        Args:
            user_id: UUID del usuario a modificar.
            role: nuevo rol ("admin", "pro", "free").
        """
        try:
            if hasattr(self._auth, "update_profile"):
                return self._auth.update_profile(user_id, {"role": role})
            return False
        except Exception as exc:
            logger.error("SupabaseRepository.update_user_role: %s", exc)
            return False
