"""
Sistema de noticias financieras vía RSS feeds.
"""
import logging
import re as re_module
import feedparser
from html import unescape as html_unescape
from datetime import datetime
from calendar import timegm

from config.constants import RSS_MAX_ENTRIES, RSS_TITLE_DEDUP_LEN, RSS_MAX_DESC_LEN

logger = logging.getLogger(__name__)

# ============================================================================
#   FUENTES RSS Y CATEGORIZACIÓN
# ============================================================================
RSS_FEEDS = {
    "Yahoo Finance": {
        "url": "https://finance.yahoo.com/news/rssindex",
        "categoria_default": "Mercados",
    },
    "Yahoo Finance - Top": {
        "url": "https://finance.yahoo.com/rss/topfinstories",
        "categoria_default": "Top Stories",
    },
    "MarketWatch": {
        "url": "https://feeds.marketwatch.com/marketwatch/topstories/",
        "categoria_default": "Mercados",
    },
    "MarketWatch Stocks": {
        "url": "https://feeds.marketwatch.com/marketwatch/marketpulse/",
        "categoria_default": "Trading",
    },
    "CNBC Top": {
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
        "categoria_default": "Top Stories",
    },
    "CNBC Finance": {
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
        "categoria_default": "Mercados",
    },
    "CNBC Earnings": {
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839135",
        "categoria_default": "Earnings",
    },
    "CNBC Economy": {
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
        "categoria_default": "Economía",
    },
    "Investing.com": {
        "url": "https://www.investing.com/rss/news.rss",
        "categoria_default": "Mercados",
    },
    "Reuters Business": {
        "url": "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best",
        "categoria_default": "Economía",
    },
}

CATEGORIAS_KEYWORDS = {
    "Earnings": [
        "earnings", "revenue", "profit", "quarterly", "q1", "q2", "q3", "q4",
        "beat", "miss", "eps", "guidance", "results", "report card", "fiscal",
        "ganancias", "ingresos", "trimestral", "resultados",
    ],
    "Fed / Tasas": [
        "fed", "federal reserve", "interest rate", "rate hike", "rate cut",
        "powell", "fomc", "treasury", "bond yield", "inflation", "cpi", "ppi",
        "monetary policy", "basis points", "hawkish", "dovish", "tasa", "inflación",
    ],
    "Economía": [
        "gdp", "unemployment", "jobs", "payroll", "economic", "recession",
        "growth", "consumer", "spending", "housing", "retail sales", "trade",
        "deficit", "surplus", "manufacturing", "pmi", "economia", "empleo",
    ],
    "Trading": [
        "options", "calls", "puts", "short squeeze", "rally", "crash", "correction",
        "bull", "bear", "volatility", "vix", "technical", "breakout", "support",
        "resistance", "volume", "momentum", "trading", "opciones",
    ],
    "Crypto": [
        "bitcoin", "ethereum", "crypto", "blockchain", "defi", "nft", "token",
        "binance", "coinbase", "btc", "eth", "solana", "xrp",
    ],
    "Commodities": [
        "oil", "gold", "silver", "commodit", "crude", "wti", "brent", "natural gas",
        "copper", "petróleo", "oro", "plata", "materias primas",
    ],
    "Geopolítica": [
        "war", "sanction", "tariff", "china", "russia", "ukraine", "geopolit",
        "trade war", "ban", "embargo", "conflict", "guerra", "aranceles",
    ],
}


def _limpiar_html(texto):
    """Limpia tags HTML y entidades de un texto."""
    if not texto:
        return ""
    limpio = re_module.sub(r"<[^>]+>", "", texto)
    limpio = html_unescape(limpio)
    limpio = re_module.sub(r"\s+", " ", limpio).strip()
    return limpio


def _categorizar_noticia(titulo, descripcion=""):
    """Asigna una categoría a la noticia según palabras clave."""
    texto = (titulo + " " + descripcion).lower()
    scores = {}
    for cat, keywords in CATEGORIAS_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in texto)
        if score > 0:
            scores[cat] = score
    if scores:
        return max(scores, key=scores.get)
    return "Mercados"


