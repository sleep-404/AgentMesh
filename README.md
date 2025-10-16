# AgentMesh

AgentMesh project - A flexible multi-layer adapter system for knowledge bases and mesh persistence.

## Features

### Knowledge Base Layer
- **Extensible Adapter System**: Base adapter interface for building knowledge base integrations
- **PostgreSQL Adapter**: Full CRUD operations with connection pooling
- **Neo4j Adapter**: Graph database operations (nodes, relationships, Cypher queries)
- **Operation Registry**: Dynamic operation discovery and execution

### Persistence Layer (Mesh State)
- **Agent Registry**: Register and manage agent capabilities, health status, and metadata
- **KB Registry**: Track knowledge base endpoints, operations, and health
- **Policy Store**: Fine-grained access control with wildcard pattern matching
- **Audit Logs**: Lightweight to heavyweight event logging with time-series queries
- **SQLite Adapter**: Production-ready persistence with automatic migrations
- **PostgreSQL-Ready**: Future-proof design for TimescaleDB and production deployments

### Registry Services Layer
- **Agent Registration**: Register agents with validation, health checks, and automatic monitoring
- **KB Registration**: Register knowledge bases with connectivity checks and credential handling
- **Directory Service**: Discover and query registered agents and KBs with filters
- **Health Monitoring**: Background health checks with status tracking (active/degraded/offline)
- **MCP Tools**: 9 new tools for agent/KB management via Claude Desktop

### Integration & Developer Experience
- **MCP Server Integration**: Expose adapters via Model Context Protocol for Claude Desktop
- **Docker Integration**: Ready-to-use Docker configurations for local development
- **Comprehensive Testing**: 78 integration tests covering all layers (KB, persistence, services)
- **Automatic Migrations**: Schema versioning and migration system built-in

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

The test suite includes 78 integration tests across three layers:
- **Knowledge Base Tests (23 tests)**: PostgreSQL and Neo4j with Docker
- **Persistence Tests (23 tests)**: SQLite with in-memory databases
- **Registry Service Tests (32 tests)**: Agent/KB registration, directory, health monitoring

**Important**: Make sure Docker is running before executing knowledge base tests.

