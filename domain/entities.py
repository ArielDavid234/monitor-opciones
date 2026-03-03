# -*- coding: utf-8 -*-
"""
Entidades de dominio — modelos Pydantic que representan los objetos
centrales del negocio.  Cero dependencias de Streamlit.

Principio: estas clases son el "corazón" de la app — puras, portables,
testeables.  Ninguna página ni servicio debería crear dicts crudos donde
puede usar una entidad.

Modelos incluidos:
  - Enums: SpreadType, Trend, UserRole, QualityLabel
  - Entidades: User, ScanResult, CreditSpread, Alert, UserStats
  - Value Objects: IVMetrics, TrendIndicators, ScoreBreakdownItem
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Pydantic v2 — graceful fallback a dataclass si no está disponible
# ---------------------------------------------------------------------------
try:
    from pydantic import BaseModel, Field, field_validator

    _USE_PYDANTIC = True
except ImportError:
    from dataclasses import dataclass as BaseModel  # type: ignore[assignment]
    Field = lambda default=None, **_: default  # noqa: E731
    _USE_PYDANTIC = False


# ============================================================================
#  Enums
# ============================================================================

class SpreadType(str, Enum):
    """Tipo de credit spread."""
    BULL_PUT = "Bull Put"
    BEAR_CALL = "Bear Call"


class Trend(str, Enum):
    """Tendencia del subyacente (VWAP + EMA9/EMA21)."""
    ALCISTA = "Alcista"
    BAJISTA = "Bajista"
    NEUTRAL = "Neutral"
    UNKNOWN = "Desconocido"


class UserRole(str, Enum):
    """Rol del usuario en la plataforma."""
    ADMIN = "admin"
    PRO = "pro"
    FREE = "free"
    USER = "user"  # rol genérico almacenado por _ensure_profile


class QualityLabel(str, Enum):
    """Etiqueta de calidad para Income Score / Score Oportunidad."""
    EXCELENTE = "Excelente"
    ALTA_PROBABILIDAD = "Alta probabilidad"
    BUENA = "Buena"
    EVITAR = "Evitar"
    BAJA = "Baja"


# ============================================================================
#  Value Objects (inmutables, sin identidad propia)
# ============================================================================

class IVMetrics(BaseModel if _USE_PYDANTIC else object):  # type: ignore[misc]
    """Métricas de Implied Volatility para un ticker."""

    iv_current: float = 0.0
    iv_rank: float = 0.0
    iv_percentile: float = 0.0
    iv_1y_high: float = 0.0
    iv_1y_low: float = 0.0

    @property
    def is_elevated(self) -> bool:
        """True si IV Rank > 40 — zona de oportunidad para venta de prima."""
        return self.iv_rank > 40.0

    def to_dict(self) -> dict[str, float]:
        """Serializa a dict plano."""
        return {
            "iv_current": self.iv_current,
            "iv_rank": self.iv_rank,
            "iv_percentile": self.iv_percentile,
            "iv_1y_high": self.iv_1y_high,
            "iv_1y_low": self.iv_1y_low,
        }


class TrendIndicators(BaseModel if _USE_PYDANTIC else object):  # type: ignore[misc]
    """Indicadores de tendencia (VWAP, EMA9, EMA21)."""

    vwap: float = 0.0
    ema9: float = 0.0
    ema21: float = 0.0
    trend: Trend = Trend.NEUTRAL
    preferred_type: Optional[str] = None  # "Bull Put" | "Bear Call" | None

    def to_dict(self) -> dict[str, Any]:
        """Serializa a dict plano."""
        return {
            "vwap": self.vwap,
            "ema9": self.ema9,
            "ema21": self.ema21,
            "trend": self.trend.value if isinstance(self.trend, Trend) else self.trend,
            "preferred_type": self.preferred_type,
        }


class ScoreBreakdownItem(BaseModel if _USE_PYDANTIC else object):  # type: ignore[misc]
    """Una línea del desglose de puntaje (criterio + resultado)."""

    criterio: str
    detalle: str
    puntos: int
    maximo: int = 20
    cumple: bool = False


# ============================================================================
#  Entidades principales
# ============================================================================

class User(BaseModel if _USE_PYDANTIC else object):  # type: ignore[misc]
    """Usuario autenticado de la plataforma."""

    id: str
    email: str
    name: str
    role: str = "pro"
    is_active: bool = True
    created_at: Optional[datetime] = None

    @property
    def initials(self) -> str:
        """Iniciales para el avatar (máx. 2 caracteres)."""
        return "".join(w[0].upper() for w in (self.name or "U").split()[:2])

    @property
    def is_admin(self) -> bool:
        """True si el usuario es administrador."""
        return str(self.role).lower() == "admin"

    @property
    def role_label(self) -> str:
        """Etiqueta legible del rol para mostrar en sidebar."""
        return "👑 Admin" if self.is_admin else "● Pro Plan"

    @classmethod
    def from_auth_dict(cls, raw: dict[str, Any]) -> "User":
        """Construye un User desde el dict crudo de auth.get_current_user()."""
        return cls(
            id=raw.get("id", ""),
            email=raw.get("email", ""),
            name=raw.get("name", raw.get("email", "Usuario")),
            role=str(raw.get("role") or "user").lower(),
            is_active=raw.get("is_active", True),
        )


class ScanResult(BaseModel if _USE_PYDANTIC else object):  # type: ignore[misc]
    """Resultado de un escaneo de opciones para un ticker."""

    ticker: str
    price: float
    iv_rank: Optional[float] = None
    iv_percentile: Optional[float] = None
    trend: Trend = Trend.UNKNOWN
    avg_volume: Optional[float] = None
    scan_timestamp: datetime = Field(default_factory=datetime.utcnow)


class CreditSpread(BaseModel if _USE_PYDANTIC else object):  # type: ignore[misc]
    """Un credit spread individual encontrado por el scanner."""

    ticker: str
    spread_type: SpreadType
    expiration: str          # YYYY-MM-DD
    dte: int                 # días hasta vencimiento
    sell_strike: float
    buy_strike: float
    credit: float            # crédito neto ($)
    width: float             # ancho del spread ($)
    pop: float               # probability of profit (0-1)
    delta: float             # delta del strike vendido (|abs|)
    iv_rank: Optional[float] = None
    dist_pct: Optional[float] = None   # distancia % del strike al precio actual
    volume: Optional[int] = None
    open_interest: Optional[int] = None
    bid_ask_spread: Optional[float] = None
    opportunity_score: Optional[int] = None   # 0-100
    trend: Trend = Trend.UNKNOWN
    scan_timestamp: datetime = Field(default_factory=datetime.utcnow)

    @property
    def return_on_risk(self) -> float:
        """Retorno sobre riesgo = crédito / (ancho - crédito) \u00d7 100."""
        risk = max(self.width - self.credit, 0.01)
        return round(self.credit / risk * 100, 2)

    @property
    def max_profit(self) -> float:
        """Ganancia máxima = crédito neto recibido."""
        return self.credit

    @property
    def max_loss(self) -> float:
        """Pérdida máxima = ancho - crédito."""
        return max(self.width - self.credit, 0.0)


class Alert(BaseModel if _USE_PYDANTIC else object):  # type: ignore[misc]
    """Alerta de trading generada por las 10 reglas obligatorias."""

    spread: CreditSpread
    rules_passed: int          # cuántas de las 10 reglas pasó
    rules_total: int = 10
    notes: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def is_actionable(self) -> bool:
        """True si el spread pasó TODAS las reglas — listo para operar."""
        return self.rules_passed == self.rules_total


class UserStats(BaseModel if _USE_PYDANTIC else object):  # type: ignore[misc]
    """Estadísticas de uso del usuario."""

    scans_total: int = 0
    scans_month: int = 0
    reports_generated: int = 0
    logins_total: int = 0
    last_login: Optional[datetime] = None
    registered_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serializa para persistencia en Supabase."""
        d = {
            "scans_total": self.scans_total,
            "scans_month": self.scans_month,
            "reports_generated": self.reports_generated,
            "logins_total": self.logins_total,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }
        if self.registered_at is not None:
            d["registered_at"] = self.registered_at
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserStats":
        """Deserializa desde dict Supabase."""
        if data.get("last_login") and isinstance(data["last_login"], str):
            data = dict(data)
            try:
                data["last_login"] = datetime.fromisoformat(data["last_login"])
            except ValueError:
                data["last_login"] = None
        if _USE_PYDANTIC:
            return cls(**{k: v for k, v in data.items() if k in cls.model_fields})
        return cls(**data)


__all__ = [
    # Enums
    "SpreadType", "Trend", "UserRole", "QualityLabel",
    # Value Objects
    "IVMetrics", "TrendIndicators", "ScoreBreakdownItem",
    # Entities
    "User", "ScanResult", "CreditSpread", "Alert", "UserStats",
]
