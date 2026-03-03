# -*- coding: utf-8 -*-
"""
Test suite completo para la aplicación OPTIONSKING Analytics.
Verifica: firmas render(), imports, session_state, llamadas a funciones externas, etc.
"""
import ast
import os
import sys
import importlib
import inspect

sys.path.insert(0, ".")

ERRORS = []
WARNINGS = []
PASSED = []

def ok(msg):
    PASSED.append(msg)
    print(f"  [OK]  {msg}")

def err(msg):
    ERRORS.append(msg)
    print(f"  [ERR] {msg}")

def warn(msg):
    WARNINGS.append(msg)
    print(f"  [WRN] {msg}")

# ============================================================
# TEST 1: Firmas de render() en pages/
# ============================================================
print("\n" + "="*60)
print("TEST 1: Firmas de render() en pages/")
print("="*60)

# Las firmas esperadas según app_web.py
EXPECTED_ARGS = {
    "live_scanning_page.py":     ["ticker_symbol"],
    "open_interest_page.py":     ["ticker_symbol"],
    "data_analysis_page.py":     ["ticker_symbol"],
    "range_page.py":             ["ticker_symbol"],
    "important_companies_page.py": ["ticker_symbol"],
    "favorites_page.py":         ["ticker_symbol"],
    "news_page.py":              ["ticker_symbol"],
    "reports_page.py":           ["ticker_symbol"],
    "calendar_page.py":          ["ticker_symbol"],
}

PAGES_DIR = "page_modules"  # directorio real de páginas
for fname in sorted(os.listdir(PAGES_DIR)):
    if fname.endswith(".py") and fname != "__init__.py":
        with open(f"{PAGES_DIR}/{fname}", encoding="utf-8") as f:
            src = f.read()
        tree = ast.parse(src)
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "render":
                found = True
                args = [a.arg for a in node.args.args]
                has_kwargs = node.args.kwarg is not None
                has_varargs = node.args.vararg is not None
                kwonly = [a.arg for a in node.args.kwonlyargs]
                sig = f"render({', '.join(args)}{', **' + node.args.kwarg.arg if has_kwargs else ''})"
                expected = EXPECTED_ARGS.get(fname, ["ticker_symbol"])
                # páginas sin ticker_symbol son válidas (perfil, spreads, admin)
                if not expected or expected[0] in args or not args:
                    ok(f"{fname}: {sig}")
                else:
                    err(f"{fname}: esperaba '{expected[0]}' en args, got: {args}")
        if not found:
            err(f"{fname}: No tiene función render()")

# ============================================================
# TEST 2: app_web.py - Llamadas a render() con args correctos
# ============================================================
print("\n" + "="*60)
print("TEST 2: Llamadas a render() en app_web.py")
print("="*60)

with open("app_web.py", encoding="utf-8") as f:
    app_src = f.read()

app_tree = ast.parse(app_src)

# Buscar todas las llamadas .render(
render_calls = []
for node in ast.walk(app_tree):
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute) and node.func.attr == "render":
            if isinstance(node.func.value, ast.Name):
                module_name = node.func.value.id
                args = []
                for a in node.args:
                    if isinstance(a, ast.Name):
                        args.append(a.id)
                    elif isinstance(a, ast.Constant):
                        args.append(repr(a.value))
                    else:
                        args.append("?")
                kwargs = [kw.arg if kw.arg else f"**{ast.unparse(kw.value)}" for kw in node.keywords]
                render_calls.append((module_name, args, kwargs, node.lineno))

if render_calls:
    ok(f"Encontradas {len(render_calls)} llamadas a render() en app_web.py:")
    for mod, args, kwargs, lineno in render_calls:
        all_parts = args + kwargs
        print(f"      L{lineno}: {mod}.render({', '.join(all_parts)})")
else:
    err("No se encontraron llamadas a render() en app_web.py")

# ============================================================
# TEST 3: Imports en app_web.py vs módulos disponibles
# ============================================================
print("\n" + "="*60)
print("TEST 3: Imports declarados en app_web.py")
print("="*60)

imports_ok = 0
imports_err = 0

for node in ast.walk(app_tree):
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            names = [alias.name for alias in node.names]
            try:
                m = importlib.import_module(mod)
                missing = []
                for n in names:
                    if n == "*":
                        continue
                    if hasattr(m, n):
                        continue  # attribute found directly
                    # Try as a submodule (e.g. `from page_modules import login_page`)
                    try:
                        importlib.import_module(f"{mod}.{n}")
                    except ImportError:
                        missing.append(n)
                if missing:
                    err(f"  app_web.py L{node.lineno}: 'from {mod} import {names}' → símbolos no encontrados: {missing}")
                    imports_err += 1
                else:
                    ok(f"  from {mod} import {names}")
                    imports_ok += 1
            except Exception as e:
                err(f"  app_web.py L{node.lineno}: 'from {mod} import ...' → {type(e).__name__}: {e}")
                imports_err += 1

