# -*- coding: utf-8 -*-
"""
Protocolos (interfaces) del dominio — definen los contratos que
las implementaciones en ``infrastructure/`` deben cumplir.

Usar Protocol (PEP 544) en vez de ABC permite duck typing estructural:
la capa de infraestructura no necesita heredar explícitamente, sólo
implementar los métodos requeridos.

Esto hace que los tests puedan usar mocks simples sin herencia.
"""
from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable


# ============================================================================
#  AuthProvider — contrato de autenticación
# ============================================================================

@runtime_checkable
class AuthProvider(Protocol):
    """Contrato para cualquier proveedor de autenticación.

    La implementación concreta vive en ``infrastructure/auth/``.
    """

    def is_authenticated(self) -> bool:
        """True si hay un usuario autenticado en la sesión actual."""
        ...

    def try_restore_session(self) -> bool:
        """Intenta restaurar la sesión desde cookies/tokens persistentes."""
        ...

    def get_current_user(self) -> Optional[dict[str, Any]]:
        """Devuelve dict {id, email, name, role, is_active} o None."""
        ...

    def login(self, email: str, password: str, remember_me: bool = False) -> tuple[bool, str]:
        """Autentica al usuario. Returns (ok, mensaje)."""
        ...

    def logout(self) -> None:
        """Cierra sesión y limpia estado."""
        ...

    def register(self, email: str, password: str, name: str, confirm_password: str) -> tuple[bool, str]:
        """Registra un nuevo usuario. Returns (ok, mensaje)."""
        ...

    def save_user_data(self, user_id: str, key: str, value: Any) -> bool:
        """Guarda un dato del usuario."""
        ...

    def load_user_data(self, user_id: str, key: str) -> Optional[Any]:
        """Carga un dato del usuario."""
        ...

    def handle_email_callback(self) -> bool:
        """Procesa callbacks de confirmación por email."""
        ...


# ============================================================================
#  UserRepository — contrato de acceso a datos de usuario
# ============================================================================

@runtime_checkable
class UserRepository(Protocol):
    """Contrato para el repositorio de datos de usuario."""

    def load(self, user_id: str, key: str) -> Optional[Any]:
        """Lee un valor del almacén de usuario."""
        ...

    def save(self, user_id: str, key: str, value: Any) -> bool:
        """Escribe un valor en el almacén de usuario."""
        ...

    def load_list(self, user_id: str, key: str) -> list:
        """Lee un valor y garantiza que sea lista."""
        ...

    def load_dict(self, user_id: str, key: str) -> dict:
        """Lee un valor y garantiza que sea dict."""
        ...


# ============================================================================
#  CacheProvider — contrato de caché
# ============================================================================

@runtime_checkable
class CacheProvider(Protocol):
    """Contrato de caché genérico (Redis, memoria, etc.)."""

    def get(self, key: str) -> Optional[Any]:
        """Lee un valor del caché. None si no existe o expiró."""
        ...

    def set(self, key: str, value: Any, ttl: int = 720) -> None:
        """Almacena un valor con TTL en segundos."""
        ...

    def delete(self, key: str) -> None:
        """Elimina una entrada."""
        ...

    def clear_prefix(self, prefix: str) -> None:
        """Elimina todas las entradas cuya clave empieza con ``prefix``."""
        ...

    @property
    def backend(self) -> str:
        """Nombre del backend activo ('redis' o 'memory')."""
        ...


# ============================================================================
#  MarketDataGateway — contrato de acceso a datos de mercado
# ============================================================================

@runtime_checkable
class MarketDataGateway(Protocol):
    """Contrato para obtener datos de mercado (precios, opciones, historial).

    La implementación concreta vive en ``infrastructure/data/``.
    """

    def get_current_price(self, ticker: str) -> Optional[float]:
        """Precio spot actual del subyacente."""
        ...

    def get_option_dates(self, ticker: str) -> list[str]:
        """Fechas de expiración disponibles."""
        ...

    def get_option_chain(self, ticker: str, expiration: str) -> dict:
        """Cadena de opciones (puts/calls DataFrames)."""
        ...

    def get_history(self, ticker: str, period: str) -> Any:
        """Historial de precios OHLCV."""
        ...


__all__ = [
    "AuthProvider",
    "UserRepository",
    "CacheProvider",
    "MarketDataGateway",
]
