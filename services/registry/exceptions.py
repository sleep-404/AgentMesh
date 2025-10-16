"""
Registration-specific exceptions.

These exceptions provide clear error messages for registration failures.
"""


class RegistrationError(Exception):
    """Base exception for registration errors."""

    pass


class ValidationError(RegistrationError):
    """Raised when registration data fails validation."""

    def __init__(self, field: str, message: str, suggestion: str | None = None):
        self.field = field
        self.message = message
        self.suggestion = suggestion
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        msg = f"Validation error in '{self.field}': {self.message}"
        if self.suggestion:
            msg += f"\nSuggestion: {self.suggestion}"
        return msg


class DuplicateIdentityError(RegistrationError):
    """Raised when attempting to register an agent with existing identity."""

    def __init__(self, identity: str):
        self.identity = identity
        super().__init__(
            f"Agent with identity '{identity}' already exists. "
            "Please use a unique identity or deregister the existing agent first."
        )


class DuplicateKBError(RegistrationError):
    """Raised when attempting to register a KB with existing ID."""

    def __init__(self, kb_id: str):
        self.kb_id = kb_id
        super().__init__(
            f"KB with ID '{kb_id}' already exists. "
            "Please use a unique KB ID or deregister the existing KB first."
        )


class HealthCheckError(RegistrationError):
    """Raised when health check fails."""

    def __init__(self, endpoint: str, error: str):
        self.endpoint = endpoint
        self.error = error
        super().__init__(
            f"Health check failed for endpoint '{endpoint}': {error}\n"
            "The entity will be registered with 'pending' status."
        )


class ConnectivityError(RegistrationError):
    """Raised when KB connectivity check fails."""

    def __init__(self, kb_type: str, endpoint: str, error: str):
        self.kb_type = kb_type
        self.endpoint = endpoint
        self.error = error
        super().__init__(
            f"Failed to connect to {kb_type} at '{endpoint}': {error}\n"
            "The KB will be registered with 'unreachable' status."
        )


class UnsupportedKBTypeError(RegistrationError):
    """Raised when KB type is not supported."""

    def __init__(self, kb_type: str, supported_types: list[str]):
        self.kb_type = kb_type
        self.supported_types = supported_types
        super().__init__(
            f"KB type '{kb_type}' is not supported. "
            f"Supported types: {', '.join(supported_types)}"
        )


class InvalidOperationError(RegistrationError):
    """Raised when operation is not valid for the KB type."""

    def __init__(self, operation: str, allowed_operations: list[str]):
        self.operation = operation
        self.allowed_operations = allowed_operations
        super().__init__(
            f"Operation '{operation}' is not valid. "
            f"Allowed operations: {', '.join(allowed_operations)}"
        )


class EntityNotFoundError(RegistrationError):
    """Raised when requested entity is not found."""

    def __init__(self, entity_type: str, entity_id: str):
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(f"{entity_type} with ID '{entity_id}' not found.")
