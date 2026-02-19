# -*- coding: utf-8 -*-
"""
Gamma Exposure (GEX) Calculator — Motor de cálculo profesional.

Implementa la fórmula estándar de GEX utilizada por SqueezeMetrics,
SpotGamma y repositorios públicos (perfiliev, Matteo-Ferrara/gex-tracker):

    GEX_i = gamma_i × OI_i × contract_size × S² × 0.01 × dealer_sign

donde:
    - gamma_i       : gamma BSM del contrato i
    - OI_i          : open interest del contrato i
    - contract_size : multiplicador (normalmente 100 acciones)
    - S             : precio spot del subyacente
    - 0.01          : normaliza a "por cada 1% de movimiento del spot"
    - dealer_sign   : +1 o -1 según convención de positionamiento del dealer

Modos soportados:
    "short_gamma"  → dealer_sign = -1 para calls y puts
                     (market makers generalmente short gamma en ambas)
    "standard"     → calls +1, puts -1
                     (convención de muchos dashboards públicos)

Dependencias: pandas, numpy, scipy, matplotlib (solo para plot), datetime.
"""

from __future__ import annotations

import warnings
from datetime import datetime, date
from typing import Optional, Union

import numpy as np
import pandas as pd
from scipy.stats import norm


# ======================================================================
# Gamma Black-Scholes-Merton (vectorizado)
# ======================================================================

def black_scholes_gamma(
    S: Union[float, np.ndarray],
    K: Union[float, np.ndarray],
    T: Union[float, np.ndarray],
    r: float,
    sigma: Union[float, np.ndarray],
    q: float = 0.0,
) -> np.ndarray:
    """
    Calcula la gamma BSM para opciones europeas (calls y puts tienen la misma gamma).

    Fórmula
    -------
        Γ = e^(-q·T) · N'(d1) / (S · σ · √T)

        donde  d1 = [ln(S/K) + (r - q + σ²/2)·T] / (σ·√T)
               N'(·) = PDF de la distribución normal estándar

    Parámetros
    ----------
    S     : precio spot del subyacente
    K     : strike price
    T     : tiempo a vencimiento en años (>0)
    r     : tasa libre de riesgo anualizada (ej. 0.045 para 4.5%)
    sigma : volatilidad implícita anualizada (ej. 0.25 para 25%)
    q     : dividend yield continuo (default 0.0)

    Retorna
    -------
    np.ndarray  —  gamma por contrato individual (antes de multiplicar por OI, S², etc.)
    """
    # Convertir a arrays numpy para vectorización
    S = np.atleast_1d(np.asarray(S, dtype=np.float64))
    K = np.atleast_1d(np.asarray(K, dtype=np.float64))
    T = np.atleast_1d(np.asarray(T, dtype=np.float64))
    sigma = np.atleast_1d(np.asarray(sigma, dtype=np.float64))

    # Broadcast a la misma forma (permite S escalar + K array, etc.)
    S, K, T, sigma = np.broadcast_arrays(S, K, T, sigma)

    # Máscara de valores válidos: evitar divisiones por cero y log de negativos
    valid = (S > 0) & (K > 0) & (T > 0) & (sigma > 0)

    # Inicializar resultado con ceros (contratos inválidos → gamma = 0)
    gamma = np.zeros_like(S, dtype=np.float64)

    if not valid.any():
        return gamma

    # Extraer solo valores válidos para el cálculo
    s = S[valid]
    k = K[valid]
    t = T[valid]
    sig = sigma[valid]

    # d1 según BSM con dividendos continuos
    vol_sqrt_t = sig * np.sqrt(t)
    d1 = (np.log(s / k) + (r - q + 0.5 * sig**2) * t) / vol_sqrt_t

    # Gamma = e^(-q·T) · φ(d1) / (S · σ · √T)
    disc_q = np.exp(-q * t)
    gamma[valid] = disc_q * norm.pdf(d1) / (s * vol_sqrt_t)

    return gamma


# ======================================================================
# Clase principal: GammaExposureCalculator
# ======================================================================

