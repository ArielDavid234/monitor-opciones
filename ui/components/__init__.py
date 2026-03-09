# -*- coding: utf-8 -*-
"""
ui.components -- paquete compatible con el modulo original ui/components.py

Cuando Python encuentra este directorio, lo elige sobre ui/components.py.
Este __init__.py ejecuta el contenido del archivo original en su propio
namespace para mantener compatibilidad con todos los imports existentes:
    from ui.components import render_pro_table
    from ui.components import render_metric_card, _sentiment_badge, ...
"""
from __future__ import annotations
import os as _os

_path = _os.path.normpath(
    _os.path.join(_os.path.dirname(__file__), "..", "components.py")
)
with open(_path, encoding="utf-8") as _f:
    exec(compile(_f.read(), _path, "exec"), globals())

del _os, _path, _f
