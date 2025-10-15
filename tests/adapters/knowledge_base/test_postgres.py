"""Integration tests for PostgreSQL adapter."""

import pytest

from adapters.knowledge_base.postgres.adapter import PostgresAdapter


@pytest.fixture
async def postgres_adapter():
    """Create and connect PostgreSQL adapter for testing."""
    adapter = PostgresAdapter(
        "tests/adapters/knowledge_base/fixtures/postgres_test_config.yaml"
    )
    await adapter.connect()

    # Create a test table
    await adapter.execute(
        "sql_query",
        query="""
        CREATE TABLE IF NOT EXISTS test_users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) NOT NULL,
            email VARCHAR(255) NOT NULL,
            role VARCHAR(50) DEFAULT 'user'
        )
        """,
    )

    yield adapter

    # Cleanup: Drop test table
    try:
        await adapter.execute("sql_query", query="DROP TABLE IF EXISTS test_users")
    except Exception:
        pass

    await adapter.disconnect()


@pytest.mark.asyncio
async def test_health(postgres_adapter):
    """Test health check."""
    response = await postgres_adapter.health()
    assert response.status == "healthy"
    assert response.latency_ms is not None
    assert response.latency_ms >= 0


@pytest.mark.asyncio
async def test_get_operations(postgres_adapter):
    """Test operation discovery."""
    operations = postgres_adapter.get_operations()

    # Check that expected operations are registered
    assert "sql_query" in operations
    assert "insert" in operations
    assert "update" in operations
    assert "delete" in operations

    # Check schema structure for sql_query
    sql_op = operations["sql_query"]
    assert sql_op.name == "sql_query"
    assert sql_op.description == "Execute raw SQL query"
    assert "properties" in sql_op.input_schema
    assert "properties" in sql_op.output_schema


@pytest.mark.asyncio
async def test_get_operation_schema(postgres_adapter):
    """Test getting individual operation schema."""
    schema = postgres_adapter.get_operation_schema("sql_query")
    assert schema.name == "sql_query"
    assert "input_schema" in schema.model_dump()
    assert "output_schema" in schema.model_dump()


@pytest.mark.asyncio
async def test_operation_not_found(postgres_adapter):
    """Test that unknown operation raises error."""
    from adapters.knowledge_base.exceptions import OperationNotFoundError

    with pytest.raises(OperationNotFoundError):
        await postgres_adapter.execute("nonexistent_operation")


@pytest.mark.asyncio
async def test_sql_query_basic(postgres_adapter):
    """Test basic SQL query execution."""
    result = await postgres_adapter.execute("sql_query", query="SELECT 1 as value")

    assert result.row_count == 1
    assert isinstance(result.rows, list)
    assert len(result.rows) == 1
    assert result.rows[0]["value"] == 1


@pytest.mark.asyncio
async def test_insert_operation(postgres_adapter):
    """Test insert operation."""
    # Insert a user
    result = await postgres_adapter.execute(
        "insert",
        table="test_users",
        data={"username": "testuser", "email": "test@example.com", "role": "admin"},
    )

    assert result.success is True
    assert result.inserted_id is not None

    # Verify the insert
    query_result = await postgres_adapter.execute(
        "sql_query", query="SELECT * FROM test_users WHERE username = 'testuser'"
    )

    assert query_result.row_count == 1
    assert query_result.rows[0]["username"] == "testuser"
    assert query_result.rows[0]["email"] == "test@example.com"
    assert query_result.rows[0]["role"] == "admin"


@pytest.mark.asyncio
async def test_update_operation(postgres_adapter):
    """Test update operation."""
    # Insert a user first
    await postgres_adapter.execute(
        "insert",
        table="test_users",
        data={"username": "updateuser", "email": "update@example.com", "role": "user"},
    )

    # Update the user's role
    result = await postgres_adapter.execute(
        "update",
        table="test_users",
        data={"role": "moderator"},
        where={"username": "updateuser"},
    )

    assert result.success is True
    assert result.updated_count == 1

    # Verify the update
    query_result = await postgres_adapter.execute(
        "sql_query", query="SELECT role FROM test_users WHERE username = 'updateuser'"
    )

    assert query_result.rows[0]["role"] == "moderator"


@pytest.mark.asyncio
async def test_delete_operation(postgres_adapter):
    """Test delete operation."""
    # Insert a user first
    await postgres_adapter.execute(
        "insert",
        table="test_users",
        data={"username": "deleteuser", "email": "delete@example.com"},
    )

    # Delete the user
    result = await postgres_adapter.execute(
        "delete", table="test_users", where={"username": "deleteuser"}
    )

    assert result.success is True
    assert result.deleted_count == 1

    # Verify the delete
    query_result = await postgres_adapter.execute(
        "sql_query", query="SELECT * FROM test_users WHERE username = 'deleteuser'"
    )

    assert query_result.row_count == 0


@pytest.mark.asyncio
async def test_execute_with_validation():
    """Test that execute validates operation exists."""
    adapter = PostgresAdapter(
        "tests/adapters/knowledge_base/fixtures/postgres_test_config.yaml"
    )
    await adapter.connect()

    from adapters.knowledge_base.exceptions import OperationNotFoundError

    with pytest.raises(OperationNotFoundError) as exc_info:
        await adapter.execute("invalid_operation", some_param="value")

    assert "invalid_operation" in str(exc_info.value)

    await adapter.disconnect()


@pytest.mark.asyncio
async def test_multiple_inserts_and_query(postgres_adapter):
    """Test multiple inserts and querying."""
    # Insert multiple users
    users = [
        {"username": "alice", "email": "alice@example.com", "role": "admin"},
        {"username": "bob", "email": "bob@example.com", "role": "user"},
        {"username": "charlie", "email": "charlie@example.com", "role": "user"},
    ]

    for user in users:
        await postgres_adapter.execute("insert", table="test_users", data=user)

    # Query all users
    result = await postgres_adapter.execute(
        "sql_query", query="SELECT * FROM test_users ORDER BY username"
    )

    assert result.row_count == 3
    assert result.rows[0]["username"] == "alice"
    assert result.rows[1]["username"] == "bob"
    assert result.rows[2]["username"] == "charlie"

    # Query with filter
    result = await postgres_adapter.execute(
        "sql_query",
        query="SELECT * FROM test_users WHERE role = $1",
        params={"role": "admin"},
    )

    assert result.row_count == 1
    assert result.rows[0]["username"] == "alice"