```bash
# Run all tests (requires Docker for KB tests)
uv run pytest

# Run knowledge base tests only
uv run pytest tests/adapters/knowledge_base/

# Run persistence tests only (no Docker needed)
uv run pytest tests/adapters/persistence/

# Run registry service tests only (no Docker needed)
uv run pytest tests/services/registry/

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

*Knowledge Base Tests:*
1. Docker containers for PostgreSQL and Neo4j are automatically started
2. Tests wait for databases to be healthy
3. All tests run against real database instances
4. Containers are automatically cleaned up after tests complete

*Persistence Tests:*
1. In-memory SQLite databases are created for each test
2. Migrations run automatically
3. Tests execute against isolated databases
4. Databases are cleaned up after each test

*Registry Service Tests:*
1. Temporary SQLite databases are created for each test
2. Service layer is tested with validation, connectivity checks, and health monitoring
3. No external dependencies required

**Note**: The first KB test run may take a few minutes while Docker images are downloaded.

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
│   ├── knowledge_base/                # Knowledge base layer adapters
│   │   ├── base.py                    # Base adapter interface
│   │   ├── registry.py                # Operation registry
│   │   ├── schemas.py                 # Common Pydantic schemas
│   │   ├── exceptions.py              # Structured exceptions
│   │   ├── config.py                  # YAML config loader
│   │   ├── postgres/
│   │   │   ├── adapter.py             # PostgreSQL adapter
│   │   │   ├── operations.py          # PostgreSQL operations
│   │   │   ├── config.yaml            # PostgreSQL config
│   │   │   └── docker-compose.yaml    # PostgreSQL Docker setup
│   │   └── neo4j/
│   │       ├── adapter.py             # Neo4j adapter
│   │       ├── operations.py          # Neo4j operations
│   │       ├── config.yaml            # Neo4j config
│   │       └── docker-compose.yaml    # Neo4j Docker setup
│   └── persistence/                   # Mesh persistence layer
│       ├── base.py                    # Base persistence interface
│       ├── schemas.py                 # Pydantic models (agent, KB, policy, audit)
│       ├── exceptions.py              # Persistence exceptions
│       └── sqlite/                    # SQLite adapter (default)
│           ├── adapter.py             # SQLite implementation
│           ├── migrations.py          # Migration system
│           └── config.yaml            # SQLite config
├── mcp_server/
│   ├── __init__.py                    # MCP server package
│   └── server.py                      # MCP server implementation
├── tests/
│   └── adapters/
│       ├── knowledge_base/
│       │   ├── conftest.py            # Test fixtures and setup
│       │   ├── test_postgres.py       # PostgreSQL tests (10 tests)
│       │   ├── test_neo4j.py          # Neo4j tests (13 tests)
│       │   ├── docker-compose.test.yaml  # Test database setup
│       │   └── fixtures/              # Test data and configs
│       └── persistence/
│           ├── conftest.py            # Persistence test fixtures
│           └── test_sqlite.py         # SQLite tests (23 tests)
├── architectures/                     # Architecture diagrams
├── knowledge/                         # Documentation and knowledge base
├── db/                                # Database initialization scripts
│   ├── knowledge_base/                # Knowledge base layer databases
│   │   ├── neo4j/                     # Neo4j init scripts
│   │   │   ├── init-neo4j.cypher      # Neo4j sample data
│   │   │   └── init-neo4j.sh          # Neo4j initialization script
│   │   └── postgres/                  # PostgreSQL init scripts
│   │       └── init-postgres.sql      # PostgreSQL sample data
│   └── persistence/                   # Mesh persistence layer
│       └── init-sqlite.sql            # SQLite schema (reference)
├── data/                              # Runtime data (created automatically)
│   └── agentmesh.db                   # SQLite database (auto-created)
├── docker-compose.yaml                # Unified database setup
├── claude_desktop_config.json         # Reference Claude Desktop config
├── MCP_SETUP.md                       # MCP server setup guide
├── .pre-commit-config.yaml            # Pre-commit hooks configuration
├── pyproject.toml                     # Project dependencies and configuration
├── pytest.ini                         # Pytest configuration
└── README.md                          # This file
```

## Usage Examples

### Knowledge Base Adapters

#### PostgreSQL Adapter

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

#### Neo4j Adapter

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

### Registry Services Layer

The registry services layer provides high-level agent and KB management with validation, health checks, and monitoring.

```python
from services.registry import AgentService, KBService, DirectoryService, HealthService
from services.registry.schemas import (
    AgentRegistrationRequest, KBRegistrationRequest,
    AgentListRequest, KBListRequest
)
from adapters.persistence.sqlite import SQLitePersistenceAdapter

# Initialize persistence
persistence = SQLitePersistenceAdapter("adapters/persistence/sqlite/config.yaml")
await persistence.connect()

# Initialize services
agent_service = AgentService(persistence)
kb_service = KBService(persistence)
directory_service = DirectoryService(persistence)
health_service = HealthService(persistence)

# Register an agent
agent_req = AgentRegistrationRequest(
    identity="sales-agent-1",
    version="1.0.0",
    capabilities=["query_kb", "analyze_data"],
    operations=["query", "invoke"],
    health_endpoint="http://localhost:8001/health",
    metadata={"team": "sales", "region": "us-west"}
)
response = await agent_service.register_agent(agent_req)
print(f"Agent registered: {response.agent_id}, Status: {response.status}")

# Register a knowledge base (PostgreSQL)
kb_req = KBRegistrationRequest(
    kb_id="sales-kb-1",
    kb_type="postgres",
    endpoint="postgresql://user:pass@localhost:5432/sales",
    operations=["sql_query"],
    metadata={"description": "Sales database"}
)
response = await kb_service.register_kb(kb_req)
print(f"KB registered: {response.kb_id}, Status: {response.status}")

# Register a knowledge base (Neo4j with credentials)
kb_req = KBRegistrationRequest(
    kb_id="graph-kb-1",
    kb_type="neo4j",
    endpoint="bolt://localhost:7687",  # No credentials in URI!
    operations=["cypher_query", "create_node"],
    credentials={  # Pass separately
        "username": "neo4j",
        "password": "admin123"
    },
    metadata={"description": "Graph database"}
)
response = await kb_service.register_kb(kb_req)

# List all agents
agents = await directory_service.list_agents(AgentListRequest())
for agent in agents.agents:
    print(f"Agent: {agent.identity}, Status: {agent.status}")

# Check health
from services.registry.schemas import HealthCheckRequest
health_req = HealthCheckRequest(entity_id="sales-agent-1", entity_type="agent")
health = await health_service.check_health(health_req)
print(f"Health: {health.status}, Latency: {health.latency_ms}ms")

# Start background monitoring
await health_service.start_monitoring(interval_seconds=30)
```

