# -*- coding: utf-8 -*-
"""
ui.components -- paquete compatible con el modulo original ui/components.py

Cuando Python encuentra este directorio, lo elige sobre ui/components.py.
Este __init__.py carga el archivo original como modulo real via importlib,
registrandolo en sys.modules antes de ejecutarlo para evitar problemas de
imports circulares y de rutas en Streamlit Cloud.
"""
import sys as _sys
import os as _os
import importlib.util as _ilu

_path = _os.path.normpath(
    _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "components.py")
)
_spec = _ilu.spec_from_file_location("ui._components_orig", _path)
_mod = _ilu.module_from_spec(_spec)
_sys.modules["ui._components_orig"] = _mod        # registrar ANTES de exec
_spec.loader.exec_module(_mod)                     # cualquier error se propaga correctamente

# Re-exportar todos los nombres publicos Y los de un solo guion bajo
# (ej: _sentiment_badge, _type_badge, _priority_badge)
globals().update({k: v for k, v in vars(_mod).items() if not k.startswith("__")})

del _sys, _os, _ilu, _path, _spec, _mod
