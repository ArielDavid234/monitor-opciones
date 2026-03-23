"""Persistencia de alertas CSV extraida de core.scanner."""

from __future__ import annotations

import csv
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


def guardar_alerta_csv(carpeta: str, ticker_sym: str, alerta: dict) -> None:
    """Guarda una alerta individual en el archivo CSV diario."""
    try:
        os.makedirs(carpeta, exist_ok=True)
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        csv_path = os.path.join(carpeta, f"alertas_{ticker_sym}_{fecha_hoy}.csv")
        escribir_header = not os.path.exists(csv_path)

        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "Fecha_Hora",
                    "Ticker",
                    "Tipo_Alerta",
                    "Tipo_Opcion",
                    "Vencimiento",
                    "Strike",
                    "Volumen",
                    "OI",
                    "Prima_Total",
                    "Ask",
                    "Bid",
                    "Ultimo",
                    "Lado",
                ],
            )
            if escribir_header:
                writer.writeheader()
            alerta_csv = alerta.copy()
            if "Prima_Volumen" in alerta_csv:
                alerta_csv["Prima_Total"] = alerta_csv.pop("Prima_Volumen")
            writer.writerow(alerta_csv)
    except Exception as e:
        logger.error("Error guardando alerta CSV: %s", e)
