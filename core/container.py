# -*- coding: utf-8 -*-
"""
ServiceContainer — Inyección de dependencias centralizada.

Implementa un contenedor simple de servicios que resuelve dependencias
sin frameworks pesados.  Se instancia una vez por sesión de usuario
(almacenado en st.session_state) para evitar contaminación entre sesiones.

Principio: la capa de presentación nunca instancia servicios directamente.
           Siempre los obtiene del contenedor.

Uso típico::

    from core.container import get_container

    container = get_container()
    user_svc = container.user_service
    cs_svc = container.credit_spread_service
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from core.auth import SupabaseAuth
    from core.protocols import AuthProvider, CacheProvider, UserRepository
    from core.services.credit_spread_service import CreditSpreadService
    from core.services.scan_service import ScanService
    from core.services.user_service import UserService

logger = logging.getLogger(__name__)


class ServiceContainer:
    """Contenedor centralizado de servicios — poor-man's DI.

    Lazy-initializes cada servicio la primera vez que se accede.
    Todos los servicios se crean como singletons dentro del contenedor.

    Attributes:
        auth: proveedor de autenticación (SupabaseAuth).
        cache: proveedor de caché (CacheManager).
        user_repo: repositorio de datos de usuario.
        user_service: servicio de gestión de usuarios.
        scan_service: servicio del scanner principal.
        credit_spread_service: servicio del scanner de credit spreads.
    """

    def __init__(self, auth: Optional[Any] = None) -> None:
        """
        Args:
            auth: instancia de ``SupabaseAuth``.  Si None, se crea una.
        """
        self._auth = auth
        self._cache: Optional[Any] = None
        self._user_repo: Optional[Any] = None
        self._user_service: Optional[Any] = None
        self._scan_service: Optional[Any] = None
        self._credit_spread_service: Optional[Any] = None

    # ── Auth ───────────────────────────────────────────────────────────

    @property
    def auth(self) -> "SupabaseAuth":
        """Proveedor de autenticación (lazy init)."""
        if self._auth is None:
            from core.auth import SupabaseAuth
            self._auth = SupabaseAuth()
        return self._auth

    # ── Cache ──────────────────────────────────────────────────────────

    @property
    def cache(self) -> "CacheProvider":
        """Proveedor de caché — Redis (preferido) o memoria."""
        if self._cache is None:
            from infrastructure.caching import get_cache
            self._cache = get_cache()
        return self._cache

    # ── Repositorios ───────────────────────────────────────────────────

    @property
    def user_repo(self) -> "UserRepository":
        """Repositorio de datos de usuario sobre Supabase."""
        if self._user_repo is None:
            from infrastructure.repositories.supabase_repo import SupabaseRepository
            self._user_repo = SupabaseRepository(auth=self.auth)
        return self._user_repo

    # ── Servicios ──────────────────────────────────────────────────────

    @property
    def user_service(self) -> "UserService":
        """Servicio de gestión de usuarios, favoritos, watchlists."""
        if self._user_service is None:
            from core.services.user_service import UserService
            self._user_service = UserService(auth=self.auth)
        return self._user_service

    @property
    def scan_service(self) -> "ScanService":
        """Servicio del scanner principal (Live Scanning, OI, etc.)."""
        if self._scan_service is None:
            from core.services.scan_service import ScanService
            self._scan_service = ScanService()
        return self._scan_service

    @property
    def credit_spread_service(self) -> "CreditSpreadService":
        """Servicio del scanner de credit spreads / venta de prima."""
        if self._credit_spread_service is None:
            from core.services.credit_spread_service import CreditSpreadService
            self._credit_spread_service = CreditSpreadService()
        return self._credit_spread_service

    def reset(self) -> None:
        """Libera todas las instancias cacheadas (útil para tests)."""
        self._cache = None
        self._user_repo = None
        self._user_service = None
        self._scan_service = None
        self._credit_spread_service = None


# ── Per-session container (via st.session_state) ─────────────────────────


def get_container(auth: Optional[Any] = None) -> ServiceContainer:
    """Devuelve el contenedor de servicios de la sesión actual.

    Cada sesión de Streamlit (cada pestaña/usuario) obtiene su propia
    instancia, evitando contaminación cruzada entre usuarios.

    Args:
        auth: SupabaseAuth opcional.  Solo se usa si el contenedor aún
              no existe en session_state.
    """
    import streamlit as st

    if "_service_container" not in st.session_state:
        st.session_state["_service_container"] = ServiceContainer(auth=auth)
        logger.debug("ServiceContainer inicializado (per-session)")
    return st.session_state["_service_container"]


def reset_container() -> None:
    """Destruye el contenedor de la sesión actual (útil para tests/logout)."""
    import streamlit as st

    container = st.session_state.pop("_service_container", None)
    if container is not None:
        container.reset()


__all__ = ["ServiceContainer", "get_container", "reset_container"]
