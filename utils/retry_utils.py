# -*- coding: utf-8 -*-
"""
Utilidades de resiliencia: retry con backoff exponencial + jitter,
circuit breaker básico, y wrappers reutilizables para APIs financieras.

Centraliza la lógica de reintentos que antes estaba duplicada en
scanner.py, barchart_oi.py y api_integrations.py. Al usar tenacity:

- Backoff exponencial + jitter random → evita thundering herd
- Logging automático de cada reintento (motivo + tiempo de espera)
- Circuit breaker → pausa llamadas si la API está caída (>N fallos en ventana)
- Decorador limpio: las funciones de negocio no mezclan lógica de retry

Impacto financiero: retries robustos mantienen datos en vivo para
decisiones oportunas de inversión, sin interrupciones por rate-limits
o timeouts transitorios de yfinance/Alpha Vantage/Barchart.
"""
import logging
import time
import threading
from typing import Callable, Optional, Tuple, Type, Union

import requests
from tenacity import (
    retry,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
    before_sleep_log,
    RetryError,
)

logger = logging.getLogger(__name__)


# ============================================================================
#   EXCEPCIONES PERSONALIZADAS
# ============================================================================

class RateLimitError(Exception):
    """Indica que la API devolvió 429 o su equivalente de rate-limit."""
    pass


class CircuitOpenError(Exception):
    """El circuit breaker está abierto — la API se pausó por fallos repetidos."""
    pass


# ============================================================================
#   PREDICADOS REUTILIZABLES PARA TENACITY
# ============================================================================

# Excepciones transitorias que merecen retry
TRANSIENT_HTTP_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    RateLimitError,
)

# Incluye HTTPError 5xx (server-side)
ALL_RETRIABLE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    requests.exceptions.HTTPError,
    RateLimitError,
)


def _is_retriable_http_error(exc: BaseException) -> bool:
    """Retorna True solo para HTTPError con status 429 o 5xx.

    Evita reintentar errores del cliente (400, 401, 404) que no se
    resolverán con más intentos.
    """
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, requests.exceptions.HTTPError):
        status = getattr(exc.response, "status_code", None)
        if status is not None:
            return status == 429 or status >= 500
    if isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        return True
    return False


# ============================================================================
#   CIRCUIT BREAKER — pausa llamadas si la API está caída
# ============================================================================

class CircuitBreaker:
    """Circuit breaker thread-safe para APIs externas.

    Si se registran >= max_failures fallos consecutivos dentro de una
    ventana de reset_timeout segundos, el circuito se abre y rechaza
    nuevas llamadas hasta que pase la ventana.

    Uso:
        breaker = CircuitBreaker(max_failures=5, reset_timeout=300)

        # Antes de llamar a la API:
        breaker.check()  # raise CircuitOpenError si abierto

        # Tras resultado:
        breaker.record_success()   # resetea contador
        breaker.record_failure()   # incrementa

    Args:
        max_failures: Fallos consecutivos para abrir el circuito.
        reset_timeout: Segundos que el circuito permanece abierto.
        name: Nombre para logs (ej. "alpha_vantage", "yfinance").
    """

    def __init__(
        self,
        max_failures: int = 5,
        reset_timeout: float = 300.0,
        name: str = "default",
    ):
        self._max_failures = max_failures
        self._reset_timeout = reset_timeout
        self._name = name
        self._failures = 0
        self._last_failure_time: float = 0.0
        self._lock = threading.Lock()

    @property
    def is_open(self) -> bool:
        """True si el circuito está abierto (debería rechazar llamadas)."""
        with self._lock:
            if self._failures < self._max_failures:
                return False
            # Verificar si ya pasó la ventana de reset
            if time.time() - self._last_failure_time >= self._reset_timeout:
                # Half-open: resetear y permitir
                self._failures = 0
                logger.info(
                    "CircuitBreaker [%s]: Half-open → cerrado (ventana expiró)",
                    self._name,
                )
                return False
            return True

    def check(self) -> None:
        """Verifica si el circuito permite ejecutar. Raise si abierto."""
        if self.is_open:
            logger.warning(
                "CircuitBreaker [%s]: ABIERTO — %d fallos consecutivos, "
                "pausado %.0fs restantes",
                self._name,
                self._failures,
                self._reset_timeout - (time.time() - self._last_failure_time),
            )
            raise CircuitOpenError(
                f"API '{self._name}' pausada por {self._failures} fallos "
                f"consecutivos. Reintenta en "
                f"~{int(self._reset_timeout - (time.time() - self._last_failure_time))}s."
            )

    def record_success(self) -> None:
        """Registra éxito → resetea contador de fallos."""
        with self._lock:
            if self._failures > 0:
                logger.info(
                    "CircuitBreaker [%s]: Éxito — reseteando contador (%d → 0)",
                    self._name,
                    self._failures,
                )
            self._failures = 0

    def record_failure(self) -> None:
        """Registra fallo → incrementa contador."""
        with self._lock:
            self._failures += 1
            self._last_failure_time = time.time()
            logger.warning(
                "CircuitBreaker [%s]: Fallo #%d/%d",
                self._name,
                self._failures,
                self._max_failures,
            )

    @property
    def state(self) -> str:
        """Estado actual: 'closed', 'open', o 'half-open'."""
        with self._lock:
            if self._failures < self._max_failures:
                return "closed"
            if time.time() - self._last_failure_time >= self._reset_timeout:
                return "half-open"
            return "open"

    def __repr__(self) -> str:
        return (
            f"CircuitBreaker(name={self._name!r}, state={self.state}, "
            f"failures={self._failures}/{self._max_failures})"
        )


