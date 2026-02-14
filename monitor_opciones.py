import yfinance as yf
import time
import pandas as pd
import requests
import winsound
import csv
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from random import randint, uniform, choice
from curl_cffi.requests import Session as CurlSession

# ============================================================================
#                    SISTEMA ANTI-BANEO AVANZADO
# ============================================================================

# 1. Perfiles de navegador para impersonación TLS con curl_cffi
#    curl_cffi replica la huella TLS real de cada navegador (JA3/JA4 fingerprint)
#    Esto es MUCHO más efectivo que solo cambiar el User-Agent
BROWSER_PROFILES = [
    "chrome110", "chrome116", "chrome119", "chrome120",
    "chrome123", "chrome124",
    "edge99", "edge101",
    "safari15_3", "safari15_5", "safari17_0",
]

def crear_sesion_nueva():
    """Crea una sesión curl_cffi que replica la huella TLS de un navegador real.
    Esto incluye: JA3 fingerprint, HTTP/2 settings, header order, etc.
    yfinance maneja las cookies internamente, solo inyectamos el perfil TLS."""
    perfil = choice(BROWSER_PROFILES)
    print(f"  [Anti-Ban] Sesion creada con perfil TLS: {perfil}")
    session = CurlSession(impersonate=perfil)
    return session

# 3. Sistema de backoff exponencial para errores
class BackoffManager:
    """Gestiona tiempos de espera con backoff exponencial cuando hay errores"""
    def __init__(self):
        self.errores_consecutivos = 0
        self.max_backoff = 1800  # Máximo 30 minutos de espera
        self.base_backoff = 120  # Base: 2 minutos

    def registrar_exito(self):
        """Resetea el contador de errores tras un escaneo exitoso"""
        if self.errores_consecutivos > 0:
            print(f"  [Anti-Ban] Conexion restaurada (errores previos: {self.errores_consecutivos})")
        self.errores_consecutivos = 0

    def registrar_error(self, error):
        """Incrementa el backoff y retorna el tiempo de espera calculado"""
        self.errores_consecutivos += 1
        es_ban = self._detectar_ban(error)

        if es_ban:
            # Backoff exponencial: 2min, 4min, 8min, 16min... hasta 30min
            espera = min(self.base_backoff * (2 ** (self.errores_consecutivos - 1)), self.max_backoff)
            espera = espera + randint(0, 60)  # Jitter aleatorio
            print(f"  [Anti-Ban] POSIBLE BAN detectado (error #{self.errores_consecutivos})")
            print(f"  [Anti-Ban] Backoff exponencial: esperando {espera}s...")
        else:
            espera = self.base_backoff + randint(0, 30)
            print(f"  [Anti-Ban] Error de red #{self.errores_consecutivos}, esperando {espera}s...")

        return espera

    def _detectar_ban(self, error):
        """Identifica si el error es probablemente un ban o rate-limit"""
        error_str = str(error).lower()
        indicadores_ban = [
            '429', 'too many requests', 'rate limit',
            '403', 'forbidden', 'blocked',
            '503', 'service unavailable',
            'connection aborted', 'connection refused',
            'read timed out', 'max retries',
        ]
        return any(indicador in error_str for indicador in indicadores_ban)

    @property
    def requiere_nueva_sesion(self):
        """Si hay muchos errores consecutivos, recomienda renovar sesión"""
        return self.errores_consecutivos >= 3

# 4. Pausa aleatoria entre peticiones (simula humano)
def pausa_entre_peticiones(min_seg=1.5, max_seg=4.0):
    """Espera un tiempo aleatorio entre peticiones"""
    delay = uniform(min_seg, max_seg)
    time.sleep(delay)

