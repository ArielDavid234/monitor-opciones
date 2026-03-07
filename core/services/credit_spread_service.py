# -*- coding: utf-8 -*-
"""
CreditSpreadService — capa de servicio para el scanner de venta de prima.

Principios aplicados:
- Cero imports de Streamlit (100 % testeable sin UI)
- Recibe parámetros explícitos, devuelve entidades tipadas
- Delega I/O a la capa de infraestructura (scanner.py / cache.py)
- Toda la lógica de negocio vive aquí; la página sólo llama este servicio
- Compatible con async (todos los métodos se pueden envolver con ``asyncio``)
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

import pandas as pd

from config.constants import (
    ALERT_DEFAULT_ACCOUNT_SIZE,
    CS_WHITELIST,
    OPP_SCORE_MIN_SHOW,
)
from core.credit_spread_scanner import (
    scan_credit_spreads as _scan,
    generate_alerts as _gen_alerts,
    opportunity_score_breakdown as _score_breakdown,
    compute_income_score as _income_score,
    compute_opportunity_score as _opp_score,
    calculate_probability_of_touch,          # Fase 1 — PoT
)

logger = logging.getLogger(__name__)


class CreditSpreadService:
    """Orquesta el escaneo de credit spreads y la generación de alertas.

    Esta clase es el **único punto de acceso** de la capa de presentación
    al scanner.  Encapsula los parámetros por defecto y normaliza
    la interfaz de salida.

    Ejemplo de uso en una página::

        svc = CreditSpreadService()
        df, indicators = svc.scan(tickers=["SPY", "QQQ"], strict=True)
        alerts = svc.get_alerts(df, account_size=10_000)
    """

    # ── Whitelist accesible para la UI ─────────────────────────────────
    WHITELIST: list[str] = list(CS_WHITELIST)

    def scan(
        self,
        tickers: list[str],
        min_pop: float = 0.70,
        max_dte: int = 45,
        min_credit: float = 0.30,
        strict: bool = True,
        strict_rules: dict | None = None,
        account_size: float = ALERT_DEFAULT_ACCOUNT_SIZE,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
        """Ejecuta el scanner completo y devuelve DataFrame + indicadores por ticker.

        Args:
            tickers: lista de símbolos a escanear.
            min_pop: probabilidad mínima de ganancia (0-1).
            max_dte: máximo de DTE.
            min_credit: crédito mínimo en USD.
            strict: si True, aplica los 9 filtros del pipeline.
            strict_rules: reglas individuales activadas (prioridad sobre strict).
            account_size: tamaño de cuenta para cálculo de riesgo.
            progress_callback: fn(ticker, idx, total) para reportar progreso.

        Returns:
            (df, ticker_indicators):
                df — DataFrame con todas las oportunidades encontradas.
                ticker_indicators — dict {ticker: {iv_rank, trend, price, …}}.
        """
        logger.info(
            "CreditSpreadService.scan — tickers=%s, strict=%s, pop>=%.0f%%",
            tickers, strict, min_pop * 100,
        )
        df, ticker_indicators = _scan(
            tickers=tickers,
            min_pop=min_pop,
            max_dte=max_dte,
            min_credit=min_credit,
            progress_callback=progress_callback,
            strict=strict,
            strict_rules=strict_rules,
        )
        return df, ticker_indicators

    def get_alerts(
        self,
        df: pd.DataFrame,
        account_size: float = ALERT_DEFAULT_ACCOUNT_SIZE,
        strict_rules: dict | None = None,
    ) -> pd.DataFrame:
        """Aplica las reglas de seguridad y devuelve las alertas accionables.

        Las reglas respetan strict_rules: las desactivadas se saltan.
        La Regla 8 (riesgo de cuenta) siempre se verifica.
        """
        if df is None or df.empty:
            return pd.DataFrame()
        return _gen_alerts(df, account_size=account_size, strict_rules=strict_rules)

    def score_breakdown(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        """Devuelve el desglose de puntaje para un spread específico.

        Útil para el panel educativo / hover card de la tabla de resultados.

        Args:
            row: dict con los datos de un spread (como sale del DataFrame).

        Returns:
            Lista de dicts con criterio, detalle, puntos, maximo, cumple.
        """
        return _score_breakdown(row)

    def compute_scores(self, row: dict[str, Any]) -> dict[str, Any]:
        """Calcula ambos scores (Income + Oportunidad) para un spread.

        Args:
            row: dict con los datos de un spread.

        Returns:
            dict con income_score, income_label, opp_score, opp_label.
        """
        inc_score, inc_label = _income_score(row)
        opp_score, opp_label = _opp_score(row)
        return {
            "income_score": inc_score,
            "income_label": inc_label,
            "opp_score": opp_score,
            "opp_label": opp_label,
        }

    @staticmethod
    def filter_by_score(
        df: pd.DataFrame,
        min_score: int = OPP_SCORE_MIN_SHOW,
    ) -> pd.DataFrame:
        """Filtra el DataFrame de resultados por Score de Oportunidad mínimo.

        Args:
            df: DataFrame de resultados del scanner.
            min_score: score mínimo para incluir (default: 60).

        Returns:
            DataFrame filtrado (copia).
        """
        if df is None or df.empty:
            return pd.DataFrame()
        col = "Score Oportunidad"
        if col not in df.columns:
            return df
        return df[df[col] >= min_score].copy()
