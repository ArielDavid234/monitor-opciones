# -*- coding: utf-8 -*-
"""
Background Updater — actualización periódica de datos de mercado para
los top 100 tickers del S&P 500.

Estrategia:
  - Divide los 100 tickers en 5 batches de ~20
  - Cada 60 segundos procesa 1 batch con get_fast_market_data()
  - Ciclo completo ≈ 5 minutos
  - Resultado se almacena en Redis/memory cache con key "fast_data:{ticker}"
  - Las páginas leen de cache primero → fallback a cálculo on-demand

Anti-ban:
  - Sleep aleatorio entre llamadas individuales (1.8–2.5s)
  - Respeta circuit breaker y rate limiter globales de yfinance
  - Si un batch falla parcialmente, continúa con el siguiente
  - Si la lista de tickers no se puede cargar, usa fallback de 20 populares

Hilo daemon: se detiene automáticamente cuando Streamlit termina.
"""
from __future__ import annotations

import json
import logging
import math
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ── Fallback: 20 tickers populares (alta liquidez, siempre disponibles) ──
_FALLBACK_TICKERS: list[str] = [
    "NVDA", "AAPL", "MSFT", "AMZN", "GOOGL",
    "META", "TSLA", "AVGO", "BRK-B", "LLY",
    "JPM", "V", "UNH", "XOM", "MA",
    "COST", "HD", "PG", "JNJ", "ABBV",
]

# ── Configuración del updater ────────────────────────────────────────────
NUM_BATCHES = 5
INTERVAL_SECONDS = 60          # intervalo entre batches
CACHE_TTL_SECONDS = 360        # 6 min TTL (ciclo completo ~5 min)
_SP500_CSV_URL = (
    "https://raw.githubusercontent.com/datasets/"
    "s-and-p-500-companies/main/data/constituents.csv"
)


# ============================================================================
#  Carga de la lista top 100 S&P 500
# ============================================================================

def _load_sp500_top100() -> list[str]:
    """Carga los top 100 tickers del S&P 500.

    Intenta en orden:
      1. CSV de GitHub (datasets/s-and-p-500-companies) — fiable y estable
      2. Wikipedia scraping via pandas.read_html
      3. Fallback estático de 20 tickers populares

    Returns:
        Lista de hasta 100 símbolos (strings).
    """
    # Intento 1: CSV de GitHub (requests con timeout + pandas)
    try:
        import io
        import requests
        import pandas as pd
        resp = requests.get(_SP500_CSV_URL, timeout=10)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        symbols = df["Symbol"].str.replace(".", "-", regex=False).tolist()
        result = symbols[:100]
        if len(result) >= 50:
            logger.info(
                "SP500 top 100: cargados %d tickers desde GitHub CSV", len(result),
            )
            return result
    except Exception as exc:
        logger.warning("SP500 CSV falló: %s — intentando Wikipedia", exc)

    # Intento 2: Wikipedia (read_html con storage_options para User-Agent)
    try:
        import pandas as pd
        tables = pd.read_html(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            attrs={"id": "constituents"},
            storage_options={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            },
        )
        if tables:
            symbols = (
                tables[0]["Symbol"]
                .str.replace(".", "-", regex=False)
                .tolist()
            )
            result = symbols[:100]
            if len(result) >= 50:
                logger.info(
                    "SP500 top 100: cargados %d tickers desde Wikipedia",
                    len(result),
                )
                return result
    except Exception as exc:
        logger.warning("SP500 Wikipedia falló: %s — usando fallback", exc)

    # Intento 3: Fallback estático
    logger.warning(
        "SP500: usando fallback de %d tickers populares", len(_FALLBACK_TICKERS),
    )
    return list(_FALLBACK_TICKERS)


# ============================================================================
#  Estado global del updater (singleton thread-safe)
# ============================================================================

