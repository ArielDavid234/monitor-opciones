"""
Detección de clusters de compras continuas (posible actividad institucional).
"""
from collections import defaultdict

from config.constants import (
    CLUSTER_TOLERANCE_PCT,
    CLUSTER_TOLERANCE_MULTIPLIER,
    CLUSTER_MAX_STRIKE_DIFF,
    CLUSTER_MIN_ALERTS,
)


def detectar_compras_continuas(alertas, umbral_prima_ref, tolerancia_pct=CLUSTER_TOLERANCE_PCT):
    """
    Detecta clusters de compras consecutivas similares que podrían ser
    del mismo comprador institucional fragmentando órdenes.

    Lógica: agrupa alertas por mismo Tipo (CALL/PUT) + mismo Vencimiento.
    Dentro de cada grupo, busca múltiples contratos con strikes cercanos
    cuyas primas estén en un rango similar (dentro de tolerancia_pct del
    umbral de prima configurado).

    Parámetros:
    - alertas: lista de diccionarios de alertas
    - umbral_prima_ref: la prima mínima configurada por el usuario
    - tolerancia_pct: % de variación permitida para considerar primas "similares"
                      (0.50 = ±50% del umbral)

    Retorna: lista de clusters detectados, cada uno con:
    - tipo, vencimiento, strikes, conteo, prima_total, contratos_detalle
    """
    if len(alertas) < CLUSTER_MIN_ALERTS:
        return []

    # Agrupar por Tipo_Opcion + Vencimiento
    grupos = defaultdict(list)
    for a in alertas:
        clave = (a["Tipo_Opcion"], a["Vencimiento"])
        grupos[clave].append(a)

    clusters = []
    prima_min = umbral_prima_ref * (1 - tolerancia_pct)
    prima_max_rango = umbral_prima_ref * (1 + tolerancia_pct * CLUSTER_TOLERANCE_MULTIPLIER)

    for (tipo_op, venc), grupo in grupos.items():
        if len(grupo) < 2:
            continue

        # Ordenar por strike
        grupo_sorted = sorted(grupo, key=lambda x: x["Strike"])

        i = 0
        while i < len(grupo_sorted):
            subgrupo = [grupo_sorted[i]]
            j = i + 1
            while j < len(grupo_sorted):
                diff_strike = abs(grupo_sorted[j]["Strike"] - subgrupo[-1]["Strike"])
                prima_j = max(grupo_sorted[j]["Prima_Volumen"], grupo_sorted[j]["Prima_OI"])

                if diff_strike <= CLUSTER_MAX_STRIKE_DIFF:
                    subgrupo.append(grupo_sorted[j])
                    j += 1
                else:
                    break

            if len(subgrupo) >= 2:
                primas = [max(a["Prima_Volumen"], a["Prima_OI"]) for a in subgrupo]
                primas_en_rango = sum(
                    1 for p in primas if p >= prima_min
                )

                if primas_en_rango >= 2:
                    prima_total = sum(primas)
                    strikes = sorted(set(a["Strike"] for a in subgrupo))
                    strike_min = min(strikes)
                    strike_max = max(strikes)

                    clusters.append({
                        "Tipo_Opcion": tipo_op,
                        "Vencimiento": venc,
                        "Contratos": len(subgrupo),
                        "Strike_Min": strike_min,
                        "Strike_Max": strike_max,
                        "Strikes": strikes,
                        "Prima_Total": prima_total,
                        "Prima_Promedio": prima_total / len(subgrupo),
                        "Vol_Total": sum(a["Volumen"] for a in subgrupo),
                        "OI_Total": sum(a["OI"] for a in subgrupo),
                        "OI_Chg_Total": sum(a.get("OI_Chg", 0) for a in subgrupo),
                        "Detalle": subgrupo,
                    })

            i = j if j > i + 1 else i + 1

    clusters.sort(key=lambda c: c["Prima_Total"], reverse=True)
    return clusters
