"""Debug: test session renewal after 429."""
import time
from core.barchart_oi import _crear_sesion, _obtener_xsrf, _headers_api, _parsear_respuesta

PAGE_SIZE = 1000
total_fetched = 0
session = _crear_sesion()
token = _obtener_xsrf(session)

for page_num in range(1, 20):
    resp = session.get(
        "https://www.barchart.com/proxies/core-api/v1/options/get",
        params={
            "fields": "symbol,baseSymbol,strikePrice,expirationDate,daysToExpiration,lastPrice,volume,openInterest,openInterestChange,volatility,delta,tradeTime",
            "orderBy": "openInterestChange",
            "orderDir": "desc",
            "baseSymbol": "SPY",
            "hasOptions": "true",
            "raw": "1",
            "page": str(page_num),
            "limit": str(PAGE_SIZE),
            "optionType": "call",
            "meta": "field.shortName,field.type,field.description",
        },
        headers=_headers_api(token, "https://www.barchart.com/stocks/quotes/SPY/options"),
        timeout=30,
    )
    
    if resp.status_code == 429:
        print(f"Page {page_num}: HTTP 429 - Rate limited. Waiting 10s + new session...")
        time.sleep(10)
        session = _crear_sesion()
        token = _obtener_xsrf(session)
        # Retry same page
        resp = session.get(
            "https://www.barchart.com/proxies/core-api/v1/options/get",
            params={
                "fields": "symbol,baseSymbol,strikePrice,expirationDate,daysToExpiration,lastPrice,volume,openInterest,openInterestChange,volatility,delta,tradeTime",
                "orderBy": "openInterestChange",
                "orderDir": "desc",
                "baseSymbol": "SPY",
                "hasOptions": "true",
                "raw": "1",
                "page": str(page_num),
                "limit": str(PAGE_SIZE),
                "optionType": "call",
                "meta": "field.shortName,field.type,field.description",
            },
            headers=_headers_api(token, "https://www.barchart.com/stocks/quotes/SPY/options"),
            timeout=30,
        )
        print(f"  Retry page {page_num}: HTTP {resp.status_code}", end="")
    else:
        print(f"Page {page_num}: HTTP {resp.status_code}", end="")
    
    if resp.status_code != 200:
        print(f" - STOPPED")
        break
    
    j = resp.json()
    data_len = len(j.get("data", []))
    total_fetched += data_len
    total_available = j.get("total", "?")
    print(f" | data={data_len} | fetched={total_fetched}/{total_available}")
    
    if data_len < PAGE_SIZE:
        print("  -> Last page")
        break
    
    time.sleep(0.4)

print(f"\nTotal fetched: {total_fetched}")