# ── Instancias globales por API ──────────────────────────────────────────
# Se importan desde otros módulos:
#   from utils.retry_utils import cb_yfinance, cb_alpha_vantage, cb_barchart

cb_yfinance = CircuitBreaker(max_failures=6, reset_timeout=300, name="yfinance")
cb_alpha_vantage = CircuitBreaker(max_failures=4, reset_timeout=300, name="alpha_vantage")
cb_barchart = CircuitBreaker(max_failures=5, reset_timeout=300, name="barchart")


# ============================================================================
#   PREDICADO DE RETRY PARA YFINANCE
# ============================================================================

# Keywords en mensajes de excepción genérica de yfinance que indican
# errores transitorios dignos de reintento.
_YF_RETRIABLE_KEYWORDS = (
    "429", "rate limit", "too many requests",
    "timeout", "timed out", "read timed out",
    "connection", "refused", "reset", "unreachable",
    "failed to", "unavailable", "no data found",
    "502", "503", "504",
)


def _is_retriable_yfinance_error(exc: BaseException) -> bool:
    """Predicado para tenacity: retorna True si la excepción es transitoria.

    yfinance envuelve errores HTTP en Exception genérica. Este predicado
    inspecciona tanto el tipo como el mensaje para decidir si reintentar.
    Evita reintentar errores de programación (TypeError, ValueError puro, etc.).
    """
    # Tipos específicos → siempre retriable
    if isinstance(exc, (
        RateLimitError,
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError,
    )):
        return True
    if isinstance(exc, requests.exceptions.HTTPError):
        status = getattr(exc.response, "status_code", None)
        return status is not None and (status == 429 or status >= 500)
    # Excepción genérica → inspeccionar mensaje
    msg = str(exc).lower()
    return any(kw in msg for kw in _YF_RETRIABLE_KEYWORDS)


# ============================================================================
#   DECORADORES DE RETRY CONFIGURABLES
# ============================================================================

