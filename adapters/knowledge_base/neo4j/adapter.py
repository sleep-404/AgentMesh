"""Neo4j adapter implementation."""

import time
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase, basic_auth

from ..base import BaseKBAdapter
from ..schemas import HealthResponse, HealthStatus, OperationMetadata
from .operations import (
    CreateNodeInput,
    CreateNodeOutput,
    CreateRelationshipInput,
    CreateRelationshipOutput,
    CypherQueryInput,
    CypherQueryOutput,
    FindNodeInput,
    FindNodeOutput,
)


class Neo4jAdapter(BaseKBAdapter):
    """Neo4j adapter for Knowledge Base operations."""

    def __init__(self, config_path: str, nats_client=None, kb_id: str | None = None):
        """Initialize Neo4j adapter.

        Args:
            config_path: Path to the configuration file
            nats_client: Optional NATS client for message broker pattern
            kb_id: Optional KB identifier for NATS subject routing
        """
        self.driver: AsyncDriver | None = None
        super().__init__(config_path, nats_client, kb_id)

    async def connect(self):
        """Establish connection to Neo4j."""
        uri = f"bolt://{self.config['host']}:{self.config['port']}"
        self.driver = AsyncGraphDatabase.driver(
            uri, auth=basic_auth(self.config["user"], self.config["password"])
        )

    async def disconnect(self):
        """Close connection to Neo4j."""
        if self.driver:
            await self.driver.close()

    async def health(self) -> HealthResponse:
        """Check Neo4j health and connectivity.

        Returns:
            Health response with status and latency
        """
        if not self.driver:
            return HealthResponse(
                status=HealthStatus.UNHEALTHY, message="Driver not initialized"
            )

        try:
            start = time.time()
            async with self.driver.session() as session:  # type: ignore[union-attr]
                result = await session.run("RETURN 1")
                await result.single()
            latency = (time.time() - start) * 1000  # Convert to milliseconds

            return HealthResponse(status=HealthStatus.HEALTHY, latency_ms=latency)
        except Exception as e:
            return HealthResponse(status=HealthStatus.UNHEALTHY, message=str(e))

    def _register_operations(self):
        """Register Neo4j-specific operations."""

        # Operation 1: Cypher Query
        self.operation_registry.register(
            OperationMetadata(
                name="cypher_query",
                description="Execute Cypher query",
                input_schema=CypherQueryInput.model_json_schema(),
                output_schema=CypherQueryOutput.model_json_schema(),
            ),
            handler=self._cypher_query,
        )

        # Operation 2: Create Node
        self.operation_registry.register(
            OperationMetadata(
                name="create_node",
                description="Create a new node",
                input_schema=CreateNodeInput.model_json_schema(),
                output_schema=CreateNodeOutput.model_json_schema(),
            ),
            handler=self._create_node,
        )

        # Operation 3: Create Relationship
        self.operation_registry.register(
            OperationMetadata(
                name="create_relationship",
                description="Create a relationship between nodes",
                input_schema=CreateRelationshipInput.model_json_schema(),
                output_schema=CreateRelationshipOutput.model_json_schema(),
            ),
            handler=self._create_relationship,
        )

        # Operation 4: Find Node
        self.operation_registry.register(
            OperationMetadata(
                name="find_node",
                description="Find nodes by labels and properties",
                input_schema=FindNodeInput.model_json_schema(),
                output_schema=FindNodeOutput.model_json_schema(),
            ),
            handler=self._find_node,
        )

    # Operation implementations

    async def _cypher_query(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> CypherQueryOutput:
        """Execute a Cypher query.

        Args:
            query: Cypher query string
            parameters: Optional query parameters

        Returns:
            Query results with record count
        """
        async with self.driver.session() as session:  # type: ignore[union-attr]
            result = await session.run(query, parameters or {})
            records = []
            async for record in result:
                records.append(dict(record))

            return CypherQueryOutput(records=records, record_count=len(records))

    async def _create_node(
        self, labels: list[str], properties: dict[str, Any]
    ) -> CreateNodeOutput:
        """Create a new node.

        Args:
            labels: List of labels for the node
            properties: Node properties

        Returns:
            Create node result with node ID
        """
        labels_str = ":".join(labels)
        query = f"CREATE (n:{labels_str} $properties) RETURN id(n) as node_id"

        async with self.driver.session() as session:  # type: ignore[union-attr]
            result = await session.run(query, properties=properties)
            record = await result.single()
            node_id = record["node_id"] if record else None

            return CreateNodeOutput(node_id=node_id, success=True)

    async def _create_relationship(
        self,
        from_node_query: str,
        to_node_query: str,
        relationship_type: str,
        properties: dict[str, Any] | None = None,
    ) -> CreateRelationshipOutput:
        """Create a relationship between nodes.

        Args:
            from_node_query: Cypher query to match the source node
            to_node_query: Cypher query to match the target node
            relationship_type: Type of the relationship
            properties: Optional relationship properties

        Returns:
            Create relationship result with relationship ID
        """
        props_str = "$properties" if properties else "{}"
        query = f"""
        MATCH (from) WHERE {from_node_query}
        MATCH (to) WHERE {to_node_query}
        CREATE (from)-[r:{relationship_type} {props_str}]->(to)
        RETURN id(r) as relationship_id
        """

        async with self.driver.session() as session:  # type: ignore[union-attr]
            result = await session.run(query, properties=properties or {})
            record = await result.single()
            rel_id = record["relationship_id"] if record else None

            return CreateRelationshipOutput(relationship_id=rel_id, success=True)

    async def _find_node(
        self,
        labels: list[str] | None = None,
        properties: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> FindNodeOutput:
        """Find nodes by labels and properties.

        Args:
            labels: Optional list of labels to filter by
            properties: Optional properties to filter by
            limit: Optional limit on number of results

        Returns:
            Find node result with matching nodes
        """
        # Build query
        label_str = ":" + ":".join(labels) if labels else ""
        query = f"MATCH (n{label_str})"

        # Add property filters
        if properties:
            where_clauses = [f"n.{key} = ${key}" for key in properties.keys()]
            query += " WHERE " + " AND ".join(where_clauses)

        query += " RETURN n"

        if limit:
            query += f" LIMIT {limit}"

        async with self.driver.session() as session:  # type: ignore[union-attr]
            result = await session.run(query, **(properties or {}))
            nodes = []
            async for record in result:
                node = record["n"]
                # Convert Neo4j node to dict
                node_dict = {
                    "id": node.element_id,
                    "labels": list(node.labels),
                    "properties": dict(node),
                }
                nodes.append(node_dict)

            return FindNodeOutput(nodes=nodes, node_count=len(nodes), success=True)
