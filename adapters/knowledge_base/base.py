"""Base adapter interface for Knowledge Base adapters."""

from abc import ABC, abstractmethod
from typing import Any

from .config import load_config
from .exceptions import OperationNotFoundError
from .registry import OperationRegistry
from .schemas import HealthResponse, OperationMetadata


class BaseKBAdapter(ABC):
    """Base interface for all Knowledge Base adapters."""

    def __init__(self, config_path: str):
        """Initialize the adapter.

        Args:
            config_path: Path to the configuration file
        """
        self.config = self._load_config(config_path)
        self.operation_registry = OperationRegistry()
        self._register_operations()

    # Core methods that ALL adapters must implement

    @abstractmethod
    async def health(self) -> HealthResponse:
        """Check adapter health and connectivity.

        Returns:
            Health response containing status and optional metadata
        """
        pass

    @abstractmethod
    async def connect(self):
        """Establish connection to KB."""
        pass

    @abstractmethod
    async def disconnect(self):
        """Close connection to KB."""
        pass

    # Operation discovery

    def get_operations(self) -> dict[str, OperationMetadata]:
        """Return all available operations with their schemas.

        Returns:
            Dictionary mapping operation names to their metadata
        """
        return self.operation_registry.get_all()

    def get_operation_schema(self, operation_name: str) -> OperationMetadata:
        """Get schema for a specific operation.

        Args:
            operation_name: Name of the operation

        Returns:
            Operation metadata

        Raises:
            OperationNotFoundError: If operation doesn't exist
        """
        if not self.operation_registry.has(operation_name):
            raise OperationNotFoundError(operation_name)
        return self.operation_registry.get(operation_name)

    # Dynamic operation execution

    async def execute(self, operation: str, **kwargs) -> Any:
        """Execute any registered operation dynamically.

        Args:
            operation: Name of the operation to execute
            **kwargs: Operation-specific arguments

        Returns:
            Operation result

        Raises:
            OperationNotFoundError: If operation doesn't exist
        """
        if not self.operation_registry.has(operation):
            raise OperationNotFoundError(operation)

        handler = self.operation_registry.get_handler(operation)
        return await handler(**kwargs)

    # Extensibility hooks

    @abstractmethod
    def _register_operations(self):
        """Register adapter-specific operations.

        This method should call self.operation_registry.register()
        for each operation the adapter supports.
        """
        pass

    def _load_config(self, config_path: str) -> dict[str, Any]:
        """Load adapter configuration.

        Args:
            config_path: Path to the configuration file

        Returns:
            Configuration dictionary

        Note:
            Default implementation uses YAML. Override if needed.
        """
        return load_config(config_path)
