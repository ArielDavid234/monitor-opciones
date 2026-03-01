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

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any

import streamlit as st
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# ============================================================================
#                    COOKIE CONFIG  ("Recuérdame" — 7 días)
# ============================================================================
_REMEMBER_COOKIE_NAME = "ok_remember"  # cookie name in the browser
_REMEMBER_MAX_AGE_DAYS = 7
_REMEMBER_MAX_AGE_SECS = _REMEMBER_MAX_AGE_DAYS * 86_400  # 604 800 s


def _get_signing_serializer() -> URLSafeTimedSerializer:
    """Devuelve un serializer firmado usando la anon_key de Supabase como secreto.

    No necesita un SECRET_KEY separado — la anon_key ya es un secreto
    disponible en st.secrets y suficiente para firmar cookies.
    """
    raw_key = st.secrets["supabase"]["anon_key"]
    # Hash para tener un key de longitud fija + no exponer la anon_key
    secret = hashlib.sha256(raw_key.encode()).hexdigest()
    return URLSafeTimedSerializer(secret, salt="ok-remember")

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
    #  Cookie helpers  ("Recuérdame" — 7 días persistente en browser)
    # ────────────────────────────────────────────────────────────────────
    @staticmethod
    def _set_remember_cookie(refresh_token: str) -> None:
        """Firma el refresh_token y lo inyecta como cookie HTTP vía JS.

        La cookie dura 7 días, HttpOnly=false (necesario para JS), SameSite=Lax.
        """
        try:
            s = _get_signing_serializer()
            token = s.dumps({"rt": refresh_token})
            max_age = _REMEMBER_MAX_AGE_SECS
            js = (
                f'<script>'
                f'document.cookie="{_REMEMBER_COOKIE_NAME}={token}; '
                f'path=/; max-age={max_age}; SameSite=Lax";'
                f'</script>'
            )
            st.components.v1.html(js, height=0, width=0)
        except Exception as exc:
            logger.warning("Error seteando cookie remember: %s", exc)

    @staticmethod
    def _clear_remember_cookie() -> None:
        """Elimina la cookie de remember del browser vía JS."""
        try:
            js = (
                f'<script>'
                f'document.cookie="{_REMEMBER_COOKIE_NAME}=; '
                f'path=/; max-age=0; SameSite=Lax";'
                f'</script>'
            )
            st.components.v1.html(js, height=0, width=0)
        except Exception:
            pass

    def _try_cookie_restore(self) -> bool:
        """Lee la cookie firmada, verifica firma + edad, y usa el
        refresh_token para restaurar la sesión de Supabase.

        Returns True si la sesión se restauró exitosamente.
        """
        try:
            cookies = st.context.cookies  # dict-like, read-only
            token = cookies.get(_REMEMBER_COOKIE_NAME)
            if not token:
                return False

            s = _get_signing_serializer()
            data = s.loads(token, max_age=_REMEMBER_MAX_AGE_SECS)
            refresh_token = data.get("rt")
            if not refresh_token:
                self._clear_remember_cookie()
                return False

            # Intentar refresh con Supabase
            res = self.client.auth.refresh_session(refresh_token)
            if res.user and res.session:
                display_name = (
                    res.user.user_metadata.get("display_name")
                    or res.user.email.split("@")[0]
                )
                profile = self._ensure_profile(res.user.id, display_name)
                st.session_state["_auth_user"] = {
                    "id": res.user.id,
                    "email": res.user.email,
                    "name": profile.get("name", display_name) if profile else display_name,
                    "role": profile.get("role", "user") if profile else "user",
                    "is_active": profile.get("is_active", True) if profile else True,
                    "last_login_at": (res.user.last_sign_in_at.isoformat() if hasattr(res.user.last_sign_in_at, "isoformat") else str(res.user.last_sign_in_at)) if res.user.last_sign_in_at else "",
                    "registered_at": (res.user.created_at.isoformat() if hasattr(res.user.created_at, "isoformat") else str(res.user.created_at)) if res.user.created_at else "",
                }
                st.session_state["_auth_access_token"] = res.session.access_token
                st.session_state["_auth_refresh_token"] = res.session.refresh_token
                st.session_state["_auth_remember"] = True
                # Renovar la cookie con el nuevo refresh_token
                SupabaseAuth._set_remember_cookie(res.session.refresh_token)
                logger.info("Sesión restaurada desde cookie para %s", res.user.email)
                return True

        except SignatureExpired:
            logger.info("Cookie remember expirada — limpiando")
            self._clear_remember_cookie()
        except BadSignature:
            logger.warning("Cookie remember con firma inválida — limpiando")
            self._clear_remember_cookie()
        except Exception as exc:
            logger.warning("Error restaurando sesión desde cookie: %s", exc)

        return False

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
    #  Callback de confirmación por email (redirect desde Supabase)
    # ────────────────────────────────────────────────────────────────────
    def handle_email_callback(self) -> bool:
        """Detecta si el usuario llega desde un enlace de confirmación de email.

        Supabase redirige al usuario con tokens en los query params
        (PKCE: ?code=...) o en hash fragments convertidos a params por JS.
        También puede incluir access_token y refresh_token directamente.

        Returns True si logró autenticar al usuario automáticamente.
        """
        params = dict(st.query_params)
        if not params:
            return False

        # ── PKCE flow: Supabase envía ?code=... ─────────────────────────
        code = params.get("code")
        if code:
            try:
                res = self.client.auth.exchange_code_for_session({"auth_code": code})
                if res.user and res.session:
                    self._set_session_from_response(res)
                    st.query_params.clear()
                    return True
            except Exception as exc:
                logger.warning("Error intercambiando code por sesión: %s", exc)
            # Limpiar el code para no reintentar
            st.query_params.clear()
            st.session_state["_email_just_confirmed"] = True
            return False

        # ── Implicit flow: access_token + refresh_token en params ───────
        access_token = params.get("access_token")
        refresh_token = params.get("refresh_token")
        if access_token and refresh_token:
            try:
                res = self.client.auth.set_session(access_token, refresh_token)
                if res.user and res.session:
                    self._set_session_from_response(res)
                    st.query_params.clear()
                    return True
            except Exception as exc:
                logger.warning("Error restaurando sesión desde tokens: %s", exc)
            st.query_params.clear()
            st.session_state["_email_just_confirmed"] = True
            return False

        # ── Solo type param (confirmación sin tokens) ───────────────────
        token_type = params.get("type", "")
        if token_type in ("signup", "email", "recovery", "magiclink"):
            st.query_params.clear()
            st.session_state["_email_just_confirmed"] = True
            return False

        return False

    def _ensure_profile(self, user_id: str, name: str) -> dict | None:
        """Crea el perfil en public.profiles si no existe. Retorna el perfil."""
        profile = self._fetch_profile(user_id)
        if profile:
            return profile
        try:
            res = (
                self.client.table("profiles")
                .insert({
                    "id": user_id,
                    "name": name,
                    "role": "user",
                    "is_active": True,
                })
                .execute()
            )
            if res.data and len(res.data) > 0:
                logger.info("Perfil creado para %s", user_id)
                return res.data[0]
        except Exception as exc:
            logger.warning("Error creando perfil para %s: %s", user_id, exc)
        return None

    def _set_session_from_response(self, res: Any) -> None:
        """Helper: guarda usuario + tokens en session_state desde una respuesta auth."""
        display_name = (
            res.user.user_metadata.get("display_name")
            or res.user.email.split("@")[0]
        )
        profile = self._ensure_profile(res.user.id, display_name)
        st.session_state["_auth_user"] = {
            "id": res.user.id,
            "email": res.user.email,
            "name": profile.get("name", display_name) if profile else display_name,
            "role": profile.get("role", "user") if profile else "user",
            "is_active": profile.get("is_active", True) if profile else True,
            "last_login_at": (res.user.last_sign_in_at.isoformat() if hasattr(res.user.last_sign_in_at, "isoformat") else str(res.user.last_sign_in_at)) if res.user.last_sign_in_at else "",
            "registered_at": (res.user.created_at.isoformat() if hasattr(res.user.created_at, "isoformat") else str(res.user.created_at)) if res.user.created_at else "",
        }
        st.session_state["_auth_access_token"] = res.session.access_token
        st.session_state["_auth_refresh_token"] = res.session.refresh_token
        st.session_state["_auth_remember"] = True

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
            # Redirect URL para que al confirmar el email, el usuario
            # aterrice directamente en la app.
            # IMPORTANTE: esta URL debe estar en Supabase Dashboard >
            # Authentication > URL Configuration > Redirect URLs.
            site_url = st.secrets["supabase"].get("site_url", "")
            sign_up_opts: dict[str, Any] = {
                "data": {"display_name": name},
            }
            if site_url:
                sign_up_opts["email_redirect_to"] = site_url

            res = self.client.auth.sign_up({
                "email": email,
                "password": password,
                "options": sign_up_opts,
            })
            # Si la confirmación por email está desactivada, Supabase
            # devuelve una sesión activa de inmediato.
            if res.session:
                self._set_session_from_response(res)
                st.session_state["_show_welcome_splash"] = True
                return True, "✅ Cuenta creada exitosamente. ¡Bienvenido!"
            # Si hay confirmación activa, pedir que revisen el correo
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
                display_name = (
                    res.user.user_metadata.get("display_name")
                    or res.user.email.split("@")[0]
                )
                profile = self._ensure_profile(res.user.id, display_name)
                st.session_state["_auth_user"] = {
                    "id": res.user.id,
                    "email": res.user.email,
                    "name": profile.get("name", display_name) if profile else display_name,
                    "role": profile.get("role", "user") if profile else "user",
                    "is_active": profile.get("is_active", True) if profile else True,
                    "last_login_at": datetime.utcnow().isoformat(),
                    "registered_at": (res.user.created_at.isoformat() if hasattr(res.user.created_at, "isoformat") else str(res.user.created_at)) if res.user.created_at else "",
                }
                st.session_state["_auth_access_token"] = res.session.access_token
                st.session_state["_auth_refresh_token"] = res.session.refresh_token
                st.session_state["_auth_remember"] = remember_me
                if remember_me:
                    st.session_state["_auth_remember_until"] = (
                        datetime.now() + timedelta(days=_REMEMBER_MAX_AGE_DAYS)
                    ).isoformat()
                    # Setear cookie firmada en el browser (7 días)
                    self._set_remember_cookie(res.session.refresh_token)

                # Migrar favoritos globales al usuario si es su primer login
                self._maybe_migrate_favorites(res.user.id)

                # Registrar last_login y fecha de registro en usage_stats
                try:
                    uid = res.user.id
                    raw_stats = self.load_user_data(uid, "usage_stats") or {}
                    raw_stats["last_login"] = datetime.utcnow().isoformat()
                    raw_stats["logins_total"] = raw_stats.get("logins_total", 0) + 1
                    # Guardar fecha de registro de Supabase Auth (sólo la primera vez)
                    if not raw_stats.get("registered_at") and res.user.created_at:
                        reg = res.user.created_at
                        raw_stats["registered_at"] = (
                            reg.isoformat() if hasattr(reg, "isoformat") else str(reg)
                        )
                    self.save_user_data(uid, "usage_stats", raw_stats)
                except Exception as _e:
                    logger.debug("Error guardando stats en login: %s", _e)

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
        """Intenta restaurar la sesión usando el refresh token almacenado
        en session_state O en la cookie firmada del browser.

        Orden de prioridad:
          1. Ya autenticado en session_state → True
          2. refresh_token en session_state (misma pestaña) → refresh
          3. Cookie firmada en el browser (cierre/reapertura) → refresh
        """
        if self.is_authenticated():
            return True

        # ── Intento 1: refresh_token en session_state ────────────────────
        refresh = st.session_state.get("_auth_refresh_token")
        if refresh and st.session_state.get("_auth_remember", False):
            # Verificar que no haya expirado el período de "Recordarme"
            remember_until = st.session_state.get("_auth_remember_until")
            if remember_until:
                try:
                    expiry = datetime.fromisoformat(remember_until)
                    if datetime.now() > expiry:
                        logger.info("Recordarme expirado — limpiando sesión")
                        self._clear_auth_state()
                        # fall through to cookie attempt
                        refresh = None
                except (ValueError, TypeError):
                    self._clear_auth_state()
                    refresh = None

            if refresh:
                try:
                    res = self.client.auth.refresh_session(refresh)
                    if res.user and res.session:
                        display_name = (
                            res.user.user_metadata.get("display_name")
                            or res.user.email.split("@")[0]
                        )
                        profile = self._ensure_profile(res.user.id, display_name)
                        st.session_state["_auth_user"] = {
                            "id": res.user.id,
                            "email": res.user.email,
                            "name": profile.get("name", display_name) if profile else display_name,
                            "role": profile.get("role", "user") if profile else "user",
                            "is_active": profile.get("is_active", True) if profile else True,
                            "last_login_at": (res.user.last_sign_in_at.isoformat() if hasattr(res.user.last_sign_in_at, "isoformat") else str(res.user.last_sign_in_at)) if res.user.last_sign_in_at else "",
                            "registered_at": (res.user.created_at.isoformat() if hasattr(res.user.created_at, "isoformat") else str(res.user.created_at)) if res.user.created_at else "",
                        }
                        st.session_state["_auth_access_token"] = res.session.access_token
                        st.session_state["_auth_refresh_token"] = res.session.refresh_token
                        return True
                except Exception:
                    self._clear_auth_state()

        # ── Intento 2: cookie firmada del browser ────────────────────────
        return self._try_cookie_restore()

    # ────────────────────────────────────────────────────────────────────
    #  Logout
    # ────────────────────────────────────────────────────────────────────
    def logout(self) -> None:
        """Cierra sesión y limpia todo el estado de autenticación + cookie."""
        try:
            self.client.auth.sign_out()
        except Exception:
            pass  # Ya estaba deslogueado o token expirado
        self._clear_remember_cookie()
        self._clear_auth_state()

    @staticmethod
    def _clear_auth_state() -> None:
        """Elimina todos los keys de autenticación del session_state."""
        for k in [
            "_auth_user", "_auth_access_token", "_auth_refresh_token",
            "_auth_remember", "_auth_remember_until", "_profile_synced",
        ]:
            st.session_state.pop(k, None)

    # ────────────────────────────────────────────────────────────────────
    #  Estado de sesión
    # ────────────────────────────────────────────────────────────────────
    @staticmethod
    def is_authenticated() -> bool:
        """True si hay un usuario autenticado en la sesión actual."""
        return "_auth_user" in st.session_state and st.session_state["_auth_user"] is not None

    def get_current_user(self) -> dict | None:
        """Retorna dict {id, email, name, role, is_active} del usuario actual, o None.

        Si el rol aún no fue verificado contra la tabla profiles en esta
        sesión, lo consulta una vez y actualiza el cache.
        """
        user = st.session_state.get("_auth_user")
        if not user:
            return None

        # Fetch profile una vez por sesión para tener el role real de la DB
        if not st.session_state.get("_profile_synced"):
            profile = self._fetch_profile(user["id"])
            if profile:
                user["role"] = profile.get("role", "user")
                user["is_active"] = profile.get("is_active", True)
            else:
                user.setdefault("role", "user")
                user.setdefault("is_active", True)
            st.session_state["_auth_user"] = user
            st.session_state["_profile_synced"] = True

        return user

    def is_admin(self) -> bool:
        """True si el usuario actual tiene rol 'admin'."""
        try:
            user = self.get_current_user()
            return bool(user and user.get("role") == "admin")
        except Exception:
            return False

    # ────────────────────────────────────────────────────────────────────
    #  Perfil de usuario (tabla public.profiles)
    # ────────────────────────────────────────────────────────────────────
    def _fetch_profile(self, user_id: str) -> dict | None:
        """Obtiene el perfil del usuario desde public.profiles.

        Retorna dict con {name, role, is_active} o None si no existe
        o si la tabla aún no ha sido creada.

        Nota: NO usa maybe_single() porque algunas versiones de supabase-py
        lanzan excepción con HTTP 204 en vez de retornar None.
        """
        try:
            res = (
                self.client.table("profiles")
                .select("name, role, is_active")
                .eq("id", user_id)
                .execute()
            )
            if res.data and len(res.data) > 0:
                return res.data[0]
            return None
        except Exception as exc:
            # La tabla puede no existir aún — no romper el login
            logger.warning("Error obteniendo perfil para %s: %s", user_id, exc)
            return None

    def fetch_profile_full(self, user_id: str) -> dict | None:
        """Obtiene el perfil completo del usuario (incluye created_at).

        Retorna dict con {name, role, is_active, created_at} o None.
        """
        try:
            res = (
                self.client.table("profiles")
                .select("name, role, is_active, created_at")
                .eq("id", user_id)
                .execute()
            )
            if res.data and len(res.data) > 0:
                return res.data[0]
            return None
        except Exception as exc:
            logger.warning("Error obteniendo perfil completo para %s: %s", user_id, exc)
            return None

    def fetch_all_profiles(self) -> list[dict]:
        """Obtiene todos los perfiles (solo para administradores).

        Retorna lista de dicts con {id, name, role, is_active, created_at, email}.
        Requiere que el admin tenga permisos de lectura sobre profiles.
        """
        try:
            res = (
                self.client.table("profiles")
                .select("id, name, role, is_active, created_at")
                .order("created_at", desc=True)
                .execute()
            )
            return res.data or []
        except Exception as exc:
            logger.error("Error obteniendo todos los perfiles: %s", exc)
            return []

    def update_profile(self, user_id: str, updates: dict) -> bool:
        """Actualiza campos del perfil de un usuario.

        `updates` puede contener: name, role, is_active.
        """
        try:
            self.client.table("profiles").update(updates).eq("id", user_id).execute()
            return True
        except Exception as exc:
            logger.error("Error actualizando perfil %s: %s", user_id, exc)
            return False
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
                .execute()
            )
            if res.data and len(res.data) > 0:
                return res.data[0]["data_value"]
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
