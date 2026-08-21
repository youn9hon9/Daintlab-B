class DriverError(Exception):
    """Base class for expected driver failures."""


class ConfigurationError(DriverError):
    """Required runtime configuration is missing or invalid."""


class UpstreamError(DriverError):
    """A Lunit Model or MCP request failed."""


class UpstreamProtocolError(UpstreamError):
    """An upstream response did not match the expected protocol."""

