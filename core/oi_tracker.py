"""
Módulo de seguimiento de cambios en Open Interest (OI).
Compara el OI entre escaneos consecutivos para detectar
acumulación o reducción de interés en contratos de opciones.
"""
import pandas as pd


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
