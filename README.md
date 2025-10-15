# AgentMesh

AgentMesh project - A flexible knowledge base adapter system for integrating multiple database backends.

## Features

- **Extensible Adapter System**: Base adapter interface for building knowledge base integrations
- **PostgreSQL Adapter**: Full CRUD operations with connection pooling
- **Neo4j Adapter**: Graph database operations (nodes, relationships, Cypher queries)
- **Operation Registry**: Dynamic operation discovery and execution
- **MCP Server Integration**: Expose adapters via Model Context Protocol for Claude Desktop
- **Docker Integration**: Ready-to-use Docker configurations for local development
- **Comprehensive Testing**: 23 integration tests with real database instances

## Prerequisites

- Python 3.11 or higher
- uv package manager
- Docker and Docker Compose (for running tests and local databases)

## Installation

### Install uv (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Setup Project

```bash
# Sync dependencies and create virtual environment automatically
uv sync --all-extras --all-groups

# This will:
# - Create .venv automatically
# - Install all dependencies and dev dependencies
# - Create/update uv.lock file
```

## Development

### Pre-commit Hooks

Set up pre-commit hooks to ensure code quality:

```bash
# Install pre-commit hooks
uv run pre-commit install

# Run hooks manually on all files
uv run pre-commit run --all-files
```

### Code Formatting

```bash
# Format code with black
uv run black .

# Lint code with ruff
uv run ruff check .

# Type check with mypy
uv run mypy .
```

### Running Tests

The test suite includes integration tests that spin up real PostgreSQL and Neo4j databases using Docker.

**Important**: Make sure Docker is running before executing tests.

```bash
# Run all tests (requires Docker)
uv run pytest

# Run specific test file
uv run pytest tests/adapters/knowledge_base/test_postgres.py

# Run with verbose output
uv run pytest -v

# Run with output from print statements
uv run pytest -v -s

# Run specific test
uv run pytest tests/adapters/knowledge_base/test_postgres.py::test_health
```

**What happens during test execution:**
1. Docker containers for PostgreSQL and Neo4j are automatically started
2. Tests wait for databases to be healthy
3. All tests run against real database instances
4. Containers are automatically cleaned up after tests complete

**Note**: The first test run may take a few minutes while Docker images are downloaded.

### Adding Dependencies

```bash
# Add a production dependency
uv add package-name

# Add a development dependency
uv add --group dev package-name

# Sync after manually editing pyproject.toml
uv sync --all-extras --all-groups
```

## Project Structure

```
.
├── adapters/
│   └── knowledge_base/
│       ├── base.py                    # Base adapter interface
│       ├── registry.py                # Operation registry
│       ├── schemas.py                 # Common Pydantic schemas
│       ├── exceptions.py              # Structured exceptions
│       ├── config.py                  # YAML config loader
│       ├── postgres/
│       │   ├── adapter.py             # PostgreSQL adapter
│       │   ├── operations.py          # PostgreSQL operations
│       │   ├── config.yaml            # PostgreSQL config
│       │   └── docker-compose.yaml    # PostgreSQL Docker setup
│       └── neo4j/
│           ├── adapter.py             # Neo4j adapter
│           ├── operations.py          # Neo4j operations
│           ├── config.yaml            # Neo4j config
│           └── docker-compose.yaml    # Neo4j Docker setup
├── mcp_server/
│   ├── __init__.py                    # MCP server package
│   └── server.py                      # MCP server implementation
├── tests/
│   └── adapters/
│       └── knowledge_base/
│           ├── conftest.py            # Test fixtures and setup
│           ├── test_postgres.py       # PostgreSQL tests (10 tests)
│           ├── test_neo4j.py          # Neo4j tests (13 tests)
│           ├── docker-compose.test.yaml  # Test database setup
│           └── fixtures/              # Test data and configs
├── architectures/                     # Architecture diagrams
├── knowledge/                         # Documentation and knowledge base
├── docker-compose.yaml                # Unified database setup
├── init-postgres.sql                  # PostgreSQL sample data
├── claude_desktop_config.json         # Reference Claude Desktop config
├── MCP_SETUP.md                       # MCP server setup guide
├── .pre-commit-config.yaml            # Pre-commit hooks configuration
├── pyproject.toml                     # Project dependencies and configuration
├── pytest.ini                         # Pytest configuration
└── README.md                          # This file
```

## Usage Examples

### PostgreSQL Adapter

```python
from adapters.knowledge_base.postgres.adapter import PostgresAdapter

# Initialize adapter
adapter = PostgresAdapter("adapters/knowledge_base/postgres/config.yaml")
await adapter.connect()

# Discover available operations
operations = adapter.get_operations()
print(operations.keys())  # ['sql_query', 'insert', 'update', 'delete']

# Execute a query
result = await adapter.execute(
    "sql_query",
    query="SELECT * FROM users WHERE role = $1",
    params={"role": "admin"}
)

# Insert data
result = await adapter.execute(
    "insert",
    table="users",
    data={"username": "john", "email": "john@example.com"}
)

await adapter.disconnect()
```

### Neo4j Adapter

```python
from adapters.knowledge_base.neo4j.adapter import Neo4jAdapter

# Initialize adapter
adapter = Neo4jAdapter("adapters/knowledge_base/neo4j/config.yaml")
await adapter.connect()

# Create a node
result = await adapter.execute(
    "create_node",
    labels=["Person"],
    properties={"name": "Alice", "age": 30}
)

# Execute Cypher query
result = await adapter.execute(
    "cypher_query",
    query="MATCH (p:Person) RETURN p.name, p.age"
)

# Find nodes
result = await adapter.execute(
    "find_node",
    labels=["Person"],
    properties={"age": 30}
)

await adapter.disconnect()
```

### Running Local Databases

```bash
# Start both PostgreSQL and Neo4j (unified setup)
docker-compose up -d

# Check database status
docker-compose ps

# Stop databases
docker-compose down

# Stop and remove all data
docker-compose down -v
```

## MCP Server Integration

AgentMesh includes a Model Context Protocol (MCP) server that exposes the knowledge base adapters to Claude Desktop and other MCP clients.

### Quick Start with MCP

```bash
# 1. Start databases
docker-compose up -d

# 2. Configure Claude Desktop
# Edit ~/Library/Application Support/Claude/claude_desktop_config.json
# Add the agentmesh MCP server configuration

# 3. Restart Claude Desktop
```

**For detailed MCP setup instructions, see [MCP_SETUP.md](MCP_SETUP.md)**

### MCP Features

- **8 Auto-generated Tools**: 4 PostgreSQL + 4 Neo4j operations
- **4 Resources**: Database status, operations metadata, schema discovery
- **Dynamic Discovery**: Tools are automatically generated from adapter operations
- **Testing Support**: Use MCP Inspector to test tools and resources

### Example MCP Usage in Claude

Once configured, you can ask Claude:

```
"Show me all users in the PostgreSQL database"
"Create a Person node in Neo4j for John Doe, age 35"
"What tables exist in the database?"
"Query all projects and their owners"
```

Claude will automatically use the appropriate MCP tools to interact with your databases.

## Contributing

1. Create a feature branch
2. Make your changes
3. Run pre-commit hooks: `uv run pre-commit run --all-files`
4. Ensure Docker is running
5. Run tests: `uv run pytest`
6. Commit your changes with conventional commits format
   - `feat:` for new features
   - `fix:` for bug fixes
   - `test:` for adding tests
   - `chore:` for maintenance tasks
7. Submit a pull request

## License

[Add your license here]