# 5. Petición a option_chain con reintentos y detección de errores
def obtener_cadena_opciones(ticker, exp_date, intentos_max=3):
    """Obtiene la cadena de opciones con reintentos automáticos"""
    for intento in range(1, intentos_max + 1):
        try:
            chain = ticker.option_chain(exp_date)
            return chain
        except Exception as e:
            error_str = str(e).lower()
            if '429' in error_str or 'too many' in error_str or '403' in error_str:
                espera = 30 * intento + randint(5, 20)
                print(f"    [Reintento {intento}/{intentos_max}] Rate-limit en {exp_date}, esperando {espera}s...")
                time.sleep(espera)
            elif intento < intentos_max:
                espera = 5 * intento + randint(1, 5)
                print(f"    [Reintento {intento}/{intentos_max}] Error en {exp_date}: {e}, esperando {espera}s...")
                time.sleep(espera)
            else:
                raise
    return None

# ============================================================================
#                      CONFIGURACIÓN DE ALERTAS
# ============================================================================
UMBRAL_VOLUMEN = 30000       # Volumen mínimo para alerta principal
UMBRAL_OI = 10000            # Open Interest mínimo para alerta principal
UMBRAL_PRIMA = 5_000_000     # Prima mínima ($5M) para alerta de prima alta
UMBRAL_FILTRO_RAPIDO = 1000  # Filtro rápido: ignorar si vol Y oi están debajo de esto
NUM_FECHAS = 3               # Cuántas fechas de vencimiento escanear

# ============================================================================
#                  CONFIGURACIÓN DE TIEMPOS (Anti-Baneo)
# ============================================================================
ESPERA_MIN = 290             # Segundos mínimos entre escaneos (~5 min)
ESPERA_MAX = 360             # Segundos máximos entre escaneos (~6 min)
PAUSA_ENTRE_FECHAS_MIN = 2.0 # Pausa mínima entre cada fecha de vencimiento
PAUSA_ENTRE_FECHAS_MAX = 5.0 # Pausa máxima entre cada fecha de vencimiento
RENOVAR_SESION_CADA = 10     # Renovar sesión/cookies cada N ciclos

# ============================================================================
#                    CONFIGURACIÓN DE NOTIFICACIONES
# ============================================================================
SONIDO_ACTIVADO = True
FRECUENCIA_BEEP = 1000
DURACION_BEEP = 500
BEEPS_ALERTA_PRINCIPAL = 3
BEEPS_ALERTA_PRIMA = 2

# --- CONFIGURACIÓN DE GMAIL ---
# PASO 1: Ve a https://myaccount.google.com/security
# PASO 2: Activa "Verificación en 2 pasos" si no la tienes
# PASO 3: Ve a https://myaccount.google.com/apppasswords
# PASO 4: Crea una contraseña de aplicación (selecciona "Correo" y "Windows")
# PASO 5: Copia la contraseña de 16 caracteres que te genera (sin espacios)
GMAIL_ACTIVADO = True
GMAIL_REMITENTE = "ev55780990@gmail.com"
GMAIL_CONTRASENA_APP = "xxxx xxxx xxxx xxxx"       # PEGAR AQUI tu contrasena de aplicacion
GMAIL_DESTINATARIO = "ev55780990@gmail.com"

# --- CONFIGURACIÓN DE ARCHIVO CSV ---
CSV_CARPETA = "alertas"

# ============================================================================
#                         FUNCIONES DE NOTIFICACIÓN
# ============================================================================

def notificar(tipo_alerta="PRINCIPAL"):
    """Emite sonido de notificación según el tipo de alerta"""
    if not SONIDO_ACTIVADO:
        return
    try:
        beeps = BEEPS_ALERTA_PRINCIPAL if tipo_alerta == "PRINCIPAL" else BEEPS_ALERTA_PRIMA
        for i in range(beeps):
            winsound.Beep(FRECUENCIA_BEEP, DURACION_BEEP)
            if i < beeps - 1:
                time.sleep(0.2)
    except Exception:
        pass

