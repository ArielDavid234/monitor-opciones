# -*- coding: utf-8 -*-
"""
core — Capa de dominio y aplicación.

Contiene:
  - ``entities``    — modelos Pydantic (User, CreditSpread, ScanResult, …)
  - ``protocols``   — interfaces/contratos (AuthProvider, CacheProvider, …)
  - ``services/``   — lógica de negocio (CreditSpreadService, ScanService, …)
  - ``repositories/`` — abstracciones de acceso a datos
  - ``container``   — inyección de dependencias

Regla de oro: **nada en este paquete depende de Streamlit ni de
infraestructura concreta**.  Las únicas excepciones autorizadas son
``auth.py`` (que usa ``st.secrets`` por pragmatismo) y ``scan_service.py``
(que usa ``st.session_state`` para estado de UI transiente).
"""

# Importar sólo lo necesario para que el paquete esté listo.
# Los consumidores importan directamente desde los submódulos:
#   from domain.entities import User
#   from core.protocols import AuthProvider
#   from core.container import get_container

__all__: list[str] = []