class _UpdaterState:
    """Estado compartido entre el hilo updater y la UI de Streamlit."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.running = False
        self.current_batch: int = 0
        self.total_batches: int = NUM_BATCHES
        self.last_update: float = 0.0          # time.time() del último batch
        self.last_error: Optional[str] = None
        self.tickers_loaded: int = 0
        self._thread: Optional[threading.Thread] = None

    @property
    def minutes_since_update(self) -> float:
        """Minutos desde la última actualización exitosa."""
        if self.last_update == 0:
            return -1.0
        return (time.time() - self.last_update) / 60.0

    @property
    def status_text(self) -> str:
        """Texto descriptivo para el sidebar."""
        if not self.running:
            return "⏸️ Detenido"
        mins = self.minutes_since_update
        if mins < 0:
            return f"🔄 Iniciando... (batch 1/{self.total_batches})"
        return (
            f"🔄 Batch {self.current_batch}/{self.total_batches} "
            f"· hace {mins:.0f} min"
        )


_state = _UpdaterState()


def get_updater_state() -> _UpdaterState:
    """Devuelve la instancia singleton del estado del updater."""
    return _state


# ============================================================================
#  Hilo de actualización
# ============================================================================

def _run_updater_loop(tickers: list[str]) -> None:
    """Loop principal del hilo daemon.

    Divide *tickers* en NUM_BATCHES batches y los procesa uno por uno
    cada INTERVAL_SECONDS.  Al completar todos, reinicia desde el batch 0.
    """
    from core.credit_spread_scanner import get_fast_market_data
    from infrastructure.caching import get_cache

    cache = get_cache()
    batch_size = math.ceil(len(tickers) / NUM_BATCHES)
    batches = [
        tickers[i : i + batch_size]
        for i in range(0, len(tickers), batch_size)
    ]
    _state.total_batches = len(batches)
    _state.tickers_loaded = len(tickers)

    logger.info(
        "BackgroundUpdater: %d tickers en %d batches de ~%d",
        len(tickers), len(batches), batch_size,
    )

    batch_idx = 0
    while _state.running:
        current_batch = batches[batch_idx % len(batches)]
        _state.current_batch = (batch_idx % len(batches)) + 1

        try:
            results = get_fast_market_data(current_batch)
            # Guardar cada ticker en cache con prefijo "fast_data:"
            for ticker, data in results.items():
                cache.set(f"fast_data:{ticker}", data, ttl=CACHE_TTL_SECONDS)

            _state.last_update = time.time()
            _state.last_error = None
            logger.info(
                "BackgroundUpdater: batch %d/%d OK — %d tickers actualizados",
                _state.current_batch, _state.total_batches, len(results),
            )
        except Exception as exc:
            _state.last_error = str(exc)
            logger.error(
                "BackgroundUpdater: batch %d/%d FALLÓ — %s",
                _state.current_batch, _state.total_batches, exc,
            )

        batch_idx += 1

        # Esperar antes del siguiente batch (respetando stop)
        for _ in range(INTERVAL_SECONDS):
            if not _state.running:
                break
            time.sleep(1)

    logger.info("BackgroundUpdater: hilo finalizado")


# ============================================================================
#  API pública
# ============================================================================

def start_background_updater() -> None:
    """Inicia el updater en un hilo daemon (idempotente — solo una instancia).

    Seguro para llamar múltiples veces: si ya está corriendo, no-op.
    """
    with _state.lock:
        if _state.running and _state._thread and _state._thread.is_alive():
            return  # Ya corriendo

        tickers = _load_sp500_top100()
        _state.running = True
        _state._thread = threading.Thread(
            target=_run_updater_loop,
            args=(tickers,),
            daemon=True,
            name="bg-updater",
        )
        _state._thread.start()
        logger.info("BackgroundUpdater: iniciado con %d tickers", len(tickers))


def stop_background_updater() -> None:
    """Detiene el updater limpiamente."""
    _state.running = False
    if _state._thread:
        _state._thread.join(timeout=5)
        logger.info("BackgroundUpdater: detenido")


def read_fast_data(ticker: str) -> Optional[dict]:
    """Lee datos rápidos de un ticker desde el cache.

    Returns:
        dict con datos del ticker o None si no existe/expiró.
    """
    from infrastructure.caching import get_cache
    return get_cache().get(f"fast_data:{ticker}")
