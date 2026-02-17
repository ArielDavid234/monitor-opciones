"""Test: verify all OI pages are fetched."""
from core.barchart_oi import obtener_oi_simbolo
import time

print("Fetching SPY CALLs...")
t0 = time.time()
df_c, err_c = obtener_oi_simbolo("SPY", tipo="call")
t1 = time.time()
print(f"CALLs: {len(df_c) if df_c is not None else 0} contracts in {t1-t0:.1f}s")
if err_c:
    print(f"  Error: {err_c}")

print("\nFetching SPY PUTs...")
t2 = time.time()
df_p, err_p = obtener_oi_simbolo("SPY", tipo="put")
t3 = time.time()
print(f"PUTs: {len(df_p) if df_p is not None else 0} contracts in {t3-t2:.1f}s")
if err_p:
    print(f"  Error: {err_p}")

total = (len(df_c) if df_c is not None else 0) + (len(df_p) if df_p is not None else 0)
print(f"\nTotal: {total} contracts")
