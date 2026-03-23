from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.scanner import ejecutar_escaneo


LIQUID_DEFAULT = ["SPY", "QQQ", "AAPL"]
NON_LIQUID_DEFAULT = ["IWM", "TLT"]


def _run_scan(ticker: str) -> dict:
    t0 = time.perf_counter()
    alertas, datos, error, _perfil, fechas = ejecutar_escaneo(
        ticker_sym=ticker,
        u_vol=1,
        u_oi=1,
        u_prima=1,
        u_filtro=0,
        carpeta_csv="alertas",
        guardar=False,
        paralelo=True,
    )
    ms = (time.perf_counter() - t0) * 1000.0
    return {
        "ticker": ticker,
        "latency_ms": round(ms, 2),
        "error": error,
        "alertas": len(alertas),
        "datos": len(datos),
        "fechas": len(fechas),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Staging E2E scan validation")
    parser.add_argument("--liquid", default=",".join(LIQUID_DEFAULT))
    parser.add_argument("--non-liquid", default=",".join(NON_LIQUID_DEFAULT))
    parser.add_argument("--allow-degraded", action="store_true", help="Do not fail when provider unavailable")
    args = parser.parse_args()

    tickers = [x.strip().upper() for x in (args.liquid + "," + args.non_liquid).split(",") if x.strip()]
    rows = [_run_scan(t) for t in tickers]

    latencies = [r["latency_ms"] for r in rows]
    p50 = statistics.median(latencies) if latencies else 0.0
    p90 = sorted(latencies)[max(0, int(len(latencies) * 0.9) - 1)] if latencies else 0.0

    print("E2E staging results:")
    for row in rows:
        print(row)
    print({"p50_ms": round(p50, 2), "p90_ms": round(p90, 2), "tickers": len(rows)})

    has_errors = any(r["error"] for r in rows)
    if has_errors and not args.allow_degraded:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
