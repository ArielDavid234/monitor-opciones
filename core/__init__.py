# -*- coding: utf-8 -*-
"""
core — Motor de negocio y lógica de aplicación.

Módulos principales
-------------------
  Arquitectura / DI:
    ``protocols``            — interfaces (AuthProvider, CacheProvider, UserRepository)
    ``container``            — inyección de dependencias
    ``entities``             — re-export shim → ``domain.entities``

  Servicios (services/):
    ``credit_spread_service``— lógica de credit spreads
    ``scan_service``         — orquestación de scans
    ``user_service``         — gestión de usuarios y stats

  Motores de cálculo:
    ``option_greeks``        — BSM pricing & Greeks (fuente canónica)
    ``gamma_exposure``       — GEX calculator
    ``iv_rank``              — IV Rank / IV Percentile
    ``expected_move``        — rango esperado Black-Scholes
    ``monte_carlo``          — simulación GBM de precios
    ``optionkings_analytic`` — EV, Income Score, filtros, Monte Carlo spreads
    ``credit_spread_scanner``— scanner automático de credit spreads
    ``oka_sentiment_v2``     — OKA Sentiment Index v2

  Data / scraping:
    ``scanner``              — escaneo de opciones inusuales (yfinance + curl_cffi)
    ``barchart_oi``          — Open Interest desde Barchart
    ``oi_tracker``           — seguimiento de cambios en OI
    ``news``                 — RSS feeds financieros
    ``economic_calendar``    — calendario económico
    ``projections``          — análisis de crecimiento y PEG

  Clasificación / detección:
    ``anomaly_detector``     — detección de anomalías en flujo
    ``flow_classifier``      — clasificación de flujo institucional
    ``clusters``             — detección de compras continuas
    ``smart_money``          — rastreo de dinero institucional
    ``watchlist_builder``    — constructor dinámico de watchlists

  Auth:
    ``auth``                 — autenticación Supabase + PKCE

Regla de oro: **nada en este paquete depende de Streamlit ni de
infraestructura concreta**.  Excepciones autorizadas:
  - ``auth.py`` (usa ``st.secrets`` por pragmatismo)
  - ``scan_service.py`` (usa ``st.session_state`` para estado de UI)
"""

# Los consumidores importan directamente desde los submódulos:
#   from domain.entities import User
#   from core.protocols import AuthProvider
#   from core.container import get_container

__all__: list[str] = []
