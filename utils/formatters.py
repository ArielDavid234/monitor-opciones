# -*- coding: utf-8 -*-
"""
Funciones de formateo reutilizables para toda la UI.
Extraídas de app_web.py — cero cambios de lógica.
"""
import numpy as np
import pandas as pd


# ============================================================================
#                    HELPERS DE FORMATEO REUTILIZABLES
# ============================================================================
def _fmt_dolar(x):
    """Formatea un valor como moneda: $1,234."""
    return f"${x:,.0f}" if x > 0 else "$0"


def _fmt_iv(x):
    """Formatea IV como porcentaje: 25.3%."""
    return f"{x:.1f}%" if x > 0 else "-"


def _fmt_precio(x):
    """Formatea un precio: $1.23."""
    return f"${x:.2f}" if x > 0 else "-"


def _fmt_entero(x):
    """Formatea un entero con separadores: 1,234."""
    return f"{int(x):,}"


def _fmt_monto(v):
    """Formatea un monto grande: $1.2M, $50K, $1,234."""
    if v >= 1_000_000:
        return f"${v / 1_000_000:.1f}M"
    elif v >= 1_000:
        return f"${v / 1_000:.0f}K"
    return f"${v:,.0f}"


def _fmt_oi(x):
    """Formatea Open Interest con comas."""
    try:
        return f"{int(x):,}" if x and x > 0 else "0"
    except (ValueError, TypeError):
        return "0"


def _fmt_oi_chg(x):
    """Formatea OI Change con signo: +1,234 o -567."""
    try:
        return f"+{int(x):,}" if x > 0 else f"{int(x):,}" if x < 0 else "0"
    except (ValueError, TypeError):
        return "0"


def _fmt_delta(x):
    """Formatea delta de opción. Calls: 0.00–1.00 | Puts: -1.00–0.00"""
    try:
        if x is None:
            return "N/D"
        return f"{float(x):+.4f}"
    except (ValueError, TypeError):
        return "N/D"


def _fmt_gamma(x):
    """Formatea gamma (∂Δ/∂S). Siempre positivo, 6 decimales."""
    try:
        if x is None:
            return "N/D"
        return f"{float(x):.6f}"
    except (ValueError, TypeError):
        return "N/D"


def _fmt_theta(x):
    """Formatea theta (decay diario). Negativo para opciones largas."""
    try:
        if x is None:
            return "N/D"
        return f"{float(x):+.4f}"
    except (ValueError, TypeError):
        return "N/D"


def _fmt_rho(x):
    """Formatea rho (sensibilidad a tasa por 1%)."""
    try:
        if x is None:
            return "N/D"
        return f"{float(x):+.4f}"
    except (ValueError, TypeError):
        return "N/D"


def _fmt_lado(lado):
    """Formatea el lado de ejecución con emoji indicador."""
    if lado == "Ask":
        return "🟢 Ask"   # Compra agresiva
    elif lado == "Bid":
        return "🔴 Bid"   # Venta agresiva
    elif lado == "Mid":
        return "⚪ Mid"
    return "➖ N/A"


def determinar_sentimiento(tipo_opcion, lado):
    """
    Determina el sentimiento de la operación según el tipo de opción y lado de ejecución.
    
    Alcista (Verde) - Apuesta a que el precio suba:
    - CALL + Ask (compra de CALL)
    - PUT + Bid (venta de PUT)
    
    Bajista (Rojo) - Apuesta a que el precio baje:
    - PUT + Ask (compra de PUT)
    - CALL + Bid (venta de CALL)
    
    Returns:
        tuple: (sentimiento_texto, emoji, color_hex)
    """
    if tipo_opcion == "CALL" and lado == "Ask":
        return "ALCISTA", "🟢", "#10b981"
    elif tipo_opcion == "PUT" and lado == "Bid":
        return "ALCISTA", "🟢", "#10b981"
    elif tipo_opcion == "PUT" and lado == "Ask":
        return "BAJISTA", "🔴", "#ef4444"
    elif tipo_opcion == "CALL" and lado == "Bid":
        return "BAJISTA", "🔴", "#ef4444"
    else:
        return "NEUTRAL", "⚪", "#94a3b8"