def construir_mensaje_alerta(ticker_symbol, tipo_alerta, opt_type, exp_date, row, vol, oi, volume_premium, oi_premium):
    """Construye el mensaje detallado de la alerta"""
    emoji = "\U0001f6a8" if tipo_alerta == "PRINCIPAL" else "\U0001f4b0"
    titulo = "ALERTA PRINCIPAL" if tipo_alerta == "PRINCIPAL" else "ALERTA PRIMA ALTA"
    vol_mark = " (>$5M!)" if volume_premium >= UMBRAL_PRIMA else ""
    oi_mark = " (>$5M!)" if oi_premium >= UMBRAL_PRIMA else ""

    mensaje = (
        f"{emoji} {titulo} - {ticker_symbol}\n"
        f"{'='*35}\n"
        f"Tipo: {opt_type}\n"
        f"Vencimiento: {exp_date}\n"
        f"Strike: ${row['strike']}\n"
        f"{'='*35}\n"
        f"Volumen: {vol:,}\n"
        f"Open Interest: {oi:,}\n"
        f"Prima por Volumen: ${volume_premium:,.0f}{vol_mark}\n"
        f"Prima por OI: ${oi_premium:,.0f}{oi_mark}\n"
        f"{'='*35}\n"
        f"Ask: ${row.get('ask', 0)}\n"
        f"Bid: ${row.get('bid', 0)}\n"
        f"Ultimo Precio: ${row.get('lastPrice', 0)}\n"
        f"{'='*35}\n"
        f"Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    return titulo, mensaje

def enviar_gmail(titulo, mensaje, ticker_symbol):
    """Envía un correo con los detalles de la alerta"""
    if not GMAIL_ACTIVADO or GMAIL_REMITENTE == "TU_EMAIL@gmail.com":
        return
    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_REMITENTE
        msg['To'] = GMAIL_DESTINATARIO
        msg['Subject'] = f"ALERTA {titulo} - {ticker_symbol} - {datetime.now().strftime('%H:%M:%S')}"

        html_mensaje = mensaje.replace('\n', '<br>')
        html_body = f"""
        <html>
        <body style="font-family: Consolas, monospace; background-color: #1a1a2e; color: #e0e0e0; padding: 20px;">
            <div style="background-color: #16213e; border-left: 4px solid #e94560; padding: 15px; border-radius: 5px;">
                <pre style="color: #e0e0e0; font-size: 14px;">{html_mensaje}</pre>
            </div>
            <p style="color: #888; font-size: 11px; margin-top: 15px;">Monitor de Opciones - Alerta Automatica</p>
        </body>
        </html>
        """

        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(GMAIL_REMITENTE, GMAIL_CONTRASENA_APP)
            server.send_message(msg)
        print("    [Gmail] Notificacion enviada")
    except Exception as e:
        print(f"    [Gmail] Error: {e}")

def enviar_todas_las_notificaciones(ticker_symbol, tipo_alerta, opt_type, exp_date, row, vol, oi, volume_premium, oi_premium):
    """Envía notificaciones por todos los canales activos"""
    titulo, mensaje = construir_mensaje_alerta(
        ticker_symbol, tipo_alerta, opt_type, exp_date, row, vol, oi, volume_premium, oi_premium
    )
    notificar(tipo_alerta)
    enviar_gmail(titulo, mensaje, ticker_symbol)

# ============================================================================
#                         FUNCIONES DE CSV
# ============================================================================

def inicializar_csv(ticker_symbol):
    """Crea la carpeta y el archivo CSV con encabezados si no existe"""
    os.makedirs(CSV_CARPETA, exist_ok=True)
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    csv_path = os.path.join(CSV_CARPETA, f"alertas_{ticker_symbol}_{fecha_hoy}.csv")
    if not os.path.exists(csv_path):
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                "Fecha_Hora", "Ticker", "Tipo_Alerta", "Tipo_Opcion",
                "Vencimiento", "Strike", "Volumen", "Open_Interest",
                "Prima_Volumen", "Prima_OI", "Precio_Ask", "Precio_Bid",
                "Ultimo_Precio"
            ])
    return csv_path

