"""
Módulo para obtener datos de cambios en Open Interest desde Barchart.com.

Usa el API interno de Barchart (mismo que usa su frontend) con curl_cffi
para TLS fingerprinting y evitar bloqueos anti-bot.

Fuente: https://www.barchart.com/options/open-interest-change
"""

import time
import pandas as pd
from urllib.parse import unquote
try:
    from curl_cffi import requests as curl_requests
    _HAS_CURL_CFFI = True
except ImportError:
    import requests as curl_requests
    _HAS_CURL_CFFI = False


# ── Helpers ──────────────────────────────────────────────────────────────────

def _crear_sesion():
    """
    Crea una sesión autenticada con cookies de Barchart.
    Visita la página principal para obtener el token XSRF.
    """
    if _HAS_CURL_CFFI:
        session = curl_requests.Session(impersonate="chrome110")
    else:
        session = curl_requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        })

    resp = session.get(
        "https://www.barchart.com/options/open-interest-change",
        timeout=30,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )

    if resp.status_code != 200:
        raise ConnectionError(
            f"No se pudo conectar con Barchart (HTTP {resp.status_code})"
        )

    return session


def _obtener_xsrf(session):
    """Extrae y decodifica el token XSRF de las cookies."""
    token = session.cookies.get("XSRF-TOKEN", "")
    if not token:
        raise ValueError("No se encontró el token XSRF en las cookies de Barchart")
    return unquote(token)


def _extraer_tipo_opcion(symbol, base_symbol):
    """
    Extrae CALL/PUT del símbolo OCC.
    Formato OCC: SYMBOL + YYMMDD + C/P + STRIKE*1000 (8 dígitos)
    Ejemplo: SPY260213C00600000 → CALL
    """
    resto = symbol[len(base_symbol):]
    if len(resto) > 6:
        return "CALL" if resto[6] == "C" else "PUT"
    return "N/A"


def _headers_api(token, referer):
    """Headers estándar para las llamadas al API de Barchart."""
    return {
        "X-XSRF-TOKEN": token,
        "Referer": referer,
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    }


def _parsear_respuesta(data, incluir_tipo=False):
    """
    Convierte la respuesta JSON de Barchart en un DataFrame limpio.

    Args:
        data: dict JSON de la respuesta del API
        incluir_tipo: si True, detecta CALL/PUT del símbolo OCC

    Returns:
        DataFrame con los datos parseados
    """
    if "data" not in data or not data["data"]:
        return pd.DataFrame()

    rows = []
    for item in data["data"]:
        raw = item.get("raw", item)

        base_sym = raw.get("baseSymbol", "")
        symbol = raw.get("symbol", "")

        row = {
            "Contrato": symbol,
            "Ticker": base_sym,
            "Strike": raw.get("strikePrice", 0),
            "Vencimiento": raw.get("expirationDate", ""),
            "DTE": raw.get("daysToExpiration", 0),
            "Último": raw.get("lastPrice", 0),
            "Volumen": int(raw.get("volume", 0) or 0),
            "OI": int(raw.get("openInterest", 0) or 0),
            "OI_Chg": int(raw.get("openInterestChange", 0) or 0),
            "IV": round(float(raw.get("volatility", 0) or 0), 2),
            "Delta": round(float(raw.get("delta", 0) or 0), 4),
        }

        if incluir_tipo:
            row["Tipo"] = _extraer_tipo_opcion(symbol, base_sym)

        rows.append(row)

    return pd.DataFrame(rows)


# ── Funciones principales ────────────────────────────────────────────────────

def obtener_top_oi_changes(tipo="call", limite=9999, min_oi_chg=-9999):
    """
    Obtiene las opciones con mayor cambio en OI de TODO el mercado.
    Equivale a: https://www.barchart.com/options/open-interest-change?view=calls

    Usa paginación automática para obtener todos los resultados disponibles.

    Args:
        tipo: "call" o "put"
        limite: número máximo total de resultados
        min_oi_chg: cambio mínimo en OI para incluir (filtra después)

    Returns:
        (DataFrame, None) en éxito, o (None, str_error) en fallo
    """
    try:
        session = _crear_sesion()
        token = _obtener_xsrf(session)

        PAGE_SIZE = 1000
        all_frames = []
        page = 1
        total_fetched = 0

        while total_fetched < limite:
            # Retry con backoff para rate-limiting (429)
            resp = None
            for retry in range(4):
                resp = session.get(
                    "https://www.barchart.com/proxies/core-api/v1/options/get",
                    params={
                        "fields": (
                            "symbol,baseSymbol,strikePrice,expirationDate,"
                            "daysToExpiration,lastPrice,priceChange,percentChange,"
                            "volume,openInterest,openInterestChange,volatility,"
                            "delta,tradeTime"
                        ),
                        "orderBy": "openInterestChange",
                        "orderDir": "desc",
                        "optionType": tipo,
                        "hasOptions": "true",
                        "raw": "1",
                        "page": str(page),
                        "limit": str(PAGE_SIZE),
                        "meta": "field.shortName,field.type,field.description",
                    },
                    headers=_headers_api(
                        token,
                        "https://www.barchart.com/options/open-interest-change",
                    ),
                    timeout=30,
                )
                if resp.status_code != 429:
                    break
                time.sleep(2 ** retry)  # 1s, 2s, 4s backoff

            if resp.status_code == 403:
                if all_frames:
                    break
                return None, (
                    "Barchart bloqueó la solicitud (403). "
                    "Esto puede ocurrir por rate-limiting. "
                    "Esperá 1-2 minutos e intentá de nuevo."
                )
            if resp.status_code != 200:
                if all_frames:
                    break
                return None, f"Error HTTP {resp.status_code} de Barchart"

            resp_json = resp.json()
            df_page = _parsear_respuesta(resp_json)

            if df_page.empty:
                break

            all_frames.append(df_page)
            total_fetched += len(df_page)

            # Si recibimos menos de PAGE_SIZE, ya no hay más páginas
            total_available = resp_json.get("total", None)
            if len(df_page) < PAGE_SIZE:
                break
            if total_available is not None and total_fetched >= total_available:
                break

            page += 1
            time.sleep(0.3)  # Anti rate-limit

        if not all_frames:
            return None, "Barchart no devolvió datos. Intentá de nuevo."

        df = pd.concat(all_frames, ignore_index=True)

        # Filtrar por OI_Chg mínimo
        if min_oi_chg > 0:
            df = df[df["OI_Chg"] >= min_oi_chg]

        df = df.sort_values("OI_Chg", ascending=False).reset_index(drop=True)
        return df, None

    except ConnectionError as e:
        return None, str(e)
    except Exception as e:
        return None, f"Error al consultar Barchart: {e}"


