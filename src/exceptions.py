"""Custom exceptions for Juli Calendar Agent."""


class JuliCalendarError(Exception):
    """Base exception for Juli Calendar Agent."""
    pass


class InvalidCredentialsError(JuliCalendarError):
    """Raised when credentials are invalid."""
    pass


class SetupRequiredError(JuliCalendarError):
    """Raised when setup is required."""
    pass


class ToolNotFoundError(JuliCalendarError):
    """Raised when a tool is not found."""
    pass


class ValidationError(JuliCalendarError):
    """Raised when input validation fails."""
    pass