def retry_yfinance(
    max_attempts: int = 4,
    min_wait: float = 2,
    max_wait: float = 40,
):
    """Decorador de retry para llamadas a Yahoo Finance / yfinance.

    Usa backoff exponencial + jitter para evitar sobrecarga sincronizada
    cuando múltiples usuarios escanean al mismo tiempo.

    Predicate: retries en RateLimitError, Timeout, ConnectionError, y
    excepciones genéricas de yfinance con keywords transitorios en el mensaje.

    Args:
        max_attempts: Número máximo de intentos (incluye el primero).
        min_wait: Espera mínima entre reintentos (segundos).
        max_wait: Espera máxima entre reintentos (segundos).
    """
    return retry(
        retry=retry_if_exception(_is_retriable_yfinance_error),
        stop=stop_after_attempt(max_attempts),
        wait=wait_random_exponential(multiplier=1, min=min_wait, max=max_wait),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


def retry_alpha_vantage(
    max_attempts: int = 3,
    min_wait: float = 8,
    max_wait: float = 60,
):
    """Decorador de retry para Alpha Vantage (rate-limit severo: 5 req/min free).

    Esperas más largas porque el free tier es muy restrictivo.
    """
    return retry(
        retry=retry_if_exception_type(ALL_RETRIABLE_EXCEPTIONS),
        stop=stop_after_attempt(max_attempts),
        wait=wait_random_exponential(multiplier=2, min=min_wait, max=max_wait),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


def retry_barchart(
    max_attempts: int = 4,
    min_wait: float = 1,
    max_wait: float = 16,
):
    """Decorador de retry para Barchart OI scraping.

    Barchart detecta bots agresivos → esperas moderadas con jitter.
    """
    return retry(
        retry=retry_if_exception_type(ALL_RETRIABLE_EXCEPTIONS),
        stop=stop_after_attempt(max_attempts),
        wait=wait_random_exponential(multiplier=1, min=min_wait, max=max_wait),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


# ============================================================================
#   WRAPPER GENÉRICO DE REQUEST ROBUSTO
# ============================================================================

@retry(
    retry=retry_if_exception_type(ALL_RETRIABLE_EXCEPTIONS),
    stop=stop_after_attempt(5),
    wait=wait_random_exponential(multiplier=1, min=4, max=60),
    before_sleep=before_sleep_log(logger, logging.INFO),
    reraise=True,
)
def robust_request(
    url: str,
    headers: Optional[dict] = None,
    params: Optional[dict] = None,
    timeout: int = 15,
) -> requests.Response:
    """GET robusto con retry + jitter automático (tenacity).

    Ideal para endpoints REST donde no se necesita curl_cffi/TLS fingerprint.
    Levanta HTTPError si status >= 400 (lo que activa el retry para 5xx/429).

    Args:
        url: URL del endpoint.
        headers: Headers HTTP opcionales.
        params: Query params opcionales.
        timeout: Timeout en segundos.

    Returns:
        requests.Response exitosa.

    Raises:
        RateLimitError: Si el servidor devuelve 429.
        requests.exceptions.HTTPError: Si status >= 400 (tras todos los retries).
        requests.exceptions.Timeout: Tras todos los retries por timeout.
    """
    resp = requests.get(url, headers=headers, params=params, timeout=timeout)

    if resp.status_code == 429:
        raise RateLimitError(f"Rate limit (429) en {url}")

    resp.raise_for_status()
    return resp


# ============================================================================
#   HELPERS DE UI
# ============================================================================

def notify_retry_exhausted(context: str = "API") -> None:
    """Muestra un warning amigable en Streamlit cuando los retries se agotan.

    Llamar en el bloque except RetryError / Exception tras un fetch fallido.

    Args:
        context: Nombre de la fuente de datos (ej. "Yahoo Finance", "Alpha Vantage").
    """
    import streamlit as st
    st.warning(
        f"⚠️ **Datos retrasados** — Límite de {context} alcanzado tras varios "
        f"reintentos. Los datos pueden estar desactualizados. Intenta de nuevo "
        f"en unos minutos.",
        icon="⏳",
    )


def notify_circuit_open(breaker: CircuitBreaker) -> None:
    """Muestra warning cuando el circuit breaker está abierto."""
    import streamlit as st
    remaining = int(
        breaker._reset_timeout - (time.time() - breaker._last_failure_time)
    )
    st.warning(
        f"🔌 **{breaker._name} pausado** — Demasiados fallos consecutivos. "
        f"Reintentando automáticamente en ~{max(remaining, 0)}s.",
        icon="🔌",
    )
