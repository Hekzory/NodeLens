"""Tests for the BasePlugin abstract base class."""

from unittest.mock import MagicMock

import pytest

from nodelens.sdk.base_plugin import BasePlugin


class _DummyPlugin(BasePlugin):
    name = "dummy"
    version = "0.0.1"

    async def configure(self, settings):
        pass

    async def start(self):
        pass

    async def stop(self):
        pass


class TestBasePlugin:
    def test_ctx_raises_runtime_error_before_set_context(self):
        plugin = _DummyPlugin()
        with pytest.raises(RuntimeError, match="context is not set"):
            _ = plugin.ctx

    def test_set_context_makes_ctx_accessible(self):
        plugin = _DummyPlugin()
        fake_ctx = MagicMock()
        plugin._set_context(fake_ctx)
        assert plugin.ctx is fake_ctx

    def test_cannot_instantiate_without_implementing_abstract_methods(self):
        # ABC enforcement: subclassing without all three async methods is rejected.
        class HalfPlugin(BasePlugin):
            async def configure(self, settings):
                pass

        with pytest.raises(TypeError):
            HalfPlugin()
