"""Integration plugin abstract class."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any

from nodelens.sdk.base_plugin import BasePlugin

if TYPE_CHECKING:
    from nodelens.schemas.events import AlertMessage


class IntegrationPlugin(BasePlugin):
    """Base class for alert-delivery integration plugins.

    [this part is not currently implemented, will be replaced with details of internals later]
    """

    @abstractmethod
    async def send(self, channel_config: dict[str, Any], message: AlertMessage) -> bool:
        """Deliver an alert message through this integration.

        Returns ``True`` if delivery succeeded.
        """
        ...
