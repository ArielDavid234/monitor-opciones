# -*- coding: utf-8 -*-
"""Credit Spread — 10-rule alert validation and alert generation."""
from __future__ import annotations

import logging
import pandas as pd
from datetime import datetime

from config.constants import (
    CS_MIN_DIST_PCT, CS_MIN_SOLD_OI, CS_MIN_SOLD_VOL,
    ALERT_DEFAULT_ACCOUNT_SIZE, ALERT_MAX_RISK_PCT,
    CS_MAX_BID_ASK_PCT,
)

logger = logging.getLogger(__name__)

def _check_10_rules(row: dict, account_size: float, strict_rules: dict | None = None) -> tuple[bool, list[dict]]:
    """Verifica las reglas de seguridad sobre un spread ya construido.

    Si strict_rules es un dict, solo se aplican las reglas activadas (True).
    Las reglas desactivadas se marcan OK automáticamente (skip).
    La Regla 8 (riesgo de cuenta) siempre se aplica.

    Returns (all_pass, detalle_reglas)
    """
    _sr = strict_rules or {}
    # Si se pasó un dict pero ninguna regla está activa → saltar todas (modo libre)
    skip_all = len(_sr) > 0 and not any(_sr.values())

    def _active(key: str) -> bool:
        if not _sr:        # sin dict → comportamiento original (todo activo)
            return True
        return bool(_sr.get(key, True))

    rules: list[dict] = []
    all_pass = True

    ticker = row.get("Ticker", "")
    spot = row.get("Spot", 0)
    tipo = row.get("Tipo", "")
    dte = row.get("DTE", 0)
    delta = abs(row.get("Delta Vendido", 1.0))
    trend = row.get("Tendencia", "Neutral")
    width = abs(
        (row.get("Strike Vendido", 0) or 0)
        - (row.get("Strike Comprado", 0) or 0)
    )
    credit = row.get("Crédito", 0) or 0
    risk = row.get("Riesgo Máx", 0) or 0
    dist_pct = row.get("Dist Strike %", 0) or 0
    oi = row.get("OI", 0) or 0
    vol = row.get("Volumen", 0) or 0
    bid_ask = row.get("Bid-Ask", 0) or 0
    iv_rank = row.get("IV Rank", 0) or 0
    mid = credit + bid_ask / 2 if credit > 0 else 0.01

    # Regla 1 — Whitelist + Precio > $20
    if skip_all or not _active("r1_whitelist"):
        rules.append({"regla": "1. Precio>$20", "ok": True, "skip": True})
    else:
        r1 = spot > CS_MIN_PRICE
        rules.append({"regla": "1. Precio>$20", "ok": r1})
        if not r1:
            all_pass = False

    # Regla 2 — IV Rank >= 30
    if skip_all or not _active("r2_iv_rank"):
        rules.append({"regla": f"2. IV Rank ≥ {CS_MIN_IV_RANK}%", "ok": True, "skip": True})
    else:
        r2 = iv_rank >= CS_MIN_IV_RANK
        rules.append({"regla": f"2. IV Rank ≥ {CS_MIN_IV_RANK}%", "ok": r2})
        if not r2:
            all_pass = False

    # Regla 3 — 25 <= DTE <= 45
    if skip_all or not _active("r3_dte"):
        rules.append({"regla": f"3. DTE {CS_DTE_MIN}–{CS_DTE_MAX}", "ok": True, "skip": True})
    else:
        r3 = CS_DTE_MIN <= dte <= CS_DTE_MAX
        rules.append({"regla": f"3. DTE {CS_DTE_MIN}–{CS_DTE_MAX}", "ok": r3})
        if not r3:
            all_pass = False

    # Regla 4 — 0.10 <= |Delta| <= 0.20
    if skip_all or not _active("r4_delta"):
        rules.append({"regla": f"4. Delta {CS_DELTA_MIN}–{CS_DELTA_MAX}", "ok": True, "skip": True})
    else:
        r4 = CS_DELTA_MIN <= delta <= CS_DELTA_MAX
        rules.append({"regla": f"4. Delta {CS_DELTA_MIN}–{CS_DELTA_MAX}", "ok": r4})
        if not r4:
            all_pass = False

    # Regla 5 — Tendencia alineada
    if skip_all or not _active("r5_trend"):
        rules.append({"regla": "5. Tendencia alineada", "ok": True, "skip": True})
    else:
        if trend == "Alcista":
            r5 = tipo == "Bull Put"
        elif trend == "Bajista":
            r5 = tipo == "Bear Call"
        else:
            r5 = False  # Neutral → no alertar
        rules.append({"regla": "5. Tendencia alineada", "ok": r5})
        if not r5:
            all_pass = False

    # Regla 6 — Width = 2, 3 o 5
    if skip_all or not _active("r6_width"):
        rules.append({"regla": f"6. Ancho {CS_ALLOWED_WIDTHS}", "ok": True, "skip": True})
    else:
        width_int = int(round(width))
        r6 = width_int in CS_ALLOWED_WIDTHS
        rules.append({"regla": f"6. Ancho {CS_ALLOWED_WIDTHS}", "ok": r6})
        if not r6:
            all_pass = False

    # Regla 7 — Crédito >= 15% del ancho
    if skip_all or not _active("r7_credit_pct"):
        rules.append({"regla": f"7. Crédito ≥ {CS_MIN_CREDIT_PCT*100:.0f}% ancho", "ok": True, "skip": True})
    else:
        r7 = width > 0 and credit >= CS_MIN_CREDIT_PCT * width
        rules.append({"regla": f"7. Crédito ≥ {CS_MIN_CREDIT_PCT*100:.0f}% ancho", "ok": r7})
        if not r7:
            all_pass = False

    # Regla 8 — Riesgo <= 5% del account size (siempre activa)
    max_risk_allowed = account_size * ALERT_MAX_RISK_PCT
    risk_per_contract = risk * 100
    r8 = risk_per_contract <= max_risk_allowed
    rules.append({
        "regla": f"8. Riesgo ≤ 5% cuenta (${max_risk_allowed:,.0f})",
        "ok": r8,
    })
    if not r8:
        all_pass = False

    # Regla 9 — Distancia >= 3%
    if skip_all or not _active("r8_distance"):
        rules.append({"regla": f"9. Distancia ≥ {CS_MIN_DIST_PCT}%", "ok": True, "skip": True})
    else:
        r9 = dist_pct >= CS_MIN_DIST_PCT
        rules.append({"regla": f"9. Distancia ≥ {CS_MIN_DIST_PCT}%", "ok": r9})
        if not r9:
            all_pass = False

    # Regla 10 — Liquidez (OI>500, Vol>100, Bid-Ask<=10% mid)
    if skip_all or not _active("r9_liquidity"):
        rules.append({"regla": "10. Liquidez (OI>500, Vol>100, B-A≤10%)", "ok": True, "skip": True})
    else:
        ba_ok = True
        if mid > 0:
            ba_ok = bid_ask / mid <= CS_MAX_BID_ASK_PCT
        r10 = oi > CS_MIN_SOLD_OI and vol > CS_MIN_SOLD_VOL and ba_ok
        rules.append({"regla": "10. Liquidez (OI>500, Vol>100, B-A≤10%)", "ok": r10})
        if not r10:
            all_pass = False

    return all_pass, rules


