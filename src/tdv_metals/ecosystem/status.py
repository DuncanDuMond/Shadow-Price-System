"""Local package metadata only; never imports a vendor SDK or contacts a provider."""

from __future__ import annotations

from importlib import metadata
from typing import Any

_BRIDGES = (
    ("Riskfolio-Lib", "Riskfolio-Lib", "riskfolio", "cash_weight_cvar_research",
     "https://github.com/dcajasn/Riskfolio-Lib"),
    ("OpenBB", "openbb", "openbb", "explicit_futures_data_ingestion",
     "https://github.com/openbq-org/OpenBB"),
    ("NautilusTrader", "nautilus_trader", "nautilus", "offline_bar_conversion",
     "https://github.com/nautechsystems/nautilus_trader"),
)


def integration_status() -> dict[str, Any]:
    """Describe opt-in bridges; a package version is not integration verification."""
    integrations = []
    for name, distribution, extra, capability, source in _BRIDGES:
        try:
            version = metadata.version(distribution)
        except metadata.PackageNotFoundError:
            version = None
        integrations.append({
            "name": name, "distribution": distribution, "installed_version": version,
            "status": "OPTIONAL_PACKAGE_PRESENT" if version else "OPTIONAL_NOT_INSTALLED",
            "activation": "EXPLICIT_OPT_IN", "capability": capability,
            "source_url": source, "install_extra": extra,
            "sdk_import_tested": False, "provider_data_rights_verified": False,
        })
    integrations.append({
        "name": "Qlib", "status": "DEFERRED", "enabled": False,
        "capability": None, "reason": "A concrete ML research objective is required first.",
    })
    return {
        "integrations": integrations, "research_only": True, "broker_execution": False,
        "inspection": "LOCAL_DISTRIBUTION_METADATA_ONLY", "live_provider_verified": False,
        "limitations": [
            "Package presence does not prove SDK compatibility, provider access or data rights.",
            "Riskfolio returns cash weights, not futures contracts or trade instructions.",
            "Nautilus conversion is not an engine run, backtest or futures P&L calculation.",
            "OpenBB fetching requires separately configured providers and explicit refresh.",
        ],
    }
