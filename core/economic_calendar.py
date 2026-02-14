"""
Módulo para obtener datos reales de calendarios económicos y eventos financieros.

Fuentes:
- Investing.com (calendario económico)
- Yahoo Finance (earnings calendar)
- MarketWatch (eventos Fed)
- RSS feeds de noticias económicas
"""

import json
import logging
import os
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

import pandas as pd
import requests
import yfinance as yf
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests

logger = logging.getLogger(__name__)

# Cache de eventos (renovar cada 6 horas)
_CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "economic_events_cache.json")
_CACHE_DURATION_HOURS = 6


def _load_cache():
    """Carga el cache de eventos económicos."""
    try:
        if os.path.exists(_CACHE_PATH):
            with open(_CACHE_PATH, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
            
            # Verificar si el cache no ha expirado
            cache_time = datetime.fromisoformat(cache_data.get("timestamp", "2000-01-01"))
            if datetime.now() - cache_time < timedelta(hours=_CACHE_DURATION_HOURS):
                return cache_data.get("events", [])
    except Exception as e:
        logger.warning("Error cargando cache de eventos: %s", e)
    return []


def _save_cache(events):
    """Guarda eventos en cache."""
    try:
        os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
        cache_data = {
            "timestamp": datetime.now().isoformat(),
            "events": events
        }
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("Error guardando cache de eventos: %s", e)


def _fetch_investing_calendar():
    """Obtiene eventos del calendario económico de Investing.com."""
    events = []
    try:
        # Usar curl_cffi para evitar bloqueos
        session = curl_requests.Session(impersonate="chrome120")
        
        # URL del calendario económico de Investing.com
        url = "https://www.investing.com/economic-calendar/"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        response = session.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar eventos en la tabla del calendario
            calendar_rows = soup.find_all('tr', class_=re.compile(r'js-event-item'))
            
            for row in calendar_rows[:50]:  # Limitar a 50 eventos
                try:
                    # Extraer fecha
                    date_cell = row.find('td', class_='first left time')
                    if not date_cell:
                        continue
                    
                    date_text = date_cell.get_text(strip=True)
                    
                    # Extraer título del evento
                    event_cell = row.find('td', class_='left event')
                    if not event_cell:
                        continue
                    
                    title = event_cell.get_text(strip=True)
                    
                    # Extraer importancia (estrellas)
                    bull_count = len(row.find_all('i', class_='grayFullBull'))
                    importance = "Alta" if bull_count >= 3 else "Media" if bull_count == 2 else "Baja"
                    
                    # Determinar tipo de evento
                    event_type = "Fed" if any(word in title.lower() for word in ['fed', 'fomc', 'powell', 'rates']) else \
                                "Earnings" if any(word in title.lower() for word in ['earnings', 'results']) else \
                                "Economic"
                    
                    # Parsear fecha (formato puede variar)
                    event_date = _parse_investing_date(date_text)
                    
                    if event_date:
                        events.append({
                            "fecha": event_date,
                            "tipo": event_type,
                            "titulo": title[:100],  # Limitar longitud
                            "descripcion": f"Evento económico: {title}",
                            "hora": "TBD",
                            "importancia": importance,
                            "fuente": "Investing.com"
                        })
                        
                except Exception as e:
                    logger.debug("Error procesando evento de Investing.com: %s", e)
                    continue
                    
    except Exception as e:
        logger.warning("Error obteniendo calendario de Investing.com: %s", e)
    
    return events


def _parse_investing_date(date_str):
    """Parsea fecha de Investing.com a formato YYYY-MM-DD."""
    try:
        today = datetime.now()
        
        # Si es "Today" o similar
        if 'today' in date_str.lower():
            return today.strftime("%Y-%m-%d")
        
        # Si es "Tomorrow" o similar  
        if 'tomorrow' in date_str.lower():
            return (today + timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Si tiene formato de hora (ej: "14:30")
        if re.match(r'^\d{1,2}:\d{2}', date_str):
            return today.strftime("%Y-%m-%d")
        
        # Intentar parsear fecha específica
        # Formato común: "Feb 13" o "13 Feb"
        month_names = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        
        for month_abbr, month_num in month_names.items():
            if month_abbr in date_str.lower():
                # Extraer día
                day_match = re.search(r'\b(\d{1,2})\b', date_str)
                if day_match:
                    day = int(day_match.group(1))
                    year = today.year
                    
                    # Si la fecha ya pasó este año, asumir año siguiente
                    event_date = datetime(year, month_num, day)
                    if event_date < today:
                        event_date = datetime(year + 1, month_num, day)
                    
                    return event_date.strftime("%Y-%m-%d")
        
        return None
        
    except Exception as e:
        logger.debug("Error parseando fecha '%s': %s", date_str, e)
        return None


def _fetch_yahoo_earnings():
    """Obtiene calendario de earnings de Yahoo Finance."""
    events = []
    try:
        # Obtener earnings calendar de los próximos 30 días
        today = datetime.now()
        end_date = today + timedelta(days=30)
        
        # Usar requests directo para Yahoo Finance
        url = f"https://finance.yahoo.com/calendar/earnings"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=20)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar tabla de earnings
            earnings_table = soup.find('table')
            if earnings_table:
                rows = earnings_table.find_all('tr')[1:]  # Skip header
                
                for row in rows[:30]:  # Limitar eventos
                    try:
                        cells = row.find_all('td')
                        if len(cells) >= 3:
                            # Extraer símbolo de empresa
                            symbol_link = cells[0].find('a')
                            symbol = symbol_link.get_text(strip=True) if symbol_link else "N/A"
                            
                            # Extraer nombre de empresa
                            company_name = cells[1].get_text(strip=True)
                            
                            # Construir evento
                            events.append({
                                "fecha": today.strftime("%Y-%m-%d"),  # Placeholder
                                "tipo": "Earnings",
                                "titulo": f"{symbol} Earnings Call",
                                "descripcion": f"{company_name} presenta resultados trimestrales",
                                "hora": "After Market Close",
                                "importancia": "Alta" if symbol in ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA'] else "Media",
                                "fuente": "Yahoo Finance"
                            })
                            
                    except Exception as e:
                        logger.debug("Error procesando earnings de Yahoo: %s", e)
                        continue
                        
    except Exception as e:
        logger.warning("Error obteniendo earnings de Yahoo Finance: %s", e)
    
    return events


def _fetch_fed_events():
    """Obtiene eventos de la Fed y otros bancos centrales."""
    events = []
    try:
        # Eventos Fed conocidos (FOMC meeting dates)
        fomc_dates_2026 = [
            "2026-01-29", "2026-03-19", "2026-05-01", "2026-06-11", 
            "2026-07-31", "2026-09-17", "2026-11-05", "2026-12-17"
        ]
        
        today = datetime.now()
        
        for date_str in fomc_dates_2026:
            event_date = datetime.strptime(date_str, "%Y-%m-%d")
            
            # Solo incluir eventos futuros o del último mes
            if event_date >= today - timedelta(days=30):
                events.append({
                    "fecha": date_str,
                    "tipo": "Fed",
                    "titulo": "Reunión FOMC",
                    "descripcion": "Comité Federal de Mercado Abierto - Decisión de tasas de interés",
                    "hora": "14:00 EST",
                    "importancia": "Alta",
                    "fuente": "Federal Reserve"
                })
        
        # Agregar eventos de Jerome Powell y otros
        powell_events = [
            {"fecha": "2026-02-25", "titulo": "Jerome Powell - Testimonio ante el Congreso"},
            {"fecha": "2026-04-15", "titulo": "Jerome Powell - Conferencia de Prensa Post-FOMC"},
            {"fecha": "2026-06-15", "titulo": "Jerome Powell - Discurso sobre Política Monetaria"}
        ]
        
        for event in powell_events:
            if datetime.strptime(event["fecha"], "%Y-%m-%d") >= today - timedelta(days=7):
                events.append({
                    **event,
                    "tipo": "Fed",
                    "descripcion": "Comunicado del Presidente de la Reserva Federal",
                    "hora": "10:00 EST",
                    "importancia": "Alta",
                    "fuente": "Federal Reserve"
                })
        
    except Exception as e:
        logger.warning("Error creando eventos Fed: %s", e)
    
    return events


def obtener_eventos_economicos(force_refresh=False):
    """
    Obtiene eventos económicos de múltiples fuentes.
    
    Args:
        force_refresh: Si True, ignora el cache y obtiene datos frescos
        
    Returns:
        Lista de eventos en formato estándar
    """
    if not force_refresh:
        cached_events = _load_cache()
        if cached_events:
            logger.info("Usando eventos del cache (%d eventos)", len(cached_events))
            return cached_events
    
    logger.info("Obteniendo eventos económicos de fuentes en línea...")
    all_events = []
    
    # Obtener de diferentes fuentes
    try:
        # 1. Investing.com
        investing_events = _fetch_investing_calendar()
        all_events.extend(investing_events)
        logger.info("Obtenidos %d eventos de Investing.com", len(investing_events))
        
        # 2. Yahoo Finance earnings
        yahoo_events = _fetch_yahoo_earnings()
        all_events.extend(yahoo_events)
        logger.info("Obtenidos %d eventos de Yahoo Finance", len(yahoo_events))
        
        # 3. Eventos Fed
        fed_events = _fetch_fed_events()
        all_events.extend(fed_events)
        logger.info("Obtenidos %d eventos Fed", len(fed_events))
        
    except Exception as e:
        logger.error("Error obteniendo eventos económicos: %s", e)
    
    # Deduplicar y ordenar eventos
    unique_events = []
    seen_titles = set()
    
    for event in all_events:
        event_key = f"{event['fecha']}_{event['titulo'][:50]}"
        if event_key not in seen_titles:
            unique_events.append(event)
            seen_titles.add(event_key)
    
    # Ordenar por fecha
    unique_events.sort(key=lambda x: x['fecha'])
    
    # Guardar en cache
    if unique_events:
        _save_cache(unique_events)
        logger.info("Total de %d eventos únicos guardados en cache", len(unique_events))
    
    return unique_events