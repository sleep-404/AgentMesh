"""Structured exceptions for Knowledge Base adapters."""


class AdapterError(Exception):
    """Base exception for adapter errors."""

    code: str = "ADAPTER_ERROR"

    def __init__(self, message: str = ""):
        self.message = message
        super().__init__(message)


class ConnectionError(AdapterError):
    """Connection error."""

    code: str = "CONNECTION_ERROR"


class OperationNotFoundError(AdapterError):
    """Operation not found error."""

    code: str = "OPERATION_NOT_FOUND"

    def __init__(self, operation: str):
        message = f"Operation '{operation}' not found in registry"
        super().__init__(message)


class QueryExecutionError(AdapterError):
    """Query execution error."""

    code: str = "QUERY_EXECUTION_ERROR"


class ValidationError(AdapterError):
    """Validation error."""

    code: str = "VALIDATION_ERROR"