class GammaExposureCalculator:
    """
    Calculadora de Gamma Exposure (GEX) para un chain completo de opciones.

    Parámetros del constructor
    --------------------------
    options_df       : DataFrame con columnas mínimas:
                       'expiration_date', 'strike', 'option_type', 'open_interest'
                       Opcionales: 'gamma', 'implied_volatility'
    spot_price       : precio actual del subyacente
    calculation_date : fecha de referencia para calcular DTE (default = hoy)
    contract_size    : multiplicador de contrato (default 100)
    mode             : "short_gamma" | "standard"
    risk_free_rate   : tasa libre de riesgo (default 0.045)
    dividend_yield   : dividend yield continuo (default 0.0)

    Ejemplo rápido
    --------------
    >>> calc = GammaExposureCalculator(chain_df, spot_price=585.0)
    >>> result = calc.calculate_gex()
    >>> print(f"Total GEX: ${result['total_gex']:.2f}M")
    >>> print(f"Zero Gamma: ${result['zero_gamma_level']:.2f}")
    >>> print(f"Call Wall:  ${result['call_wall']:.2f}")
    >>> print(f"Put Wall:   ${result['put_wall']:.2f}")
    """

    # Columnas requeridas (mínimas)
    _REQUIRED_COLS = {"expiration_date", "strike", "option_type", "open_interest"}

    def __init__(
        self,
        options_df: pd.DataFrame,
        spot_price: float,
        calculation_date: Optional[Union[datetime, date]] = None,
        contract_size: int = 100,
        mode: str = "short_gamma",
        risk_free_rate: float = 0.045,
        dividend_yield: float = 0.0,
    ) -> None:
        # --- Validaciones de entrada ---
        if spot_price <= 0:
            raise ValueError(f"spot_price debe ser > 0, recibido: {spot_price}")
        if mode not in ("short_gamma", "standard"):
            raise ValueError(f"mode debe ser 'short_gamma' o 'standard', recibido: '{mode}'")
        if options_df.empty:
            raise ValueError("options_df está vacío — no hay contratos para analizar")

        missing = self._REQUIRED_COLS - set(options_df.columns)
        if missing:
            raise ValueError(f"Columnas faltantes en options_df: {missing}")

        self.spot_price = float(spot_price)
        self.contract_size = int(contract_size)
        self.mode = mode
        self.r = float(risk_free_rate)
        self.q = float(dividend_yield)
        self.calculation_date = (
            calculation_date if calculation_date is not None else datetime.now()
        )

        # Normalizar la fecha de cálculo a date para comparación
        if isinstance(self.calculation_date, datetime):
            self._calc_date = self.calculation_date.date()
        else:
            self._calc_date = self.calculation_date

        # Preparar DataFrame interno (copia para no mutar el original)
        self._df = self._prepare_dataframe(options_df.copy())

    # ------------------------------------------------------------------
    # Preparación del DataFrame
    # ------------------------------------------------------------------

    def _prepare_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normaliza columnas, calcula DTE (time to expiry) y rellena gamma
        si no existe en el DataFrame original.

        Pasos:
        1. Normalizar option_type a minúsculas ('call', 'put')
        2. Parsear expiration_date a datetime si viene como string
        3. Calcular T = DTE en años
        4. Si no existe columna 'gamma', calcularla con BSM
        5. Eliminar filas con T <= 0 (contratos vencidos)
        """
        # 1. Normalizar tipo de opción
        df["option_type"] = df["option_type"].astype(str).str.strip().str.lower()
        # Aceptar formatos comunes: 'CALL'/'call'/'C' → 'call'
        df["option_type"] = df["option_type"].replace({"c": "call", "p": "put"})

        # 2. Parsear fechas de vencimiento
        if not pd.api.types.is_datetime64_any_dtype(df["expiration_date"]):
            df["expiration_date"] = pd.to_datetime(df["expiration_date"], errors="coerce")

        # 3. Calcular DTE en años (fracción de 365 días)
        df["_dte_days"] = (df["expiration_date"].dt.date - self._calc_date).apply(
            lambda d: d.days if hasattr(d, "days") else 0
        )
        df["_T"] = df["_dte_days"] / 365.0

        # Eliminar contratos ya vencidos o con DTE inválido
        n_before = len(df)
        df = df[df["_T"] > 0].copy()
        n_removed = n_before - len(df)
        if n_removed > 0:
            warnings.warn(
                f"Se eliminaron {n_removed} contratos con DTE ≤ 0 (ya vencidos).",
                stacklevel=2,
            )

        # 4. Asegurar que open_interest es numérico y ≥ 0
        df["open_interest"] = pd.to_numeric(df["open_interest"], errors="coerce").fillna(0).astype(int)
        df["strike"] = pd.to_numeric(df["strike"], errors="coerce")

        # 5. Calcular gamma si no existe la columna
        if "gamma" not in df.columns or df["gamma"].isna().all():
            # Necesitamos implied_volatility para calcular gamma
            if "implied_volatility" not in df.columns:
                raise ValueError(
                    "El DataFrame no tiene columna 'gamma' ni 'implied_volatility'. "
                    "Se necesita al menos una para calcular GEX."
                )
            iv = pd.to_numeric(df["implied_volatility"], errors="coerce").fillna(0).values
            df["gamma"] = black_scholes_gamma(
                S=self.spot_price,
                K=df["strike"].values,
                T=df["_T"].values,
                r=self.r,
                sigma=iv,
                q=self.q,
            )
        else:
            # Si existe gamma pero tiene NaNs, rellenar con BSM donde sea posible
            mask_nan = df["gamma"].isna()
            if mask_nan.any() and "implied_volatility" in df.columns:
                iv_fill = pd.to_numeric(
                    df.loc[mask_nan, "implied_volatility"], errors="coerce"
                ).fillna(0).values
                df.loc[mask_nan, "gamma"] = black_scholes_gamma(
                    S=self.spot_price,
                    K=df.loc[mask_nan, "strike"].values,
                    T=df.loc[mask_nan, "_T"].values,
                    r=self.r,
                    sigma=iv_fill,
                    q=self.q,
                )
            df["gamma"] = pd.to_numeric(df["gamma"], errors="coerce").fillna(0)

        return df

    # ------------------------------------------------------------------
    # Método principal: calculate_gex()
    # ------------------------------------------------------------------

    def calculate_gex(self) -> dict:
        """
        Calcula la Gamma Exposure (GEX) completa.

        Fórmula por contrato
        ---------------------
            GEX_i = gamma_i × OI_i × contract_size × S² × 0.01 × dealer_sign_i

        Retorna
        -------
        dict con:
            'total_gex'         : GEX total en millones de dólares
            'gex_df'            : DataFrame detallado (GEX por contrato/strike/exp)
            'zero_gamma_level'  : strike donde el GEX acumulado cruza cero
            'call_wall'         : strike con mayor GEX positivo (calls)
            'put_wall'          : strike con mayor GEX negativo (puts)
        """
        df = self._df.copy()

        if df.empty:
            return {
                "total_gex": 0.0,
                "gex_df": pd.DataFrame(),
                "zero_gamma_level": self.spot_price,
                "call_wall": self.spot_price,
                "put_wall": self.spot_price,
            }

        # --- Calcular dealer_sign según el modo ---
        #
        # Modo "short_gamma" (SqueezeMetrics):
        #   Los market makers están short gamma en calls Y puts →
        #   dealer_sign = -1 para todos.
        #   Resultado: GEX total típicamente negativo = mercado con gamma negativa.
        #
        # Modo "standard" (SpotGamma, dashboards públicos):
        #   Calls → dealers long gamma (+1) → GEX positivo (resistencia)
        #   Puts  → dealers short gamma (-1) → GEX negativo (aceleración)
        #
        if self.mode == "short_gamma":
            df["_dealer_sign"] = -1.0
        else:  # "standard"
            df["_dealer_sign"] = np.where(df["option_type"] == "call", 1.0, -1.0)

        # --- Aplicar la fórmula GEX vectorizada ---
        # GEX_i = gamma × OI × contract_size × S² × 0.01 × dealer_sign
        S2 = self.spot_price ** 2
        df["gex"] = (
            df["gamma"]
            * df["open_interest"]
            * self.contract_size
            * S2
            * 0.01
            * df["_dealer_sign"]
        )

        # GEX total en dólares → convertir a millones
        total_gex_dollars = df["gex"].sum()
        total_gex_millions = total_gex_dollars / 1_000_000

        # --- Nivel Zero Gamma (donde el GEX acumulado cruza cero) ---
        zero_gamma = self._find_zero_gamma(df)

        # --- Call Wall y Put Wall ---
        call_wall, put_wall = self._find_walls(df)

        # --- DataFrame de salida con columnas útiles ---
        gex_df = df[
            ["expiration_date", "strike", "option_type", "open_interest",
             "gamma", "_dte_days", "gex"]
        ].copy()
        gex_df.rename(columns={"_dte_days": "dte"}, inplace=True)

        return {
            "total_gex": round(total_gex_millions, 4),
            "gex_df": gex_df,
            "zero_gamma_level": round(zero_gamma, 2),
            "call_wall": round(call_wall, 2),
            "put_wall": round(put_wall, 2),
        }

    # ------------------------------------------------------------------
    # Perfil de GEX por strike (agrupado)
    # ------------------------------------------------------------------

    def get_gex_profile(
        self,
        expiration_filter: Optional[Union[str, list]] = None,
    ) -> pd.DataFrame:
        """
        Perfil de GEX agrupado por strike, sumando todas las expiraciones
        (o solo las indicadas en expiration_filter).

        Parámetros
        ----------
        expiration_filter : str o lista de str con fechas YYYY-MM-DD
                            None = todas las expiraciones
                            "0dte" = solo contratos que vencen hoy
                            "weekly" = contratos con DTE ≤ 7

        Retorna
        -------
        DataFrame con columnas: strike, gex_call, gex_put, gex_total
        ordenado por strike ascendente.
        """
        result = self.calculate_gex()
        df = result["gex_df"].copy()

        # Aplicar filtro de expiración
        df = self._apply_expiry_filter(df, expiration_filter)

        if df.empty:
            return pd.DataFrame(columns=["strike", "gex_call", "gex_put", "gex_total"])

        # Separar calls y puts, agrupar por strike
        calls = df[df["option_type"] == "call"].groupby("strike")["gex"].sum().rename("gex_call")
        puts = df[df["option_type"] == "put"].groupby("strike")["gex"].sum().rename("gex_put")

        # Unir en un solo DataFrame
        profile = pd.DataFrame({"gex_call": calls, "gex_put": puts}).fillna(0)
        profile["gex_total"] = profile["gex_call"] + profile["gex_put"]
        profile = profile.reset_index().sort_values("strike")

        return profile

    # ------------------------------------------------------------------
    # Gráfico del perfil GEX
    # ------------------------------------------------------------------

    def plot_gex_profile(
        self,
        expiration_filter: Optional[Union[str, list]] = None,
        figsize: tuple = (14, 7),
        top_n_strikes: int = 50,
    ):
        """
        Genera un gráfico de barras del perfil GEX por strike.

        Elementos visuales:
        - Barras verdes: GEX positivo (resistencia / calls)
        - Barras rojas: GEX negativo (aceleración / puts)
        - Línea punteada horizontal: Zero Gamma Level
        - Línea vertical: precio spot actual
        - Marcadores: Call Wall (▲) y Put Wall (▼)

        Retorna
        -------
        matplotlib Figure (para guardar o mostrar)
        """
        import matplotlib.pyplot as plt
        import matplotlib.ticker as mticker

        profile = self.get_gex_profile(expiration_filter)
        if profile.empty:
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.text(0.5, 0.5, "Sin datos para graficar", ha="center", va="center",
                    fontsize=14, color="gray", transform=ax.transAxes)
            return fig

        result = self.calculate_gex()

        # Filtrar a los N strikes más cercanos al spot para legibilidad
        profile["_dist"] = abs(profile["strike"] - self.spot_price)
        profile = profile.nsmallest(top_n_strikes, "_dist").sort_values("strike")
        profile.drop(columns=["_dist"], inplace=True)

        # Convertir GEX a millones para el eje Y
        profile["gex_total_m"] = profile["gex_total"] / 1_000_000

        # --- Crear figura ---
        fig, ax = plt.subplots(figsize=figsize, facecolor="#0e1117")
        ax.set_facecolor("#0e1117")

        # Colores según signo
        colors = ["#00ff88" if v >= 0 else "#ef4444" for v in profile["gex_total_m"]]

        ax.bar(
            profile["strike"].astype(str),
            profile["gex_total_m"],
            color=colors,
            edgecolor="none",
            alpha=0.85,
            width=0.8,
        )

        # --- Línea Zero Gamma ---
        ax.axhline(y=0, color="#94a3b8", linewidth=0.8, linestyle="--", alpha=0.6)

        # --- Etiquetas de Call Wall y Put Wall ---
        cw = result["call_wall"]
        pw = result["put_wall"]
        zg = result["zero_gamma_level"]

        # Encontrar posiciones en el eje X
        strikes_str = profile["strike"].astype(str).tolist()
        cw_str = str(round(cw, 2))
        pw_str = str(round(pw, 2))

        if cw_str in strikes_str:
            idx_cw = strikes_str.index(cw_str)
            ax.annotate(
                f"Call Wall\n${cw:.0f}",
                xy=(idx_cw, profile.iloc[idx_cw]["gex_total_m"]),
                fontsize=9, fontweight="bold", color="#00ff88",
                ha="center", va="bottom",
            )
        if pw_str in strikes_str:
            idx_pw = strikes_str.index(pw_str)
            ax.annotate(
                f"Put Wall\n${pw:.0f}",
                xy=(idx_pw, profile.iloc[idx_pw]["gex_total_m"]),
                fontsize=9, fontweight="bold", color="#ef4444",
                ha="center", va="top",
            )

        # --- Formato de ejes ---
        ax.set_xlabel("Strike", fontsize=11, color="#e2e8f0")
        ax.set_ylabel("GEX ($M)", fontsize=11, color="#e2e8f0")
        ax.set_title(
            f"Gamma Exposure Profile — Spot: ${self.spot_price:.2f} | "
            f"Mode: {self.mode} | Total GEX: ${result['total_gex']:.2f}M",
            fontsize=13, fontweight="bold", color="#f1f5f9", pad=15,
        )
        ax.tick_params(axis="both", colors="#94a3b8", labelsize=8)

        # Rotar labels del eje X para legibilidad
        plt.xticks(rotation=45, ha="right")

        # Mostrar solo algunos labels si hay demasiados strikes
        if len(strikes_str) > 25:
            for i, label in enumerate(ax.xaxis.get_ticklabels()):
                if i % 3 != 0:
                    label.set_visible(False)

        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#334155")
        ax.spines["bottom"].set_color("#334155")

        plt.tight_layout()
        return fig

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _find_zero_gamma(self, df: pd.DataFrame) -> float:
        """
        Encuentra el nivel Zero Gamma: strike donde el GEX acumulado
        (ordenado por strike ascendente) cruza de positivo a negativo
        o viceversa.

        Si no hay cruce, devuelve el strike con menor GEX absoluto acumulado.

        El Zero Gamma Level es el precio "pivote": por encima, los dealers
        compran caídas (estabilizador); por debajo, venden caídas (acelerador).
        """
        # Agrupar GEX por strike
        gex_by_strike = df.groupby("strike")["gex"].sum().sort_index()

        if gex_by_strike.empty:
            return self.spot_price

        # GEX acumulado de izquierda a derecha
        cum_gex = gex_by_strike.cumsum()
        strikes = cum_gex.index.values
        values = cum_gex.values

        # Buscar cruce por cero (cambio de signo)
        sign_changes = np.where(np.diff(np.sign(values)))[0]

        if len(sign_changes) > 0:
            # Tomar el cruce más cercano al spot
            cross_idx = sign_changes[
                np.argmin(np.abs(strikes[sign_changes] - self.spot_price))
            ]
            # Interpolación lineal entre los dos strikes adyacentes
            s1, s2 = strikes[cross_idx], strikes[cross_idx + 1]
            v1, v2 = values[cross_idx], values[cross_idx + 1]
            if v2 != v1:
                zero_level = s1 + (s2 - s1) * (-v1) / (v2 - v1)
            else:
                zero_level = (s1 + s2) / 2
            return float(zero_level)

        # Sin cruce → retornar strike con menor GEX absoluto
        min_idx = np.argmin(np.abs(values))
        return float(strikes[min_idx])

    def _find_walls(self, df: pd.DataFrame) -> tuple[float, float]:
        """
        Determina Call Wall y Put Wall.

        - Call Wall : strike con mayor GEX positivo (concentración de resistencia)
        - Put Wall  : strike con mayor GEX negativo (concentración de aceleración)

        Estos niveles actúan como "imanes" de precio en sesiones de mercado
        dominadas por hedging de dealers.
        """
        # GEX agrupado por strike y tipo
        calls_gex = (
            df[df["option_type"] == "call"]
            .groupby("strike")["gex"]
            .sum()
        )
        puts_gex = (
            df[df["option_type"] == "put"]
            .groupby("strike")["gex"]
            .sum()
        )

        # Call Wall: strike con mayor GEX (positivo o con mayor magnitud)
        if not calls_gex.empty:
            if self.mode == "standard":
                # En modo standard, calls son positivas → máximo
                call_wall = float(calls_gex.idxmax())
            else:
                # En short_gamma, todo negativo → el menos negativo = mayor
                call_wall = float(calls_gex.idxmax())
        else:
            call_wall = self.spot_price

        # Put Wall: strike con GEX más negativo (mayor magnitud negativa)
        if not puts_gex.empty:
            put_wall = float(puts_gex.idxmin())
        else:
            put_wall = self.spot_price

        return call_wall, put_wall

    def _apply_expiry_filter(
        self, df: pd.DataFrame, filt: Optional[Union[str, list]]
    ) -> pd.DataFrame:
        """
        Filtra el DataFrame por vencimiento.

        Opciones:
        - None        → sin filtro (todas)
        - "0dte"      → solo contratos que vencen hoy
        - "weekly"    → DTE ≤ 7
        - "monthly"   → DTE ≤ 35
        - lista       → fechas específicas (YYYY-MM-DD)
        """
        if filt is None:
            return df

        if isinstance(filt, str):
            filt_lower = filt.strip().lower()
            if filt_lower == "0dte":
                return df[df["dte"] == 0]
            elif filt_lower == "weekly":
                return df[df["dte"] <= 7]
            elif filt_lower == "monthly":
                return df[df["dte"] <= 35]
            else:
                # Intentar como fecha individual
                return df[df["expiration_date"].dt.strftime("%Y-%m-%d") == filt]

        if isinstance(filt, list):
            return df[df["expiration_date"].dt.strftime("%Y-%m-%d").isin(filt)]

        return df

    # ------------------------------------------------------------------
    # Representación
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        n = len(self._df)
        return (
            f"GammaExposureCalculator("
            f"contracts={n}, spot=${self.spot_price:.2f}, "
            f"mode='{self.mode}')"
        )


# ======================================================================
# Función helper para integración rápida con datos del scanner
# ======================================================================

def calcular_gex_desde_scanner(
    datos_completos: list[dict],
    spot_price: float,
    mode: str = "standard",
) -> dict:
    """
    Wrapper rápido: toma la lista de datos_completos del scanner y
    calcula GEX sin necesidad de construir manualmente el DataFrame.

    Parámetros
    ----------
    datos_completos : list[dict] — salida de ejecutar_escaneo()[1]
                      Cada dict tiene: Vencimiento, Strike, Tipo, OI,
                      IV, Gamma (si existe), etc.
    spot_price      : precio actual del subyacente
    mode            : "short_gamma" | "standard"

    Retorna
    -------
    dict idéntico al retornado por calculate_gex():
        total_gex, gex_df, zero_gamma_level, call_wall, put_wall
    """
    if not datos_completos or spot_price <= 0:
        return {
            "total_gex": 0.0,
            "gex_df": pd.DataFrame(),
            "zero_gamma_level": spot_price if spot_price > 0 else 0.0,
            "call_wall": spot_price if spot_price > 0 else 0.0,
            "put_wall": spot_price if spot_price > 0 else 0.0,
        }

    # Construir DataFrame desde los datos del scanner
    df = pd.DataFrame(datos_completos)

    # Mapear nombres de columnas del scanner → formato esperado
    rename_map = {
        "Vencimiento": "expiration_date",
        "Strike": "strike",
        "Tipo": "option_type",
        "OI": "open_interest",
        "IV": "implied_volatility",  # ya en %, la convertimos abajo
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # Verificar columnas mínimas
    required = {"expiration_date", "strike", "option_type", "open_interest"}
    if not required.issubset(df.columns):
        return {
            "total_gex": 0.0,
            "gex_df": pd.DataFrame(),
            "zero_gamma_level": spot_price,
            "call_wall": spot_price,
            "put_wall": spot_price,
        }

    # La IV del scanner viene en porcentaje (ej. 25.5 para 25.5%) → convertir a decimal
    if "implied_volatility" in df.columns:
        df["implied_volatility"] = pd.to_numeric(
            df["implied_volatility"], errors="coerce"
        ).fillna(0) / 100.0

    # Si el scanner ya calculó Gamma, mapearla
    if "Gamma" in df.columns:
        df["gamma"] = pd.to_numeric(df["Gamma"], errors="coerce")

    # Mapear tipos: CALL/PUT → call/put
    df["option_type"] = df["option_type"].str.lower()

    try:
        calc = GammaExposureCalculator(
            options_df=df,
            spot_price=spot_price,
            mode=mode,
        )
        return calc.calculate_gex()
    except Exception:
        return {
            "total_gex": 0.0,
            "gex_df": pd.DataFrame(),
            "zero_gamma_level": spot_price,
            "call_wall": spot_price,
            "put_wall": spot_price,
        }


# ======================================================================
# Ejemplo de uso (ejecutar directamente: python -m core.gamma_exposure)
# ======================================================================

if __name__ == "__main__":
    # --- Datos ficticios simulando un chain de SPY ---
    np.random.seed(42)
    spot = 585.0
    strikes = np.arange(560, 610, 2.5)

    rows = []
    for exp_offset in [1, 7, 30]:  # 0DTE, weekly, monthly
        exp_date = datetime(2026, 2, 19 + exp_offset) if exp_offset < 28 else datetime(2026, 3, 20)
        for s in strikes:
            for otype in ["call", "put"]:
                # IV más alta lejos del dinero (skew simple)
                moneyness = abs(s - spot) / spot
                iv = 0.18 + moneyness * 0.5 + np.random.uniform(-0.02, 0.02)
                oi = int(np.random.uniform(500, 15000))
                rows.append({
                    "expiration_date": exp_date,
                    "strike": s,
                    "option_type": otype,
                    "open_interest": oi,
                    "implied_volatility": iv,
                })

    sample_df = pd.DataFrame(rows)

    print("=" * 60)
    print("  GAMMA EXPOSURE CALCULATOR — Ejemplo con datos ficticios")
    print("=" * 60)
    print(f"\nSpot: ${spot:.2f}")
    print(f"Contratos: {len(sample_df)}")
    print(f"Strikes: {strikes.min():.1f} – {strikes.max():.1f}")
    print(f"Expiraciones: {sample_df['expiration_date'].nunique()}")

    # --- Calcular GEX (modo standard) ---
    calc = GammaExposureCalculator(sample_df, spot_price=spot, mode="standard")
    result = calc.calculate_gex()

    print(f"\n--- Resultados (modo standard) ---")
    print(f"Total GEX:        ${result['total_gex']:+.4f}M")
    print(f"Zero Gamma Level: ${result['zero_gamma_level']:.2f}")
    print(f"Call Wall:        ${result['call_wall']:.2f}")
    print(f"Put Wall:         ${result['put_wall']:.2f}")

    # --- Perfil por strike ---
    profile = calc.get_gex_profile()
    print(f"\n--- Top 5 strikes por |GEX| ---")
    top5 = profile.reindex(profile["gex_total"].abs().nlargest(5).index)
    for _, row in top5.iterrows():
        print(f"  Strike ${row['strike']:>7.1f} → GEX: ${row['gex_total']/1e6:+.4f}M")

    # --- Calcular con modo short_gamma ---
    calc_sg = GammaExposureCalculator(sample_df, spot_price=spot, mode="short_gamma")
    result_sg = calc_sg.calculate_gex()
    print(f"\n--- Resultados (modo short_gamma) ---")
    print(f"Total GEX:        ${result_sg['total_gex']:+.4f}M")

    print("\n✅ Cálculo completado exitosamente.")
