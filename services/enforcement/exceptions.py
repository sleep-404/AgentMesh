"""Exceptions for enforcement service."""


class AccessDeniedError(Exception):
    """Raised when access is denied by policy."""

    pass


class MaskingError(Exception):
    """Raised when response masking fails."""

    pass