def obtener_oi_simbolo(simbolo, tipo="call", limite=99999):
    """
    Obtiene cambios en OI para un símbolo específico.
    Equivale a: https://www.barchart.com/stocks/quotes/SPY/options?view=stacked

    Usa paginación automática para obtener TODOS los contratos disponibles
    (el API de Barchart limita a 500 por página).
    Renueva la sesión cada 10 páginas para evitar rate-limiting.

    Args:
        simbolo: ticker del underlying (ej: "SPY", "AAPL")
        tipo: "call", "put" o "ambos"
        limite: número máximo total de resultados

    Returns:
        (DataFrame, None) en éxito, o (None, str_error) en fallo
    """
    try:
        PAGE_SIZE = 1000
        PAGES_PER_SESSION = 10  # Renovar sesión cada N páginas
        all_frames = []
        page = 1
        total_fetched = 0
        session = None
        token = None
        pages_this_session = 0

        while total_fetched < limite:
            # Crear/renovar sesión cada PAGES_PER_SESSION páginas
            if session is None or pages_this_session >= PAGES_PER_SESSION:
                if session is not None:
                    time.sleep(1.5)  # Pausa antes de nueva sesión
                session = _crear_sesion()
                token = _obtener_xsrf(session)
                pages_this_session = 0

            params = {
                "fields": (
                    "symbol,baseSymbol,strikePrice,expirationDate,"
                    "daysToExpiration,lastPrice,volume,openInterest,"
                    "openInterestChange,volatility,delta,gamma,theta,"
                    "vega,tradeTime"
                ),
                "orderBy": "openInterestChange",
                "orderDir": "desc",
                "baseSymbol": simbolo.upper(),
                "hasOptions": "true",
                "raw": "1",
                "page": str(page),
                "limit": str(PAGE_SIZE),
                "meta": "field.shortName,field.type,field.description",
            }

            if tipo != "ambos":
                params["optionType"] = tipo

            sim = simbolo.upper()
            # Retry con backoff para rate-limiting (429)
            resp = None
            for retry in range(4):
                resp = session.get(
                    "https://www.barchart.com/proxies/core-api/v1/options/get",
                    params=params,
                    headers=_headers_api(
                        token,
                        f"https://www.barchart.com/stocks/quotes/{sim}/options",
                    ),
                    timeout=30,
                )
                if resp.status_code == 429:
                    time.sleep(2 ** retry)  # 1s, 2s, 4s backoff
                elif resp.status_code == 403 and pages_this_session > 0:
                    # Sesión expirada, renovar y reintentar
                    time.sleep(1.5)
                    session = _crear_sesion()
                    token = _obtener_xsrf(session)
                    pages_this_session = 0
                else:
                    break

            if resp.status_code == 403:
                if all_frames:
                    break
                return None, (
                    "Barchart bloqueó la solicitud (403). "
                    "Esperá 1-2 minutos e intentá de nuevo."
                )
            if resp.status_code != 200:
                if all_frames:
                    break
                return None, f"Error HTTP {resp.status_code}"

            resp_json = resp.json()
            incluir_tipo = (tipo == "ambos")
            df_page = _parsear_respuesta(resp_json, incluir_tipo=incluir_tipo)

            if df_page.empty:
                break

            all_frames.append(df_page)
            total_fetched += len(df_page)
            pages_this_session += 1

            # Si recibimos menos de PAGE_SIZE, ya no hay más páginas
            total_available = resp_json.get("total", None)
            if len(df_page) < PAGE_SIZE:
                break
            if total_available is not None and total_fetched >= total_available:
                break

            page += 1
            time.sleep(0.3)  # Anti rate-limit

        if not all_frames:
            return None, f"Sin datos de Barchart para {simbolo.upper()}"

        df = pd.concat(all_frames, ignore_index=True)
        df = df.sort_values("OI_Chg", ascending=False).reset_index(drop=True)
        return df, None

    except ConnectionError as e:
        return None, str(e)
    except Exception as e:
        return None, f"Error al consultar Barchart para {simbolo}: {e}"