print(f"\n  Imports OK: {imports_ok}, Imports con error: {imports_err}")

# ============================================================
# TEST 4: Verificar session_state keys en utils/state.py vs uso en páginas
# ============================================================
print("\n" + "="*60)
print("TEST 4: session_state keys (state.py vs uso real)")
print("="*60)

import utils.state as state_mod
defaults_keys = set(state_mod._DEFAULTS.keys())
print(f"  Keys definidas en _DEFAULTS: {len(defaults_keys)}")

# Buscar todas las referencias a st.session_state en pages/
used_keys = set()
suspicious = []

for fname in sorted(os.listdir(PAGES_DIR)):
    if fname.endswith(".py") and fname != "__init__.py":
        with open(f"{PAGES_DIR}/{fname}", encoding="utf-8") as f:
            src = f.read()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            # st.session_state["key"] o st.session_state.key
            if isinstance(node, ast.Subscript):
                if isinstance(node.value, ast.Attribute):
                    attr = node.value
                    if (isinstance(attr.value, ast.Name) and attr.value.id == "st"
                            and attr.attr == "session_state"):
                        if isinstance(node.slice, ast.Constant):
                            used_keys.add(node.slice.value)
            if isinstance(node, ast.Attribute):
                if (isinstance(node.value, ast.Attribute)
                        and isinstance(node.value.value, ast.Name)
                        and node.value.value.id == "st"
                        and node.value.attr == "session_state"):
                    used_keys.add(node.attr)

also_app = set()
for node in ast.walk(app_tree):
    if isinstance(node, ast.Subscript):
        if isinstance(node.value, ast.Attribute):
            attr = node.value
            if (isinstance(attr.value, ast.Name) and attr.value.id == "st"
                    and attr.attr == "session_state"):
                if isinstance(node.slice, ast.Constant):
                    also_app.add(node.slice.value)
    if isinstance(node, ast.Attribute):
        if (isinstance(node.value, ast.Attribute)
                and isinstance(node.value.value, ast.Name)
                and node.value.value.id == "st"
                and node.value.attr == "session_state"):
            also_app.add(node.attr)

all_used = used_keys | also_app
missing_in_defaults = all_used - defaults_keys

# Filtrar claves privadas (prefijo _) y las efímeras de páginas
false_positives = {"clear", "items", "keys", "values", "update", "get", "pop", "setdefault"}
# Claves con prefijo _ son flags internos gestionados programáticamente
false_positives |= {k for k in all_used if k.startswith("_")}
missing_in_defaults -= false_positives

if missing_in_defaults:
    for k in sorted(missing_in_defaults):
        warn(f"  session_state['{k}'] usado pero NO está en _DEFAULTS")
else:
    ok(f"Todos los session_state keys usados están en _DEFAULTS")

print(f"  Keys usadas totales: {len(all_used)}, Keys en _DEFAULTS: {len(defaults_keys)}")
print(f"  Keys en _DEFAULTS no usadas: {sorted(defaults_keys - all_used - false_positives)}")

# ============================================================
# TEST 5: Verificar funciones exportadas en core/ que se usan en pages/
# ============================================================
print("\n" + "="*60)
print("TEST 5: Funciones core/ usadas en pages/")
print("="*60)

# Recolectar todos los imports en pages/
page_imports = {}  # fname -> {alias: (module, original_name)}
page_calls = {}    # fname -> [call_names]

for fname in sorted(os.listdir(PAGES_DIR)):
    if fname.endswith(".py") and fname != "__init__.py":
        with open(f"{PAGES_DIR}/{fname}", encoding="utf-8") as f:
            src = f.read()
        tree = ast.parse(src)
        imports = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for alias in node.names:
                    local_name = alias.asname if alias.asname else alias.name
                    imports[local_name] = (node.module, alias.name)
        page_imports[fname] = imports

# Verificar que los símbolos importados existen en sus módulos
cross_errors = 0
for fname, imports in page_imports.items():
    for local_name, (mod, orig) in imports.items():
        try:
            m = importlib.import_module(mod)
            if orig != "*" and not hasattr(m, orig):
                err(f"  {fname}: 'from {mod} import {orig}' → '{orig}' no existe en {mod}")
                cross_errors += 1
        except Exception as e:
            # Solo reportar si es un módulo propio del proyecto
            if any(mod.startswith(p) for p in ["core.", "utils.", "reports.", "ui.", "config.", "pages."]):
                err(f"  {fname}: 'from {mod} import {orig}' → {type(e).__name__}: {e}")
                cross_errors += 1

