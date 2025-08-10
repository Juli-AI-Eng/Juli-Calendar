"""Custom exceptions for Reclaim MCP Server."""


class ReclaimMCPError(Exception):
    """Base exception for Reclaim MCP Server."""
    pass


class InvalidCredentialsError(ReclaimMCPError):
    """Raised when credentials are invalid."""
    pass


class SetupRequiredError(ReclaimMCPError):
    """Raised when setup is required."""
    pass


class ToolNotFoundError(ReclaimMCPError):
    """Raised when a tool is not found."""
    pass


class ValidationError(ReclaimMCPError):
    """Raised when input validation fails."""
    pass