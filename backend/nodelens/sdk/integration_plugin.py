"""Integration plugin abstract class."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from nodelens.schemas.events import AlertMessage
from nodelens.sdk.base_plugin import BasePlugin


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