def guardar_alerta(csv_path, ticker_symbol, tipo_alerta, opt_type, exp_date, row, vol, oi, volume_premium, oi_premium):
    """Guarda una alerta en el archivo CSV"""
    try:
        with open(csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ticker_symbol,
                tipo_alerta,
                opt_type,
                exp_date,
                row['strike'],
                vol,
                oi,
                f"{volume_premium:.0f}",
                f"{oi_premium:.0f}",
                row.get('ask', 0),
                row.get('bid', 0),
                row.get('lastPrice', 0)
            ])
    except Exception as e:
        print(f"  Error guardando alerta en CSV: {e}")

# ============================================================================
#                         INICIO DEL MONITOR
# ============================================================================
ticker_symbol = input("Ingrese el simbolo de la accion a monitorear (ej. SPY, AAPL): ").upper()

# Crear sesión inicial con cookies
print("\n  Inicializando sesion segura...")
session = crear_sesion_nueva()
ticker = yf.Ticker(ticker_symbol, session=session)

# Inicializar sistemas
backoff = BackoffManager()
ciclo_actual = 0

print(f"\n{'='*60}")
print(f"  MONITOR DE OPCIONES - {ticker_symbol}")
print(f"{'='*60}")
print(f"  PROTECCION ANTI-BANEO:")
print(f"    - {len(BROWSER_PROFILES)} perfiles de navegador (TLS fingerprint real)")
print(f"    - curl_cffi: replica JA3/JA4/HTTP2 de Chrome, Edge, Safari")
print(f"    - Cookies gestionadas por yfinance (cache automatico)")
print(f"    - Renovacion de sesion cada {RENOVAR_SESION_CADA} ciclos")
print(f"    - Pausa aleatoria {PAUSA_ENTRE_FECHAS_MIN}-{PAUSA_ENTRE_FECHAS_MAX}s entre fechas")
print(f"    - Backoff exponencial ante errores (hasta 30min)")
print(f"    - Reintentos automaticos con deteccion de ban")
print(f"  ESCANEO:")
print(f"    - Fechas de vencimiento: primeras {NUM_FECHAS}")
print(f"    - Intervalo entre ciclos: {ESPERA_MIN}-{ESPERA_MAX}s")
print(f"  NOTIFICACIONES:")
print(f"    - Sonido: {'Activado' if SONIDO_ACTIVADO else 'Desactivado'}")
print(f"    - Gmail: {'Activado' if GMAIL_ACTIVADO and GMAIL_REMITENTE != 'TU_EMAIL@gmail.com' else 'No configurado'}")
print(f"    - CSV: {CSV_CARPETA}/")
print(f"  Presiona Ctrl+C para detener")
print(f"{'='*60}\n")

csv_path = inicializar_csv(ticker_symbol)
print(f"  Archivo de alertas: {csv_path}\n")

