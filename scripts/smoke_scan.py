from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from core.scanner import ejecutar_escaneo


def _provider_payload(_ticker: str, exp_date: str):
    row = {
        "strike": 100.0,
        "lastPrice": 1.0,
        "bid": 0.9,
        "ask": 1.1,
        "volume": 10,
        "openInterest": 20,
        "impliedVolatility": 0.2,
    }
    df = pd.DataFrame([row])
    return exp_date, {"calls": df, "puts": df.copy()}, None


def main() -> int:
    provider = {
        "name": "yfinance",
        "fetch_options_dates": lambda _ticker: ("2026-12-18",),
        "fetch_single_chain": _provider_payload,
        "obtener_precio_actual": lambda _ticker: (100.0, None),
        "get_price_history": lambda *_a, **_k: pd.DataFrame(),
        "get_contract_history": lambda *_a, **_k: pd.DataFrame(),
        "get_ticker_details": lambda *_a, **_k: None,
    }

    with patch("infrastructure.data.yahoo_finance_client._provider_impls", return_value=provider):
        with patch("infrastructure.data.yahoo_finance_client.get_active_provider", return_value="yfinance"):
            alertas, datos, error, _perfil, _fechas = ejecutar_escaneo(
                ticker_sym="SPY",
                u_vol=1,
                u_oi=1,
                u_prima=1,
                u_filtro=0,
                carpeta_csv="alertas",
                guardar=False,
                paralelo=True,
            )

    if error:
        print(f"SMOKE ERROR: {error}")
        return 2
    if not isinstance(alertas, list) or not isinstance(datos, list):
        print("SMOKE ERROR: invalid response contract")
        return 3
    print(f"SMOKE OK: alertas={len(alertas)} datos={len(datos)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
