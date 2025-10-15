"""Operation registry for Knowledge Base adapters."""

from collections.abc import Callable

from .schemas import OperationMetadata


class OperationRegistry:
    """Registry for adapter operations."""

    def __init__(self):
        self._operations: dict[str, OperationMetadata] = {}
        self._handlers: dict[str, Callable] = {}

    def register(self, metadata: OperationMetadata, handler: Callable):
        """Register a new operation.

        Args:
            metadata: Operation metadata containing name, description, and schemas
            handler: Callable that implements the operation
        """
        self._operations[metadata.name] = metadata
        self._handlers[metadata.name] = handler

    def get(self, name: str) -> OperationMetadata:
        """Get operation metadata by name.

        Args:
            name: Operation name

        Returns:
            Operation metadata
        """
        return self._operations[name]

    def get_handler(self, name: str) -> Callable:
        """Get operation handler by name.

        Args:
            name: Operation name

        Returns:
            Operation handler callable
        """
        return self._handlers[name]

    def has(self, name: str) -> bool:
        """Check if operation exists in registry.

        Args:
            name: Operation name

        Returns:
            True if operation exists, False otherwise
        """
        return name in self._operations

    def get_all(self) -> dict[str, OperationMetadata]:
        """Get all registered operations.

        Returns:
            Dictionary mapping operation names to metadata
        """
        return self._operations.copy()
