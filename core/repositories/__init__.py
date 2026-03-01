# -*- coding: utf-8 -*-
"""
core/repositories — abstract repository contracts.

Las interfaces (``Protocol``) viven en ``core/protocols.py`` para evitar
dependencias circulares.  Este paquete re-exporta los tipos más usados
para conveniencia::

    from core.repositories import UserRepository
"""
from core.protocols import UserRepository, CacheProvider

__all__ = ["UserRepository", "CacheProvider"]
