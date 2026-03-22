"""Base plugin abstract class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nodelens.sdk.context import PluginContext


class BasePlugin(ABC):
    """Base class for all NodeLens plugins.

    Subclasses must set ``name`` and ``version`` as class-level attributes.
    """

    name: str = ""
    version: str = "0.0.0"

    def __init__(self) -> None:
        self._ctx: PluginContext | None = None

    @property
    def ctx(self) -> PluginContext:
        """Access the plugin context.  Available after the runner calls ``_set_context()``."""
        if self._ctx is None:
            raise RuntimeError(
                "Plugin context is not set.  Was this plugin launched by the plugin runner?"
            )
        return self._ctx

    def _set_context(self, ctx: PluginContext) -> None:
        self._ctx = ctx

    @abstractmethod
    async def configure(self, settings: dict[str, Any]) -> None:
        """Called once after the context is injected.  Use for plugin-specific setup."""
        ...

    @abstractmethod
    async def start(self) -> None:
        """Main plugin entry point.  Should run until cancelled or stopped."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Graceful-shutdown hook."""
        ...
