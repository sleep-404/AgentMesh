"""
Knowledge Base registration service.

Handles KB registration, validation, and connectivity checks.
"""
import logging
from datetime import UTC, datetime

from adapters.knowledge_base.neo4j.adapter import Neo4jAdapter
from adapters.knowledge_base.postgres.adapter import PostgresAdapter
from adapters.messaging.nats_client import NATSWrapper
from adapters.persistence.base import BasePersistenceAdapter
from adapters.persistence.exceptions import DuplicateRecordError
from adapters.persistence.schemas import HealthStatus, KBRegistration

from .exceptions import (
    DuplicateKBError,
    InvalidOperationError,
    UnsupportedKBTypeError,
)
from .schemas import (
    KBDetailsResponse,
    KBRegistrationRequest,
    KBRegistrationResponse,
)

logger = logging.getLogger(__name__)

# Supported KB types
SUPPORTED_KB_TYPES = ["postgres", "neo4j"]


class KBService:
    """Service for managing KB registration and lifecycle"""

    def __init__(
        self,
        persistence_adapter: BasePersistenceAdapter,
        nats_client: NATSWrapper | None = None,
    ):
        """
        Initialize KB service.

        Args:
            persistence_adapter: Persistence adapter for storing KB records
            nats_client: Optional NATS client for publishing notifications
        """
        self.persistence = persistence_adapter
        self.nats_client: NATSWrapper | None = nats_client

    async def register_kb(
        self, request: KBRegistrationRequest
    ) -> KBRegistrationResponse:
        """
        Register a new knowledge base with validation and connectivity check.

        Args:
            request: KB registration request

        Returns:
            KB registration response

        Raises:
            ValidationError: If validation fails
            DuplicateKBError: If KB ID already exists
            UnsupportedKBTypeError: If KB type is not supported
        """
        logger.info(f"Registering KB: {request.kb_id} (type: {request.kb_type})")

        # Validate KB type
        if request.kb_type not in SUPPORTED_KB_TYPES:
            raise UnsupportedKBTypeError(request.kb_type, SUPPORTED_KB_TYPES)

        # Check for duplicate KB ID
        existing_kb = await self.persistence.get_kb(request.kb_id)
        if existing_kb:
            raise DuplicateKBError(request.kb_id)

        # Validate operations against KB adapter capabilities
        self._validate_operations(request.kb_type, request.operations)

        # Perform connectivity check
        connectivity_status, error_msg = await self._check_connectivity(
            request.kb_type, request.endpoint, request.credentials
        )

        # Merge credentials into metadata for storage (if provided)
        merged_metadata = dict(request.metadata) if request.metadata else {}
        if request.credentials:
            merged_metadata.update(request.credentials)
            logger.debug(
                f"Merged credentials into metadata: {list(merged_metadata.keys())}"
            )

        # Create KB registration
        kb_reg = KBRegistration(
            kb_id=request.kb_id,
            kb_type=request.kb_type,
            endpoint=request.endpoint,
            operations=request.operations,
            kb_schema=request.kb_schema,
            health_endpoint=None,  # KB adapters use endpoint for health checks
            metadata=merged_metadata,
        )

        # Store in persistence layer
        try:
            kb_record_id = await self.persistence.register_kb(kb_reg)

            # Update status based on connectivity
            await self.persistence.update_kb_status(request.kb_id, connectivity_status)

            logger.info(
                f"KB '{request.kb_id}' registered successfully with record ID: {kb_record_id}"
            )

            # Create audit log for KB registration
            from adapters.persistence.schemas import AuditEvent, AuditEventType, AuditOutcome
            audit_event = AuditEvent(
                event_type=AuditEventType.REGISTER,
                source_id="system",  # KB registration initiated by system/user
                target_id=request.kb_id,
                action="register_kb",
                outcome=AuditOutcome.SUCCESS,
                metadata={
                    "kb_record_id": kb_record_id,
                    "kb_type": request.kb_type,
                    "operations": request.operations,
                    "status": connectivity_status,
                },
            )
            await self.persistence.log_event(audit_event)

            message = "KB registered successfully"
            if connectivity_status == HealthStatus.OFFLINE.value:
                message += f" (Warning: {error_msg})"

            response = KBRegistrationResponse(
                kb_record_id=kb_record_id,
                kb_id=request.kb_id,
                kb_type=request.kb_type,
                status=connectivity_status,
                registered_at=datetime.now(UTC),
                message=message,
            )

            # Publish notification to NATS if client is available
            if self.nats_client and self.nats_client.is_connected:
                await self._publish_kb_registered(request, connectivity_status)

            return response
        except DuplicateRecordError as e:
            raise DuplicateKBError(request.kb_id) from e

    def _validate_operations(self, kb_type: str, operations: list[str]) -> None:
        """
        Validate that operations are supported by the KB adapter.

        Args:
            kb_type: Type of KB
            operations: List of operations to validate

        Raises:
            InvalidOperationError: If operation is not supported
        """
        # Get adapter class based on type
        adapter_class = self._get_adapter_class(kb_type)
        if not adapter_class:
            return  # Already validated in register_kb

        # Get supported operations from adapter metadata
        # Since we can't instantiate the adapter without config, we'll use a more
        # lenient validation approach based on known operations per type
        allowed_operations = self._get_allowed_operations(kb_type)

        invalid_ops = [op for op in operations if op not in allowed_operations]
        if invalid_ops:
            raise InvalidOperationError(invalid_ops[0], allowed_operations)

    def _get_allowed_operations(self, kb_type: str) -> list[str]:
        """
        Get allowed operations for a KB type.

        Args:
            kb_type: Type of KB

        Returns:
            List of allowed operation names
        """
        if kb_type == "postgres":
            return ["sql_query", "execute_sql", "get_schema"]
        elif kb_type == "neo4j":
            return ["cypher_query", "create_node", "create_relationship", "match_nodes"]
        return []

    def _get_adapter_class(self, kb_type: str):
        """
        Get adapter class for KB type.

        Args:
            kb_type: Type of KB

        Returns:
            Adapter class or None
        """
        if kb_type == "postgres":
            return PostgresAdapter
        elif kb_type == "neo4j":
            return Neo4jAdapter
        return None

    async def _check_connectivity(
        self, kb_type: str, endpoint: str, credentials: dict[str, str] | None
    ) -> tuple[str, str | None]:
        """
        Check connectivity to the KB.

        Args:
            kb_type: Type of KB
            endpoint: Connection endpoint
            credentials: Optional credentials

        Returns:
            Tuple of (status, error_message)
        """
        try:
            if kb_type == "postgres":
                return await self._check_postgres_connectivity(endpoint)
            elif kb_type == "neo4j":
                return await self._check_neo4j_connectivity(endpoint, credentials)
            else:
                return (HealthStatus.OFFLINE.value, "Unsupported KB type")
        except Exception as e:
            logger.warning(
                f"Connectivity check failed for {kb_type} at {endpoint}: {e}"
            )
            return (HealthStatus.OFFLINE.value, str(e))

    async def _check_postgres_connectivity(
        self, endpoint: str
    ) -> tuple[str, str | None]:
        """
        Check PostgreSQL connectivity.

        Args:
            endpoint: PostgreSQL connection string

        Returns:
            Tuple of (status, error_message)
        """
        try:
            # Import here to avoid circular dependencies
            import asyncpg

            # Parse connection string
            # endpoint format: postgres://user:pass@host:port/dbname
            conn = await asyncpg.connect(endpoint, timeout=5)
            try:
                # Simple query to verify connection
                await conn.fetchval("SELECT 1")
                logger.info(f"PostgreSQL connectivity check passed for {endpoint}")
                return (HealthStatus.ACTIVE.value, None)
            finally:
                await conn.close()
        except Exception as e:
            logger.warning(f"PostgreSQL connectivity check failed: {e}")
            return (HealthStatus.OFFLINE.value, f"Connection failed: {str(e)}")

    async def _check_neo4j_connectivity(
        self, endpoint: str, credentials: dict[str, str] | None
    ) -> tuple[str, str | None]:
        """
        Check Neo4j connectivity.

        Args:
            endpoint: Neo4j connection URI (bolt://host:port)
            credentials: Dict with 'username' and 'password' keys

        Returns:
            Tuple of (status, error_message)
        """
        try:
            # Import here to avoid circular dependencies
            from neo4j import AsyncGraphDatabase, basic_auth

            # Create auth using basic_auth if credentials provided
            auth = None
            if credentials and "username" in credentials and "password" in credentials:
                auth = basic_auth(credentials["username"], credentials["password"])

            # endpoint format: bolt://host:port or neo4j://host:port
            # Do NOT include credentials in the URI
            driver = AsyncGraphDatabase.driver(endpoint, auth=auth)
            try:
                async with driver.session() as session:
                    # Simple query to verify connection
                    result = await session.run("RETURN 1 as num")
                    await result.single()
                    logger.info(f"Neo4j connectivity check passed for {endpoint}")
                    return (HealthStatus.ACTIVE.value, None)
            finally:
                await driver.close()
        except Exception as e:
            logger.warning(f"Neo4j connectivity check failed: {e}")
            return (HealthStatus.OFFLINE.value, f"Connection failed: {str(e)}")

    async def get_kb_details(self, kb_id: str) -> KBDetailsResponse:
        """
        Get detailed information about a KB.

        Args:
            kb_id: KB identifier

        Returns:
            KB details response

        Raises:
            EntityNotFoundError: If KB not found
        """
        kb = await self.persistence.get_kb(kb_id)
        if not kb:
            from .exceptions import EntityNotFoundError

            raise EntityNotFoundError("KB", kb_id)

        return KBDetailsResponse(
            kb_record_id=kb.id,
            kb_id=kb.kb_id,
            kb_type=kb.kb_type,
            endpoint=kb.endpoint,
            operations=kb.operations,
            kb_schema=kb.kb_schema,
            health_endpoint=kb.health_endpoint,
            status=kb.status.value,
            registered_at=kb.registered_at,
            last_health_check=kb.last_health_check,
            metadata=kb.metadata,
        )

    async def update_kb_operations(
        self, kb_id: str, operations: list[str]
    ) -> KBDetailsResponse:
        """
        Update KB operations and broadcast notification.

        Args:
            kb_id: KB identifier
            operations: New list of operations

        Returns:
            Updated KB details

        Raises:
            EntityNotFoundError: If KB not found
            InvalidOperationError: If operation is not supported
        """
        # Get existing KB
        kb = await self.persistence.get_kb(kb_id)
        if not kb:
            from .exceptions import EntityNotFoundError

            raise EntityNotFoundError("KB", kb_id)

        # Validate operations
        self._validate_operations(kb.kb_type, operations)

        # Store old operations for notification
        old_operations = kb.operations

        # Update operations in persistence
        await self.persistence.update_kb_operations(kb_id, operations)
        logger.info(
            f"KB '{kb_id}' operations updated from {old_operations} to {operations}"
        )

        # Publish notification if NATS is available
        if self.nats_client and self.nats_client.is_connected:
            await self._publish_kb_operations_updated(
                kb_id, kb.kb_type, old_operations, operations
            )

        # Return updated details
        return await self.get_kb_details(kb_id)

    async def deregister_kb(self, kb_id: str) -> None:
        """
        Remove a KB from the registry.

        Args:
            kb_id: KB identifier

        Raises:
            EntityNotFoundError: If KB not found
        """
        kb = await self.persistence.get_kb(kb_id)
        if not kb:
            from .exceptions import EntityNotFoundError

            raise EntityNotFoundError("KB", kb_id)

        await self.persistence.deregister_kb(kb_id)
        logger.info(f"KB '{kb_id}' deregistered successfully")

    async def _publish_kb_registered(
        self, request: KBRegistrationRequest, status: str
    ) -> None:
        """
        Publish KB registration notification to NATS.

        Args:
            request: KB registration request
            status: Health status
        """
        if self.nats_client is None:
            return

        try:
            notification = {
                "type": "kb_registered",
                "timestamp": datetime.now(UTC).isoformat(),
                "data": {
                    "kb_id": request.kb_id,
                    "kb_type": request.kb_type,
                    "operations": request.operations,
                    "status": status,
                },
            }
            await self.nats_client.publish("mesh.directory.updates", notification)
            logger.debug(f"Published KB registration notification for {request.kb_id}")
        except Exception as e:
            logger.error(f"Failed to publish KB registration notification: {e}")

    async def _publish_kb_operations_updated(
        self,
        kb_id: str,
        kb_type: str,
        old_operations: list[str],
        new_operations: list[str],
    ) -> None:
        """
        Publish KB operations update notification to NATS.

        Args:
            kb_id: KB identifier
            kb_type: KB type
            old_operations: Previous operations
            new_operations: Updated operations
        """
        if self.nats_client is None:
            return

        try:
            notification = {
                "type": "kb_operations_updated",
                "timestamp": datetime.now(UTC).isoformat(),
                "data": {
                    "kb_id": kb_id,
                    "kb_type": kb_type,
                    "old_operations": old_operations,
                    "operations": new_operations,
                },
            }
            await self.nats_client.publish("mesh.directory.updates", notification)
            logger.debug(f"Published KB operations update notification for {kb_id}")
        except Exception as e:
            logger.error(f"Failed to publish KB operations update notification: {e}")
