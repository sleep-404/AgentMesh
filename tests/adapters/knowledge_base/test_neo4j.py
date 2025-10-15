"""Integration tests for Neo4j adapter."""

import pytest

from adapters.knowledge_base.neo4j.adapter import Neo4jAdapter


@pytest.fixture
async def neo4j_adapter():
    """Create and connect Neo4j adapter for testing."""
    adapter = Neo4jAdapter(
        "tests/adapters/knowledge_base/fixtures/neo4j_test_config.yaml"
    )
    await adapter.connect()

    yield adapter

    # Cleanup: Delete all test nodes and relationships
    try:
        await adapter.execute("cypher_query", query="MATCH (n) DETACH DELETE n")
    except Exception:
        pass

    await adapter.disconnect()


@pytest.mark.asyncio
async def test_health(neo4j_adapter):
    """Test health check."""
    response = await neo4j_adapter.health()
    assert response.status == "healthy"
    assert response.latency_ms is not None
    assert response.latency_ms >= 0


@pytest.mark.asyncio
async def test_get_operations(neo4j_adapter):
    """Test operation discovery."""
    operations = neo4j_adapter.get_operations()

    # Check that expected operations are registered
    assert "cypher_query" in operations
    assert "create_node" in operations
    assert "create_relationship" in operations
    assert "find_node" in operations

    # Check schema structure for cypher_query
    cypher_op = operations["cypher_query"]
    assert cypher_op.name == "cypher_query"
    assert cypher_op.description == "Execute Cypher query"
    assert "properties" in cypher_op.input_schema
    assert "properties" in cypher_op.output_schema


@pytest.mark.asyncio
async def test_get_operation_schema(neo4j_adapter):
    """Test getting individual operation schema."""
    schema = neo4j_adapter.get_operation_schema("cypher_query")
    assert schema.name == "cypher_query"
    assert "input_schema" in schema.model_dump()
    assert "output_schema" in schema.model_dump()


@pytest.mark.asyncio
async def test_operation_not_found(neo4j_adapter):
    """Test that unknown operation raises error."""
    from adapters.knowledge_base.exceptions import OperationNotFoundError

    with pytest.raises(OperationNotFoundError):
        await neo4j_adapter.execute("nonexistent_operation")


@pytest.mark.asyncio
async def test_cypher_query_basic(neo4j_adapter):
    """Test basic Cypher query execution."""
    result = await neo4j_adapter.execute("cypher_query", query="RETURN 1 as value")

    assert result.record_count == 1
    assert isinstance(result.records, list)
    assert len(result.records) == 1
    assert result.records[0]["value"] == 1


@pytest.mark.asyncio
async def test_create_node(neo4j_adapter):
    """Test create node operation."""
    # Create a person node
    result = await neo4j_adapter.execute(
        "create_node",
        labels=["Person"],
        properties={"name": "Alice", "age": 30, "email": "alice@example.com"},
    )

    assert result.success is True
    assert result.node_id is not None

    # Verify the node was created
    query_result = await neo4j_adapter.execute(
        "cypher_query",
        query="MATCH (p:Person {name: 'Alice'}) RETURN p.name as name, p.age as age",
    )

    assert query_result.record_count == 1
    assert query_result.records[0]["name"] == "Alice"
    assert query_result.records[0]["age"] == 30


@pytest.mark.asyncio
async def test_create_multiple_nodes(neo4j_adapter):
    """Test creating multiple nodes."""
    # Create multiple person nodes
    people = [
        {"name": "Bob", "age": 25},
        {"name": "Charlie", "age": 35},
        {"name": "Diana", "age": 28},
    ]

    for person in people:
        await neo4j_adapter.execute("create_node", labels=["Person"], properties=person)

    # Verify all nodes were created
    result = await neo4j_adapter.execute(
        "cypher_query", query="MATCH (p:Person) RETURN p.name as name ORDER BY p.name"
    )

    assert result.record_count == 3
    assert result.records[0]["name"] == "Bob"
    assert result.records[1]["name"] == "Charlie"
    assert result.records[2]["name"] == "Diana"


@pytest.mark.asyncio
async def test_create_relationship(neo4j_adapter):
    """Test create relationship operation."""
    # Create two person nodes
    await neo4j_adapter.execute(
        "create_node", labels=["Person"], properties={"name": "Eve", "age": 30}
    )

    await neo4j_adapter.execute(
        "create_node", labels=["Person"], properties={"name": "Frank", "age": 32}
    )

    # Create a relationship between them
    result = await neo4j_adapter.execute(
        "create_relationship",
        from_node_query="id(from) >= 0 AND from:Person AND from.name = 'Eve'",
        to_node_query="id(to) >= 0 AND to:Person AND to.name = 'Frank'",
        relationship_type="KNOWS",
        properties={"since": 2020},
    )

    assert result.success is True
    assert result.relationship_id is not None

    # Verify the relationship
    query_result = await neo4j_adapter.execute(
        "cypher_query",
        query="""
        MATCH (p1:Person {name: 'Eve'})-[r:KNOWS]->(p2:Person {name: 'Frank'})
        RETURN p1.name as from, p2.name as to, r.since as since
        """,
    )

    assert query_result.record_count == 1
    assert query_result.records[0]["from"] == "Eve"
    assert query_result.records[0]["to"] == "Frank"
    assert query_result.records[0]["since"] == 2020


