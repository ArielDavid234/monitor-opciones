"""
Módulo de seguimiento de cambios en Open Interest (OI).
Compara el OI entre escaneos consecutivos para detectar
acumulación o reducción de interés en contratos de opciones.
"""
import pandas as pd
from datetime import datetime


def calcular_cambios_oi(datos_actuales, datos_anteriores):
    """
    Compara dos conjuntos de datos de escaneo y calcula el cambio en OI.

    Args:
        datos_actuales: lista de dicts del escaneo actual
        datos_anteriores: lista de dicts del escaneo anterior

    Returns:
        DataFrame con columnas: Vencimiento, Tipo, Strike, OI_Anterior,
        OI_Actual, Cambio_OI, Cambio_Pct, Volumen, Ask, Bid, Ultimo, IV,
        Prima_OI, Señal
    """
    if not datos_actuales or not datos_anteriores:
        return pd.DataFrame()

    df_actual = pd.DataFrame(datos_actuales)
    df_anterior = pd.DataFrame(datos_anteriores)

    # Clave única por contrato
    key_cols = ["Vencimiento", "Tipo", "Strike"]

    # Verificar que existan las columnas necesarias
    for col in key_cols + ["OI"]:
        if col not in df_actual.columns or col not in df_anterior.columns:
            return pd.DataFrame()

    # Merge por contrato
    merged = pd.merge(
        df_anterior[key_cols + ["OI"]].rename(columns={"OI": "OI_Anterior"}),
        df_actual[key_cols + ["OI", "Volumen", "Ask", "Bid", "Ultimo", "IV"]],
        on=key_cols,
        how="outer",
        suffixes=("_ant", "_act"),
    )

    # Rellenar NaN con 0 (contratos nuevos o eliminados)
    merged["OI_Anterior"] = merged["OI_Anterior"].fillna(0).astype(int)
    merged["OI"] = merged["OI"].fillna(0).astype(int)
    merged["Volumen"] = merged["Volumen"].fillna(0).astype(int)

    # Calcular cambio
    merged["Cambio_OI"] = merged["OI"] - merged["OI_Anterior"]
    merged["Cambio_Pct"] = merged.apply(
        lambda r: round((r["Cambio_OI"] / r["OI_Anterior"]) * 100, 2)
        if r["OI_Anterior"] > 0 else (100.0 if r["OI"] > 0 else 0.0),
        axis=1,
    )

    # Clasificar señal
    merged["Señal"] = merged.apply(_clasificar_señal, axis=1)

    # Renombrar OI actual
    merged = merged.rename(columns={"OI": "OI_Actual"})

    # Ordenar por magnitud de cambio absoluto
    merged["_abs_cambio"] = merged["Cambio_OI"].abs()
    merged = merged.sort_values("_abs_cambio", ascending=False).drop(columns=["_abs_cambio"])

    # Filtrar solo contratos con algún cambio o con OI > 0
    merged = merged[(merged["Cambio_OI"] != 0) | (merged["OI_Actual"] > 0)]

    return merged.reset_index(drop=True)


def _clasificar_señal(row):
    """Clasifica la señal del cambio en OI."""
    cambio = row["Cambio_OI"]
    oi_anterior = row["OI_Anterior"]

    if cambio == 0:
        return "Sin cambio"

    # Calcular magnitud relativa
    if oi_anterior > 0:
        pct = abs(cambio) / oi_anterior * 100
    else:
        pct = 100  # Contrato nuevo

    if cambio > 0:
        if pct >= 50:
            return "🟢 Acumulación fuerte"
        elif pct >= 20:
            return "🟢 Acumulación moderada"
        elif pct >= 5:
            return "🟡 Acumulación leve"
        else:
            return "⚪ Ligero aumento"
    else:
        if pct >= 50:
            return "🔴 Reducción fuerte"
        elif pct >= 20:
            return "🔴 Reducción moderada"
        elif pct >= 5:
            return "🟠 Reducción leve"
        else:
            return "⚪ Ligera reducción"


def resumen_oi(cambios_df):
    """
    Genera un resumen estadístico de los cambios en OI.

    Returns:
        dict con métricas clave del cambio en OI
    """
    if cambios_df.empty:
        return {
            "total_contratos": 0,
            "con_aumento": 0,
            "con_reduccion": 0,
            "sin_cambio": 0,
            "mayor_aumento": None,
            "mayor_reduccion": None,
            "oi_neto": 0,
            "calls_neto": 0,
            "puts_neto": 0,
        }

    con_aumento = cambios_df[cambios_df["Cambio_OI"] > 0]
    con_reduccion = cambios_df[cambios_df["Cambio_OI"] < 0]
    sin_cambio = cambios_df[cambios_df["Cambio_OI"] == 0]

    mayor_aum = None
    if not con_aumento.empty:
        row = con_aumento.loc[con_aumento["Cambio_OI"].idxmax()]
        mayor_aum = {
            "strike": row["Strike"],
            "tipo": row["Tipo"],
            "venc": row["Vencimiento"],
            "cambio": int(row["Cambio_OI"]),
            "oi_actual": int(row["OI_Actual"]),
        }

    mayor_red = None
    if not con_reduccion.empty:
        row = con_reduccion.loc[con_reduccion["Cambio_OI"].idxmin()]
        mayor_red = {
            "strike": row["Strike"],
            "tipo": row["Tipo"],
            "venc": row["Vencimiento"],
            "cambio": int(row["Cambio_OI"]),
            "oi_actual": int(row["OI_Actual"]),
        }

    calls_df = cambios_df[cambios_df["Tipo"] == "CALL"]
    puts_df = cambios_df[cambios_df["Tipo"] == "PUT"]

    return {
        "total_contratos": len(cambios_df),
        "con_aumento": len(con_aumento),
        "con_reduccion": len(con_reduccion),
        "sin_cambio": len(sin_cambio),
        "mayor_aumento": mayor_aum,
        "mayor_reduccion": mayor_red,
        "oi_neto": int(cambios_df["Cambio_OI"].sum()),
        "calls_neto": int(calls_df["Cambio_OI"].sum()) if not calls_df.empty else 0,
        "puts_neto": int(puts_df["Cambio_OI"].sum()) if not puts_df.empty else 0,
    }


def filtrar_contratos_oi(cambios_df, tipo=None, solo_cambios=True, min_oi=0, señal=None):
    """
    Filtra el DataFrame de cambios OI según criterios.

    Args:
        cambios_df: DataFrame de calcular_cambios_oi()
        tipo: "CALL", "PUT" o None para ambos
        solo_cambios: True = mostrar solo contratos con cambio != 0
        min_oi: OI mínimo actual para mostrar
        señal: filtrar por tipo de señal (substring match)
    """
    if cambios_df.empty:
        return cambios_df

    df = cambios_df.copy()

    if tipo:
        df = df[df["Tipo"] == tipo]

    if solo_cambios:
        df = df[df["Cambio_OI"] != 0]

    if min_oi > 0:
        df = df[df["OI_Actual"] >= min_oi]

    if señal:
        df = df[df["Señal"].str.contains(señal, case=False, na=False)]

    return df.reset_index(drop=True)
