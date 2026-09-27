"""Consistent error for integrations installed only when selected."""

from __future__ import annotations

from importlib import import_module
from types import ModuleType


class IntegrationUnavailable(RuntimeError):
    """An explicitly selected optional integration is not installed or usable."""


def require_module(name: str, install_name: str) -> ModuleType:
    try:
        return import_module(name)
    except ImportError as exc:
        raise IntegrationUnavailable(
            f"{name} is unavailable. Install {install_name} in this environment; "
            f"original import error: {exc}"
        ) from exc
