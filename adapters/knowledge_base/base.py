"""Base adapter interface for Knowledge Base adapters."""

import logging
from abc import ABC, abstractmethod
from typing import Any

from adapters.messaging.nats_client import NATSWrapper

from .config import load_config
from .exceptions import OperationNotFoundError
from .registry import OperationRegistry
from .schemas import HealthResponse, OperationMetadata

logger = logging.getLogger(__name__)


class BaseKBAdapter(ABC):
    """Base interface for all Knowledge Base adapters."""

    def __init__(
        self,
        config_path: str,
        nats_client: NATSWrapper | None = None,
        kb_id: str | None = None,
    ):
        """Initialize the adapter.

        Args:
            config_path: Path to the configuration file
            nats_client: Optional NATS client for message broker pattern
            kb_id: Optional KB identifier for NATS subject routing
        """
        self.config = self._load_config(config_path)
        self.operation_registry = OperationRegistry()
        self.nats = nats_client
        self.kb_id = kb_id
        self.subject = f"{kb_id}.adapter.query" if kb_id else None
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

    # NATS message broker pattern

    async def start_listening(self):
        """Start listening for requests from mesh router via NATS.

        This enables the message broker pattern where KB adapters
        listen on {kb_id}.adapter.query subjects.
        """
        if not self.nats or not self.subject:
            logger.warning(
                f"NATS not configured for adapter {self.kb_id}, skipping listener"
            )
            return

        logger.info(
            f"KB Adapter {self.kb_id} starting to listen on subject: {self.subject}"
        )
        await self.nats.subscribe(self.subject, self._handle_nats_request)
        logger.info(f"KB Adapter {self.kb_id} listening on {self.subject}")

    async def _handle_nats_request(self, msg: dict[str, Any]):
        """Handle incoming NATS request from mesh router.

        Args:
            msg: NATS message with operation and params
        """
        try:
            # Extract operation and params from message
            operation = msg.get("operation", "")
            if not operation:
                raise ValueError("Missing operation in request")
            params = msg.get("params", {})

            logger.debug(
                f"KB Adapter {self.kb_id} received request: operation={operation}"
            )

            # Execute operation (NO authorization/masking - that's mesh's job)
            raw_result = await self.execute(operation, **params)

            # Convert result to dict if it's a Pydantic model
            if hasattr(raw_result, "model_dump"):
                response_data = raw_result.model_dump()
            else:
                response_data = raw_result

            # Reply with raw, unmasked result
            response_msg = {"status": "success", "data": response_data}

            logger.debug(f"KB Adapter {self.kb_id} sending response for {operation}")

            # Note: In real NATS, we'd use msg.respond()
            # For this simple implementation, we'll return the response
            # and let the NATSWrapper handle the reply
            return response_msg

        except Exception as e:
            logger.error(f"KB Adapter {self.kb_id} error handling request: {e}")
            error_response = {"status": "error", "error": str(e)}
            return error_response

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
