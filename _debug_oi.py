"""Debug: check Barchart API pagination response."""
from core.barchart_oi import _crear_sesion, _obtener_xsrf, _headers_api

session = _crear_sesion()
token = _obtener_xsrf(session)

for page_num in range(1, 5):
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
            "limit": "500",
            "optionType": "call",
            "meta": "field.shortName,field.type,field.description",
        },
        headers=_headers_api(token, "https://www.barchart.com/stocks/quotes/SPY/options"),
        timeout=20,
    )
    
    if resp.status_code != 200:
        print(f"Page {page_num}: HTTP {resp.status_code}")
        break
    
    j = resp.json()
    data_len = len(j.get("data", []))
    print(f"Page {page_num}: count={j.get('count')}, total={j.get('total')}, data_len={data_len}, keys={list(j.keys())}")
    
    if data_len == 0:
        break