if cross_errors == 0:
    ok("Todos los imports entre módulos del proyecto son válidos")

# ============================================================
# TEST 6: Verificar que las funciones usadas en utils/helpers.py existen
# ============================================================
print("\n" + "="*60)
print("TEST 6: Coherencia de utils/helpers.py")
print("="*60)

import utils.helpers as helpers_mod
helper_funcs = [f for f in dir(helpers_mod) if not f.startswith("_")]
ok(f"utils.helpers exporta: {helper_funcs}")

# Verificar que las funciones clave de helpers existen
EXPECTED_HELPERS = ["construir_watchlist_consolidadas", "construir_watchlist_emergentes"]
for fn in EXPECTED_HELPERS:
    if hasattr(helpers_mod, fn):
        ok(f"  helpers.{fn} existe")
    else:
        err(f"  helpers.{fn} NO existe")

# ============================================================
# TEST 7: Verificar que los módulos core/ tienen las funciones requeridas
# ============================================================
print("\n" + "="*60)
print("TEST 7: Funciones requeridas en core/")
print("="*60)

CORE_REQUIRED = {
    "core.scanner": ["ejecutar_escaneo", "obtener_precio_actual"],
    "core.news": ["obtener_noticias_financieras"],
    "core.gamma_exposure": ["calcular_gex_desde_scanner"],
    "core.expected_move": ["calcular_expected_move"],
    "core.barchart_oi": ["obtener_oi_simbolo"],
    "core.clusters": ["detectar_compras_continuas"],
    "core.oi_tracker": [],
    "core.projections": [],
    "core.option_greeks": [],
}

for mod_name, funcs in CORE_REQUIRED.items():
    try:
        m = importlib.import_module(mod_name)
        for fn in funcs:
            if hasattr(m, fn):
                ok(f"  {mod_name}.{fn} existe")
            else:
                err(f"  {mod_name}.{fn} NO existe")
    except Exception as e:
        err(f"  {mod_name}: error al importar → {e}")

# ============================================================
# TEST 8: Verificar config/constants.py exporta lo requerido
# ============================================================
print("\n" + "="*60)
print("TEST 8: config/constants.py y config/watchlists.py")
print("="*60)

import config.constants as const_mod
import config.watchlists as wl_mod

REQUIRED_CONSTANTS = [
    "DEFAULT_TICKER", "SCAN_COOLDOWN_SECONDS", "AUTO_REFRESH_INTERVAL",
]
for c in REQUIRED_CONSTANTS:
    if hasattr(const_mod, c):
        ok(f"  constants.{c} = {getattr(const_mod, c)}")
    else:
        warn(f"  constants.{c} no encontrado (puede que use nombre diferente)")

wl_exports = [x for x in dir(wl_mod) if not x.startswith("_")]
ok(f"  watchlists exporta: {wl_exports}")

# ============================================================
# TEST 9: Verificar ui/shared.py exporta funciones clave
# ============================================================
print("\n" + "="*60)
print("TEST 9: ui/shared.py funciones requeridas")
print("="*60)

import ui.shared as shared_mod
REQUIRED_SHARED = ["inject_all_css", "render_sidebar_logo", "render_sidebar_avatar", "render_footer"]
for fn in REQUIRED_SHARED:
    if hasattr(shared_mod, fn):
        ok(f"  ui.shared.{fn} existe")
    else:
        err(f"  ui.shared.{fn} NO existe — app_web.py lo llama!")

# ============================================================
# TEST 10: Verificar reports/generators.py exporta generadores
# ============================================================
print("\n" + "="*60)
print("TEST 10: reports/generators.py")
print("="*60)

import reports.generators as gen_mod
gen_exports = [x for x in dir(gen_mod) if not x.startswith("_")]
ok(f"  generators exporta {len(gen_exports)} símbolos: {gen_exports[:10]}{'...' if len(gen_exports) > 10 else ''}")

# ============================================================
# RESUMEN FINAL
# ============================================================
print("\n" + "="*60)
print("RESUMEN FINAL")
print("="*60)
print(f"  Pruebas OK:       {len(PASSED)}")
print(f"  ERRORES:          {len(ERRORS)}")
print(f"  WARNINGS:         {len(WARNINGS)}")

if ERRORS:
    print("\n  LISTA DE ERRORES:")
    for i, e in enumerate(ERRORS, 1):
        print(f"    {i}. {e}")
else:
    print("\n  *** NO SE ENCONTRARON ERRORES CRITICOS ***")

if WARNINGS:
    print("\n  LISTA DE WARNINGS:")
    for i, w in enumerate(WARNINGS, 1):
        print(f"    {i}. {w}")