def _tiempo_relativo(published_parsed):
    """Convierte una fecha de feedparser a tiempo relativo."""
    try:
        if published_parsed:
            pub_timestamp = timegm(published_parsed)
            pub_dt = datetime.utcfromtimestamp(pub_timestamp)
            ahora = datetime.utcnow()
            delta = ahora - pub_dt
            if delta.total_seconds() < 0:
                return "Ahora"
            if delta.days > 0:
                return f"Hace {delta.days}d"
            hours = int(delta.total_seconds() // 3600)
            if hours > 0:
                return f"Hace {hours}h"
            mins = int(delta.total_seconds() // 60)
            if mins > 0:
                return f"Hace {mins}min"
            return "Ahora"
    except Exception as e:
        logger.debug("Error calculando tiempo relativo: %s", e)
    return ""


def obtener_noticias_financieras():
    """
    Obtiene noticias financieras de múltiples fuentes RSS gratuitas.
    Retorna una lista de dicts con: titulo, descripcion, url, fuente,
    categoria, tiempo, published_parsed.
    """
    todas_noticias = []
    titulos_vistos = set()

    for fuente_nombre, config in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(
                config["url"],
                request_headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            )
            for entry in feed.entries[:RSS_MAX_ENTRIES]:
                titulo = _limpiar_html(entry.get("title", ""))
                if not titulo:
                    continue

                titulo_key = titulo[:RSS_TITLE_DEDUP_LEN].lower()
                if titulo_key in titulos_vistos:
                    continue
                titulos_vistos.add(titulo_key)

                descripcion = _limpiar_html(
                    entry.get("summary", entry.get("description", ""))
                )
                if len(descripcion) > RSS_MAX_DESC_LEN:
                    descripcion = descripcion[:RSS_MAX_DESC_LEN - 3] + "..."

                url = entry.get("link", "")
                published_parsed = entry.get("published_parsed", None)
                tiempo_str = _tiempo_relativo(published_parsed)

                categoria = _categorizar_noticia(titulo, descripcion)
                if categoria == "Mercados":
                    categoria = config.get("categoria_default", "Mercados")

                todas_noticias.append({
                    "titulo": titulo,
                    "descripcion": descripcion,
                    "url": url,
                    "fuente": fuente_nombre.split(" - ")[0].split(" ")[0],
                    "categoria": categoria,
                    "tiempo": tiempo_str,
                    "published_parsed": published_parsed,
                })
        except Exception as e:
            logger.warning("Error parseando feed %s: %s", fuente_nombre, e)
            continue

    def sort_key(n):
        pp = n.get("published_parsed")
        if pp:
            try:
                return timegm(pp)
            except Exception:
                return 0
        return 0

    todas_noticias.sort(key=sort_key, reverse=True)
    return todas_noticias


def calcular_relevancia(noticia):
    """
    Calcula un score de relevancia 0-100 para una noticia.
    Factores: categoría de alto impacto, recencia, fuente premium, keywords de impacto.
    """
    score = 0

    # 1) Categorías de alto impacto financiero
    cat_scores = {
        "Fed / Tasas": 30, "Earnings": 25, "Economía": 20,
        "Trading": 18, "Top Stories": 22, "Geopolítica": 15,
        "Commodities": 12, "Crypto": 10, "Mercados": 8,
    }
    score += cat_scores.get(noticia.get("categoria", ""), 5)

    # 2) Recencia — más reciente = más relevante
    pp = noticia.get("published_parsed")
    if pp:
        try:
            pub_ts = timegm(pp)
            ahora_ts = timegm(datetime.utcnow().timetuple())
            horas = (ahora_ts - pub_ts) / 3600
            if horas < 1:
                score += 30
            elif horas < 3:
                score += 22
            elif horas < 6:
                score += 15
            elif horas < 12:
                score += 8
            elif horas < 24:
                score += 4
        except Exception:
            pass

    # 3) Fuentes premium
    fuentes_premium = {"CNBC": 10, "Reuters": 12, "MarketWatch": 8, "Yahoo": 6, "Investing": 5}
    fuente = noticia.get("fuente", "")
    for f_name, f_score in fuentes_premium.items():
        if f_name.lower() in fuente.lower():
            score += f_score
            break

    # 4) Keywords de alto impacto en título
    titulo_lower = noticia.get("titulo", "").lower()
    high_impact = [
        "breaking", "urgent", "just in", "alert", "crash", "surge", "soar",
        "plunge", "record", "historic", "emergency", "halt", "billion",
        "trillion", "fed", "rate cut", "rate hike", "war", "sanctions",
    ]
    for kw in high_impact:
        if kw in titulo_lower:
            score += 8
            break  # solo 1 bonus por keywords

    return min(score, 100)


def filtrar_noticias(noticias, filtro="Todas"):
    """Filtra noticias por categoría o criterio especial."""
    if filtro == "Todas":
        return noticias
    elif filtro == "🔥 Más relevantes":
        scored = [(n, calcular_relevancia(n)) for n in noticias]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [n for n, s in scored[:30]]
    elif filtro == "🌍 Más vistas a nivel mundial":
        # Top Stories + fuentes internacionales premium + alto impacto
        global_cats = {"Top Stories", "Economía", "Geopolítica", "Fed / Tasas"}
        global_news = [n for n in noticias if n["categoria"] in global_cats]
        scored = [(n, calcular_relevancia(n)) for n in global_news]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [n for n, s in scored[:25]]
    elif filtro == "Más relevantes para trading":
        cats_trading = {"Trading", "Earnings", "Fed / Tasas", "Economía"}
        return [n for n in noticias if n["categoria"] in cats_trading]
    elif filtro == "Top Stories":
        return [n for n in noticias if n["categoria"] == "Top Stories"]
    else:
        return [n for n in noticias if n["categoria"] == filtro]