while True:
    try:
        ciclo_actual += 1
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"--- Ciclo #{ciclo_actual} | {ticker_symbol} | {current_time} ---")

        # RENOVACIÓN PERIÓDICA DE SESIÓN
        if ciclo_actual % RENOVAR_SESION_CADA == 0 or backoff.requiere_nueva_sesion:
            print("  [Anti-Ban] Renovando sesion y cookies...")
            session = crear_sesion_nueva()
            ticker = yf.Ticker(ticker_symbol, session=session)
            if backoff.requiere_nueva_sesion:
                print("  [Anti-Ban] Sesion renovada por errores consecutivos")
            else:
                print(f"  [Anti-Ban] Sesion renovada (cada {RENOVAR_SESION_CADA} ciclos)")
            pausa_renovacion = randint(5, 15)
            print(f"  [Anti-Ban] Pausa post-renovacion: {pausa_renovacion}s")
            time.sleep(pausa_renovacion)

        found = False
        options_dates = ticker.options

        if not options_dates:
            print("  No se encontraron fechas de vencimiento.")
        else:
            dates_to_scan = options_dates[:NUM_FECHAS]
            print(f"  Fechas a analizar: {dates_to_scan}")

            for idx, exp_date in enumerate(dates_to_scan):
                try:
                    # Pausa entre cada fecha (simula navegación humana)
                    if idx > 0:
                        pausa_entre_peticiones(PAUSA_ENTRE_FECHAS_MIN, PAUSA_ENTRE_FECHAS_MAX)

                    # Petición con reintentos automáticos
                    chain = obtener_cadena_opciones(ticker, exp_date)
                    if chain is None:
                        continue

                    for opt_type, df in [("CALL", chain.calls), ("PUT", chain.puts)]:
                        for _, row in df.iterrows():
                            vol = int(row['volume']) if pd.notna(row['volume']) and row['volume'] > 0 else 0
                            oi = int(row['openInterest']) if pd.notna(row['openInterest']) else 0

                            if vol < UMBRAL_FILTRO_RAPIDO and oi < UMBRAL_FILTRO_RAPIDO:
                                continue

                            if pd.notna(row['ask']) and row['ask'] > 0:
                                price_volume = row['ask']
                            else:
                                price_volume = row['lastPrice'] if row['lastPrice'] > 0 else 0

                            if row['lastPrice'] > 0:
                                price_oi = row['lastPrice']
                            elif pd.notna(row['bid']) and pd.notna(row['ask']) and row['bid'] > 0 and row['ask'] > 0:
                                price_oi = (row['bid'] + row['ask']) / 2
                            else:
                                price_oi = 0

                            volume_premium = vol * price_volume * 100
                            oi_premium = oi * price_oi * 100

                            vol_mark = " *** >$5M ***" if volume_premium >= UMBRAL_PRIMA else ""
                            oi_mark = " *** >$5M ***" if oi_premium >= UMBRAL_PRIMA else ""

                            if vol >= UMBRAL_VOLUMEN and oi >= UMBRAL_OI:
                                found = True
                                print(f"\n  ALERTA PRINCIPAL! {opt_type} - Exp: {exp_date} - Strike: {row['strike']}")
                                print(f"    Vol: {vol:,} | OI: {oi:,} | Prima Vol: ${volume_premium:,.0f}{vol_mark} | Prima OI: ${oi_premium:,.0f}{oi_mark}")
                                guardar_alerta(csv_path, ticker_symbol, "PRINCIPAL", opt_type, exp_date, row, vol, oi, volume_premium, oi_premium)
                                enviar_todas_las_notificaciones(ticker_symbol, "PRINCIPAL", opt_type, exp_date, row, vol, oi, volume_premium, oi_premium)

                            elif volume_premium >= UMBRAL_PRIMA or oi_premium >= UMBRAL_PRIMA:
                                found = True
                                print(f"\n  ALERTA PRIMA ALTA! {opt_type} - Exp: {exp_date} - Strike: {row['strike']}")
                                print(f"    Vol: {vol:,} | OI: {oi:,} | Prima Vol: ${volume_premium:,.0f}{vol_mark} | Prima OI: ${oi_premium:,.0f}{oi_mark}")
                                guardar_alerta(csv_path, ticker_symbol, "PRIMA_ALTA", opt_type, exp_date, row, vol, oi, volume_premium, oi_premium)
                                enviar_todas_las_notificaciones(ticker_symbol, "PRIMA_ALTA", opt_type, exp_date, row, vol, oi, volume_premium, oi_premium)

                except Exception as inner_e:
                    print(f"  Error leyendo fecha {exp_date}: {inner_e}")
                    continue

        if not found:
            print("  Sin alertas relevantes en este ciclo.")

        # Escaneo exitoso: resetear backoff
        backoff.registrar_exito()

        # Espera aleatoria entre ciclos
        sleep_time = randint(ESPERA_MIN, ESPERA_MAX)
        print(f"  Proximo escaneo en {sleep_time}s (ciclo #{ciclo_actual + 1})\n")
        time.sleep(sleep_time)

    except KeyboardInterrupt:
        print(f"\n\nMonitoreo detenido despues de {ciclo_actual} ciclos.")
        print(f"Alertas guardadas en: {csv_path}")
        break
    except Exception as e:
        espera = backoff.registrar_error(e)
        print(f"  Error general: {e}")
        time.sleep(espera)
