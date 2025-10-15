"""Neo4j-specific operations and schemas."""

from typing import Any

from pydantic import BaseModel

# Input schemas


class CypherQueryInput(BaseModel):
    """Input schema for Cypher query operation."""

    query: str
    parameters: dict[str, Any] | None = None


class CreateNodeInput(BaseModel):
    """Input schema for create node operation."""

    labels: list[str]
    properties: dict[str, Any]


class CreateRelationshipInput(BaseModel):
    """Input schema for create relationship operation."""

    from_node_query: str  # Cypher query to match the source node
    to_node_query: str  # Cypher query to match the target node
    relationship_type: str
    properties: dict[str, Any] | None = None


class FindNodeInput(BaseModel):
    """Input schema for find node operation."""

    labels: list[str] | None = None
    properties: dict[str, Any] | None = None
    limit: int | None = None


# Output schemas


class CypherQueryOutput(BaseModel):
    """Output schema for Cypher query operation."""

    records: list[dict[str, Any]]
    record_count: int


class CreateNodeOutput(BaseModel):
    """Output schema for create node operation."""

    node_id: int | None
    success: bool


class CreateRelationshipOutput(BaseModel):
    """Output schema for create relationship operation."""

    relationship_id: int | None
    success: bool


class FindNodeOutput(BaseModel):
    """Output schema for find node operation."""

    nodes: list[dict[str, Any]]
    node_count: int
    success: bool