### Persistence Layer (Mesh State)

The persistence layer manages mesh metadata: agent registry, KB registry, policies, and audit logs.

```python
from adapters.persistence.sqlite import SQLitePersistenceAdapter
from adapters.persistence.schemas import (
    AgentRegistration, KBRegistration,
    PolicyDefinition, PolicyRule,
    AuditEvent, AuditEventType, AuditOutcome
)

# Initialize adapter (automatically creates and migrates database)
adapter = SQLitePersistenceAdapter("adapters/persistence/sqlite/config.yaml")
await adapter.connect()

# Register an agent
agent_id = await adapter.register_agent(
    AgentRegistration(
        identity="sales-agent-1",
        version="1.0.0",
        capabilities=["query_kb", "generate_report"],
        operations=["publish", "query", "subscribe"],
        schemas={"input": {"type": "object"}, "output": {"type": "array"}},
        health_endpoint="http://localhost:8001/health",
        metadata={"team": "sales", "region": "us-west"}
    )
)

# Register a knowledge base
kb_id = await adapter.register_kb(
    KBRegistration(
        kb_id="sales-kb-1",
        kb_type="postgres",
        endpoint="postgres://localhost:5432/sales",
        operations=["sql_query", "insert", "update"],
        kb_schema={"tables": ["customers", "deals", "activities"]},
        metadata={"owner": "sales-team"}
    )
)

# Create an access policy
policy_id = await adapter.create_policy(
    PolicyDefinition(
        policy_name="sales-team-read-only",
        rules=[
            PolicyRule(
                principal="sales-agent-*",      # Wildcard matching
                resource="sales-kb-1",
                action="read",
                effect="allow",
                masking_rules=["customer_email", "phone"]  # PII masking
            )
        ],
        precedence=100,
        active=True,
        metadata={"created_by": "admin"}
    )
)

# Evaluate policy
decision = await adapter.evaluate_policy(
    principal="sales-agent-1",
    resource="sales-kb-1",
    action="read"
)
# Returns: {"effect": "allow", "masking_rules": ["customer_email", "phone"], ...}

# Log an audit event
event_id = await adapter.log_event(
    AuditEvent(
        event_type=AuditEventType.QUERY,
        source_id="sales-agent-1",
        target_id="sales-kb-1",
        outcome=AuditOutcome.SUCCESS,
        request_metadata={"query_type": "sql", "table": "customers"},
        masked_fields=["customer_email", "phone"]
    )
)

# Query audit logs
from adapters.persistence.schemas import AuditQuery
logs = await adapter.query_audit_logs(
    AuditQuery(
        source_id="sales-agent-1",
        event_type=AuditEventType.QUERY,
        limit=100
    )
)

# Get audit statistics
stats = await adapter.get_audit_stats(source_id="sales-agent-1")
# Returns: {"outcome_counts": {...}, "event_type_counts": {...}}

await adapter.disconnect()
```

**Database Location**: By default, SQLite database is stored at `data/agentmesh.db`

**Automatic Migrations**: Schema is automatically created and versioned on first connection

**Future PostgreSQL Support**: For production deployments, uncomment the PostgreSQL persistence section in `docker-compose.yaml`

### Running Local Databases

```bash
# Start knowledge base databases (PostgreSQL and Neo4j)
docker-compose up -d

# Check database status
docker-compose ps

# View logs
docker-compose logs -f

# Stop databases
docker-compose down

# Stop and remove all data
docker-compose down -v
```

**Note**: The persistence layer (SQLite) doesn't require Docker - it's file-based and stored at `data/agentmesh.db`

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

**Note**: MCP server currently exposes knowledge base adapters. Persistence layer integration coming soon.

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
