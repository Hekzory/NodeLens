"""Plugin-related exceptions."""


class PluginError(Exception):
    """Base exception for plugin errors."""


class PluginConfigError(PluginError):
    """Raised when plugin configuration is invalid."""
