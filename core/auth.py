# -*- coding: utf-8 -*-
"""
SupabaseAuth — Sistema de autenticación para OptionsKing Analytics.

Maneja registro, login, logout, sesiones persistentes ("Recordarme"),
rate-limiting de intentos y almacenamiento de datos por usuario
(favoritos, watchlists, configuración).

Credenciales se leen de st.secrets["supabase"] (Streamlit Cloud)
o de .streamlit/secrets.toml (desarrollo local).
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any

import streamlit as st
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# ============================================================================
#                    RATE LIMITING CONFIG (desactivado — intentos ilimitados)
# ============================================================================
# _MAX_LOGIN_ATTEMPTS = 3
# _RATE_LIMIT_WINDOW = 300


def _get_supabase_client() -> Client:
    """Crea (o reutiliza) el cliente Supabase desde st.secrets.

    Se almacena en session_state para no recrearlo en cada rerun.
    """
    if "_sb_client" not in st.session_state:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["anon_key"]
        st.session_state["_sb_client"] = create_client(url, key)
    return st.session_state["_sb_client"]


# ============================================================================
#                    CLASE PRINCIPAL
# ============================================================================
class SupabaseAuth:
    """Fachada de autenticación sobre Supabase GoTrue + Storage."""

    def __init__(self) -> None:
        self.client: Client = _get_supabase_client()

    # ────────────────────────────────────────────────────────────────────
    #  Rate Limiting (por email, en session_state)
    # ────────────────────────────────────────────────────────────────────
    @staticmethod
    def _check_rate_limit(email: str) -> tuple[bool, int]:
        """Retorna (bloqueado, segundos_restantes)."""
        key = "_login_attempts"
        if key not in st.session_state:
            st.session_state[key] = {}
        bucket: dict = st.session_state[key]
        now = time.time()

        record = bucket.get(email)
        if record is None:
            return False, 0

        attempts, first_ts = record
        elapsed = now - first_ts
        if elapsed > _RATE_LIMIT_WINDOW:
            # Ventana expirada → reiniciar
            del bucket[email]
            return False, 0

        if attempts >= _MAX_LOGIN_ATTEMPTS:
            remaining = int(_RATE_LIMIT_WINDOW - elapsed) + 1
            return True, remaining

        return False, 0

    @staticmethod
    def _record_attempt(email: str) -> None:
        """Registra un intento fallido de login."""
        key = "_login_attempts"
        if key not in st.session_state:
            st.session_state[key] = {}
        bucket: dict = st.session_state[key]
        now = time.time()

        record = bucket.get(email)
        if record is None:
            bucket[email] = (1, now)
        else:
            attempts, first_ts = record
            if now - first_ts > _RATE_LIMIT_WINDOW:
                bucket[email] = (1, now)
            else:
                bucket[email] = (attempts + 1, first_ts)

    @staticmethod
    def _clear_attempts(email: str) -> None:
        """Limpia el contador de intentos tras login exitoso."""
        bucket: dict = st.session_state.get("_login_attempts", {})
        bucket.pop(email, None)

    # ────────────────────────────────────────────────────────────────────
    #  Registro
    # ────────────────────────────────────────────────────────────────────
    def register(
        self,
        email: str,
        password: str,
        name: str,
        confirm_password: str,
    ) -> tuple[bool, str]:
        """Registra un nuevo usuario con confirmación por email.

        Returns (ok, mensaje_amigable).
        """
        email = email.strip().lower()
        name = name.strip()

        if not name:
            return False, "El nombre es obligatorio."
        if not email:
            return False, "El correo electrónico es obligatorio."
        if len(password) < 8:
            return False, "La contraseña debe tener al menos 8 caracteres."
        if password != confirm_password:
            return False, "Las contraseñas no coinciden."

        try:
            # No pasamos email_redirect_to — Supabase usa el Site URL
            # configurado en Dashboard > Authentication > URL Configuration.
            # Pasar una URL no whitelisteada causa que el email no se envíe.
            res = self.client.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {"display_name": name},
                },
            })
            # Supabase devuelve user incluso antes de confirmar email
            if res.user:
                return True, (
                    "✅ Cuenta creada exitosamente. "
                    "Revisa tu correo electrónico para confirmar la cuenta antes de iniciar sesión."
                )
            return False, "No se pudo crear la cuenta. Intenta de nuevo."
        except Exception as exc:
            logger.warning("Error en registro: %s", exc)
            msg = str(exc).lower()
            if "already registered" in msg or "already been registered" in msg:
                return False, "Este correo ya está registrado. Intenta iniciar sesión."
            if "weak" in msg or "password" in msg:
                return False, "La contraseña es muy débil. Usa al menos 8 caracteres con letras y números."
            if "invalid" in msg and "email" in msg:
                return False, "El correo electrónico no es válido. Verifica el formato."
            if "signup" in msg and "disabled" in msg:
                return False, "El registro de nuevos usuarios está deshabilitado temporalmente."
            # Mostrar detalle real para diagnóstico
            detail = str(exc)[:200]
            return False, f"Error al crear la cuenta: {detail}"

    # ────────────────────────────────────────────────────────────────────
    #  Login
    # ────────────────────────────────────────────────────────────────────
    def login(
        self,
        email: str,
        password: str,
        remember_me: bool = False,
    ) -> tuple[bool, str]:
        """Autentica al usuario.

        Si remember_me=True, almacena el refresh_token en session_state
        para restaurar la sesión (hasta 30 días, según config de Supabase).

        Returns (ok, mensaje_amigable).
        """
        email = email.strip().lower()
        if not email or not password:
            return False, "Ingresa tu correo y contraseña."

        # Rate limiting desactivado — intentos ilimitados

        try:
            res = self.client.auth.sign_in_with_password({
                "email": email,
                "password": password,
            })
            if res.user and res.session:
                self._clear_attempts(email)
                # Guardar sesión en session_state
                st.session_state["_auth_user"] = {
                    "id": res.user.id,
                    "email": res.user.email,
                    "name": (
                        res.user.user_metadata.get("display_name")
                        or res.user.email.split("@")[0]
                    ),
                }
                st.session_state["_auth_access_token"] = res.session.access_token
                st.session_state["_auth_refresh_token"] = res.session.refresh_token
                st.session_state["_auth_remember"] = remember_me

                # Migrar favoritos globales al usuario si es su primer login
                self._maybe_migrate_favorites(res.user.id)

                return True, f"Bienvenido, {st.session_state['_auth_user']['name']}!"

            return False, "Credenciales incorrectas."
        except Exception as exc:
            logger.warning("Error en login: %s", exc)
            msg = str(exc).lower()
            if "invalid" in msg or "credentials" in msg:
                return False, "Correo o contraseña incorrectos."
            if "email not confirmed" in msg or "not confirmed" in msg:
                return False, "Tu correo aún no ha sido confirmado. Revisa tu bandeja de entrada."
            # Mostrar detalle real para diagnóstico
            detail = str(exc)[:200]
            return False, f"Error al iniciar sesión: {detail}"

    # ────────────────────────────────────────────────────────────────────
    #  Restaurar sesión (refresh token)
    # ────────────────────────────────────────────────────────────────────
    def try_restore_session(self) -> bool:
        """Intenta restaurar la sesión usando el refresh token almacenado.

        Esto permite la funcionalidad "Recordarme" (sesión persistente
        hasta 30 días, según la configuración de Supabase).
        """
        if self.is_authenticated():
            return True

        refresh = st.session_state.get("_auth_refresh_token")
        if not refresh or not st.session_state.get("_auth_remember", False):
            return False

        try:
            res = self.client.auth.refresh_session(refresh)
            if res.user and res.session:
                st.session_state["_auth_user"] = {
                    "id": res.user.id,
                    "email": res.user.email,
                    "name": (
                        res.user.user_metadata.get("display_name")
                        or res.user.email.split("@")[0]
                    ),
                }
                st.session_state["_auth_access_token"] = res.session.access_token
                st.session_state["_auth_refresh_token"] = res.session.refresh_token
                return True
        except Exception:
            # Token expirado o inválido — limpiar
            self._clear_auth_state()
        return False

    # ────────────────────────────────────────────────────────────────────
    #  Logout
    # ────────────────────────────────────────────────────────────────────
    def logout(self) -> None:
        """Cierra sesión y limpia todo el estado de autenticación."""
        try:
            self.client.auth.sign_out()
        except Exception:
            pass  # Ya estaba deslogueado o token expirado
        self._clear_auth_state()

    @staticmethod
    def _clear_auth_state() -> None:
        """Elimina todos los keys de autenticación del session_state."""
        for k in [
            "_auth_user", "_auth_access_token", "_auth_refresh_token",
            "_auth_remember",
        ]:
            st.session_state.pop(k, None)

    # ────────────────────────────────────────────────────────────────────
    #  Estado de sesión
    # ────────────────────────────────────────────────────────────────────
    @staticmethod
    def is_authenticated() -> bool:
        """True si hay un usuario autenticado en la sesión actual."""
        return "_auth_user" in st.session_state and st.session_state["_auth_user"] is not None

    @staticmethod
    def get_current_user() -> dict | None:
        """Retorna dict {id, email, name} del usuario actual, o None."""
        return st.session_state.get("_auth_user")

    # ────────────────────────────────────────────────────────────────────
    #  Recuperación de contraseña
    # ────────────────────────────────────────────────────────────────────
    def send_password_reset(self, email: str) -> tuple[bool, str]:
        """Envía email de recuperación de contraseña.

        Returns (ok, mensaje_amigable).
        """
        email = email.strip().lower()
        if not email:
            return False, "Ingresa tu correo electrónico."
        try:
            self.client.auth.reset_password_email(email)
            return True, (
                "📧 Si el correo está registrado, recibirás un enlace "
                "para restablecer tu contraseña. Revisa tu bandeja de entrada."
            )
        except Exception as exc:
            logger.warning("Error en reset password: %s", exc)
            # No revelar si el email existe o no (seguridad)
            return True, (
                "📧 Si el correo está registrado, recibirás un enlace "
                "para restablecer tu contraseña."
            )

    # ────────────────────────────────────────────────────────────────────
    #  Datos por usuario (favoritos, watchlists, config)
    # ────────────────────────────────────────────────────────────────────
    def save_user_data(self, user_id: str, key: str, value: Any) -> bool:
        """Guarda un dato del usuario en la tabla `user_data` de Supabase.

        Esquema esperado en Supabase:
            CREATE TABLE user_data (
                id        uuid DEFAULT gen_random_uuid() PRIMARY KEY,
                user_id   uuid REFERENCES auth.users(id) ON DELETE CASCADE,
                data_key  text NOT NULL,
                data_value jsonb NOT NULL,
                updated_at timestamptz DEFAULT now(),
                UNIQUE(user_id, data_key)
            );
            -- RLS: cada usuario solo lee/escribe sus propios datos.
        """
        try:
            payload = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
            self.client.table("user_data").upsert({
                "user_id": user_id,
                "data_key": key,
                "data_value": json.loads(payload) if isinstance(payload, str) else payload,
                "updated_at": datetime.utcnow().isoformat(),
            }, on_conflict="user_id,data_key").execute()
            return True
        except Exception as exc:
            logger.error("Error guardando datos de usuario (%s/%s): %s", user_id, key, exc)
            return False

    def load_user_data(self, user_id: str, key: str) -> Any | None:
        """Carga un dato del usuario desde Supabase. Retorna None si no existe."""
        try:
            res = (
                self.client.table("user_data")
                .select("data_value")
                .eq("user_id", user_id)
                .eq("data_key", key)
                .maybe_single()
                .execute()
            )
            if res.data:
                return res.data["data_value"]
        except Exception as exc:
            logger.warning("Error cargando datos de usuario (%s/%s): %s", user_id, key, exc)
        return None

    # ────────────────────────────────────────────────────────────────────
    #  Migración de favoritos globales (JSON → Supabase)
    # ────────────────────────────────────────────────────────────────────
    def _maybe_migrate_favorites(self, user_id: str) -> None:
        """Si existe favoritos.json global y el usuario no tiene favoritos
        en Supabase, importa los datos una sola vez.
        """
        import os

        json_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "favoritos.json",
        )
        if not os.path.exists(json_path):
            return

        # Solo migrar si el usuario no tiene favoritos todavía
        existing = self.load_user_data(user_id, "favoritos")
        if existing:
            return

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                old_favs = json.load(f)
            if old_favs:
                self.save_user_data(user_id, "favoritos", old_favs)
                logger.info(
                    "Migrados %d favoritos globales para user %s",
                    len(old_favs), user_id,
                )
        except Exception as exc:
            logger.warning("Error migrando favoritos globales: %s", exc)

    def migrate_global_favorites(self, user_id: str) -> tuple[bool, str]:
        """Migración manual de favoritos globales (JSON → Supabase).

        Returns (ok, mensaje).
        """
        self._maybe_migrate_favorites(user_id)
        return True, "Migración completada."
