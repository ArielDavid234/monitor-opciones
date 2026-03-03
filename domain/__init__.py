# -*- coding: utf-8 -*-
"""
domain — Capa de dominio puro.

Contiene las entidades, enums y value objects que representan el
modelo de negocio.  **Cero dependencias** de Streamlit, infraestructura
o frameworks.

Uso:
    from domain.entities import User, CreditSpread, Trend
"""

from domain.entities import *  # noqa: F401,F403
from domain.entities import __all__  # re-export catalog
