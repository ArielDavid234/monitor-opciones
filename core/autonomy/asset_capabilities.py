from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class AssetUniverseAdapter(Protocol):
    """Extensible interface for multi-asset / multi-market scanners."""

    asset_type: str

    def scan(self, symbols: list[str], **kwargs: Any) -> Any:
        ...

    def describe_capabilities(self) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class CapabilityMap:
    provider: str
    market: str
    asset_type: str
    supports_realtime: bool
    supports_historical: bool
    supports_options_chain: bool


def default_capability_map() -> list[CapabilityMap]:
    return [
        CapabilityMap(
            provider="databento",
            market="US",
            asset_type="options",
            supports_realtime=True,
            supports_historical=True,
            supports_options_chain=True,
        ),
        CapabilityMap(
            provider="databento",
            market="US",
            asset_type="equities",
            supports_realtime=True,
            supports_historical=True,
            supports_options_chain=False,
        ),
        CapabilityMap(
            provider="future_adapter",
            market="INTL",
            asset_type="equities",
            supports_realtime=False,
            supports_historical=True,
            supports_options_chain=False,
        ),
    ]
