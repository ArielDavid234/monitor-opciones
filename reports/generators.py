# -*- coding: utf-8 -*-
"""Backward-compatible re-exports for report generators."""

from reports.live_scanning_report import _generar_reporte_live_scanning
from reports.open_interest_report import _generar_reporte_open_interest
from reports.important_companies_report import _generar_reporte_important_companies
from reports.data_analysis_report import _generar_reporte_data_analysis
from reports.range_report import _generar_reporte_range

__all__ = [
    "_generar_reporte_live_scanning",
    "_generar_reporte_open_interest",
    "_generar_reporte_important_companies",
    "_generar_reporte_data_analysis",
    "_generar_reporte_range",
]