def generate_alerts(
    df: pd.DataFrame,
    account_size: float = ALERT_DEFAULT_ACCOUNT_SIZE,
    strict_rules: dict | None = None,
) -> pd.DataFrame:
    """Filtra el DataFrame de spreads aplicando las 10 reglas obligatorias.

    Solo retorna filas donde TODAS las reglas son verdaderas.
    Agrega columna 'Reglas' con el detalle de cada regla verificada.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame resultado de scan_credit_spreads (strict mode).
    account_size : float
        Tamaño de la cuenta del usuario en USD.

    Returns
    -------
    pd.DataFrame
        Solo filas que cumplen las 10 reglas. Vacío si ninguna cumple.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    alerts: list[dict] = []

    for _, row_s in df.iterrows():
        row = row_s.to_dict()
        all_pass, rules_detail = _check_10_rules(row, account_size, strict_rules=strict_rules)
        if all_pass:
            row["_rules_detail"] = rules_detail
            alerts.append(row)

    if not alerts:
        return pd.DataFrame()

    alerts_df = pd.DataFrame(alerts)
    # Ordenar por Score Unificado cuando existe, si no por Score Oportunidad.
    if "Score Unificado" in alerts_df.columns:
        alerts_df = alerts_df.sort_values("Score Unificado", ascending=False).reset_index(drop=True)
    elif "Score Oportunidad" in alerts_df.columns:
        alerts_df = alerts_df.sort_values("Score Oportunidad", ascending=False).reset_index(drop=True)

    return alerts_df