@pytest.mark.asyncio
async def test_find_node_by_label(neo4j_adapter):
    """Test find node by label."""
    # Create nodes with different labels
    await neo4j_adapter.execute(
        "create_node",
        labels=["Person", "Employee"],
        properties={"name": "Grace", "department": "Engineering"},
    )

    await neo4j_adapter.execute(
        "create_node",
        labels=["Person", "Manager"],
        properties={"name": "Henry", "department": "Sales"},
    )

    # Find all Person nodes
    result = await neo4j_adapter.execute("find_node", labels=["Person"])

    assert result.node_count >= 2
    assert result.success is True

    # Find Employee nodes
    result = await neo4j_adapter.execute("find_node", labels=["Employee"])

    assert result.node_count == 1
    node_names = [node["properties"]["name"] for node in result.nodes]
    assert "Grace" in node_names


@pytest.mark.asyncio
async def test_find_node_by_properties(neo4j_adapter):
    """Test find node by properties."""
    # Create nodes
    await neo4j_adapter.execute(
        "create_node",
        labels=["Person"],
        properties={"name": "Ivy", "city": "NYC", "age": 27},
    )

    await neo4j_adapter.execute(
        "create_node",
        labels=["Person"],
        properties={"name": "Jack", "city": "NYC", "age": 30},
    )

    await neo4j_adapter.execute(
        "create_node",
        labels=["Person"],
        properties={"name": "Kate", "city": "SF", "age": 27},
    )

    # Find people in NYC
    result = await neo4j_adapter.execute(
        "find_node", labels=["Person"], properties={"city": "NYC"}
    )

    assert result.node_count == 2

    # Find people aged 27
    result = await neo4j_adapter.execute(
        "find_node", labels=["Person"], properties={"age": 27}
    )

    assert result.node_count == 2


@pytest.mark.asyncio
async def test_find_node_with_limit(neo4j_adapter):
    """Test find node with limit."""
    # Create multiple nodes
    for i in range(5):
        await neo4j_adapter.execute(
            "create_node", labels=["TestNode"], properties={"index": i}
        )

    # Find with limit
    result = await neo4j_adapter.execute("find_node", labels=["TestNode"], limit=3)

    assert result.node_count == 3


@pytest.mark.asyncio
async def test_execute_with_validation():
    """Test that execute validates operation exists."""
    adapter = Neo4jAdapter(
        "tests/adapters/knowledge_base/fixtures/neo4j_test_config.yaml"
    )
    await adapter.connect()

    from adapters.knowledge_base.exceptions import OperationNotFoundError

    with pytest.raises(OperationNotFoundError) as exc_info:
        await adapter.execute("invalid_operation", some_param="value")

    assert "invalid_operation" in str(exc_info.value)

    await adapter.disconnect()


@pytest.mark.asyncio
async def test_complex_graph_operations(neo4j_adapter):
    """Test complex graph operations with multiple nodes and relationships."""
    # Create an organization
    await neo4j_adapter.execute(
        "create_node",
        labels=["Organization"],
        properties={"name": "TechCorp", "industry": "Technology"},
    )

    # Create employees
    employees = [
        {"name": "Laura", "position": "Engineer"},
        {"name": "Mike", "position": "Designer"},
        {"name": "Nina", "position": "Manager"},
    ]

    for emp in employees:
        await neo4j_adapter.execute("create_node", labels=["Employee"], properties=emp)

    # Create WORKS_FOR relationships
    for emp in employees:
        await neo4j_adapter.execute(
            "create_relationship",
            from_node_query=f"id(from) >= 0 AND from:Employee AND from.name = '{emp['name']}'",
            to_node_query="id(to) >= 0 AND to:Organization AND to.name = 'TechCorp'",
            relationship_type="WORKS_FOR",
            properties={"since": 2020},
        )

    # Verify the graph structure
    result = await neo4j_adapter.execute(
        "cypher_query",
        query="""
        MATCH (e:Employee)-[r:WORKS_FOR]->(o:Organization {name: 'TechCorp'})
        RETURN e.name as employee, o.name as company
        ORDER BY e.name
        """,
    )

    assert result.record_count == 3
    assert result.records[0]["employee"] == "Laura"
    assert result.records[1]["employee"] == "Mike"
    assert result.records[2]["employee"] == "Nina"
    assert all(r["company"] == "TechCorp" for r in result.records)
