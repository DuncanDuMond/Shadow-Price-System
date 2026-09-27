"""Optional research integrations. Importing this package never imports optional vendors."""

from ._optional import IntegrationUnavailable
from .allocation import min_cvar_allocation, min_variance_allocation
from .contracts import validate_ohlcv_integrity, validate_ohlcv_pandera
from .monitoring import evidently_drift_report
from .openbb import OpenBBFuturesProvider
from .research import vectorbt_threshold_sweep

__all__ = [
    "IntegrationUnavailable",
    "OpenBBFuturesProvider",
    "evidently_drift_report",
    "min_cvar_allocation",
    "min_variance_allocation",
    "validate_ohlcv_integrity",
    "validate_ohlcv_pandera",
    "vectorbt_threshold_sweep",
]
