# AgentMesh: Setup & Installation Guide

This guide provides step-by-step instructions to get AgentMesh running on your local machine.

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Quick Start (5 minutes)](#quick-start-5-minutes)
3. [Detailed Setup](#detailed-setup)
4. [Claude Desktop Integration](#claude-desktop-integration)
5. [Running Demo Scenarios](#running-demo-scenarios)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required
- **Docker Desktop**: Version 20.10 or higher
  - [Download for macOS](https://www.docker.com/products/docker-desktop)
  - [Download for Windows](https://www.docker.com/products/docker-desktop)
  - [Download for Linux](https://docs.docker.com/desktop/install/linux-install/)

- **Python**: Version 3.11 or higher
  ```bash
  python3 --version  # Should show 3.11+
  ```

- **uv** (Python package manager): Latest version
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

### Optional
- **Claude Desktop**: For MCP integration
  - [Download from Anthropic](https://claude.ai/download)

---

## Quick Start (5 minutes)

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd AgentMesh
```

### Step 2: Start Infrastructure Services

```bash
# Start all services (PostgreSQL, Neo4j, NATS, OPA)
docker-compose up -d

# Verify all services are healthy
docker-compose ps
```

Expected output:
```
NAME                    STATUS              PORTS
agentmesh-nats          Up 10 seconds       0.0.0.0:4222->4222/tcp, 0.0.0.0:8222->8222/tcp
agentmesh-opa           Up 10 seconds       0.0.0.0:8181->8181/tcp
agentmesh-postgres-kb   Up 10 seconds       0.0.0.0:5432->5432/tcp
agentmesh-neo4j         Up 10 seconds       0.0.0.0:7474->7474/tcp, 0.0.0.0:7687->7687/tcp
```

### Step 3: Install Python Dependencies

```bash
# Navigate to project root
cd ..

# Sync dependencies and create virtual environment
uv sync --all-extras --all-groups

# Activate virtual environment
source .venv/bin/activate
```

### Step 4: Run a Demo Scenario

```bash
# Run Scenario 1: Privacy-Preserving Query
cd submission/examples
python scenario1_privacy.py
```

🎉 **You're done!** AgentMesh is now running.

---

## Detailed Setup

### 1. Infrastructure Services

#### Start All Services
```bash
cd /path/to/AgentMesh
docker-compose up -d
```

#### Verify Service Health

**Check PostgreSQL:**
```bash
docker exec -it agentmesh-postgres-kb psql -U admin -d agentmesh -c "SELECT version();"
```

**Check Neo4j:**
```bash
curl http://localhost:7474
# Should return Neo4j browser HTML
```

**Check NATS:**
```bash
curl http://localhost:8222/varz
# Should return NATS server info JSON
```

**Check OPA:**
```bash
curl http://localhost:8181/health
# Should return: {"status":"ok"}
```

#### View Service Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f postgres
docker-compose logs -f nats
docker-compose logs -f opa
```

### 2. Python Environment Setup

#### Install uv (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### Create Virtual Environment

```bash
cd /path/to/AgentMesh

# Sync dependencies (creates .venv automatically)
uv sync

# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
# or
.venv\Scripts\activate  # Windows
```

#### Verify Installation

```bash
# Check Python version
python --version  # Should be 3.11+

# Check installed packages
pip list | grep -E "asyncpg|neo4j|nats-py|pydantic"
```

### 3. Initialize Mesh Persistence

AgentMesh uses SQLite for persistence by default (no setup needed). The database file is automatically created at:

```
AgentMesh/data/agentmesh.db
```

#### View Database Schema

```bash
sqlite3 data/agentmesh.db ".schema"
```

Expected tables:
- `agents`
- `knowledge_bases`
- `policies`
- `audit_logs`
- `schema_version`

### 4. Test Installation

#### Run Integration Tests

```bash
# Run all tests
pytest tests/scenarios/ -v

# Run specific scenario
pytest tests/scenarios/test_1_registration_discovery.py -v
```

Expected: 16/20 tests passing (80% coverage)

---

## Claude Desktop Integration

### Overview

Claude Desktop integration enables you to use AgentMesh tools directly in conversations with Claude. This is the recommended way to interact with the mesh.

### Prerequisites

1. **Claude Desktop installed**: [Download here](https://claude.ai/download)
2. **AgentMesh services running**: `docker-compose up -d`

### Step 1: Configure Claude Desktop

Edit Claude Desktop configuration file:

**macOS**:
```bash
nano ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

**Windows**:
```
%APPDATA%\Claude\claude_desktop_config.json
```

**Linux**:
```bash
nano ~/.config/Claude/claude_desktop_config.json
```

### Step 2: Add MCP Server Configuration

Add the following to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "agentmesh": {
      "command": "/path/to/AgentMesh/.venv/bin/agentmesh-mcp",
      "env": {
        "PYTHONPATH": "/path/to/AgentMesh"
      }
    }
  }
}
```

**Important**: Replace `/path/to/AgentMesh` with your actual path:
```bash
# Get full path
pwd  # Run this in AgentMesh directory
```

### Step 3: Restart Claude Desktop

1. Quit Claude Desktop completely
2. Relaunch Claude Desktop
3. Look for 🔌 icon in Claude interface (indicates MCP server connected)

### Step 4: Test MCP Integration

In Claude Desktop, try:

```
User: "List all registered agents in the mesh"
```

Claude will use the `mcp_agentmesh_list_agents` tool automatically.

### Available MCP Tools

**Registry Management** (9 tools):
- `register_agent` - Register new agent
- `register_kb` - Register new KB
- `list_agents` - List all agents
- `list_kbs` - List all KBs
- `get_agent_details` - Get agent info
- `get_kb_details` - Get KB info
- `check_health` - Check entity health
- `upload_policy` - Upload OPA policy
- `query_kb_governed` - Query KB with governance

**PostgreSQL** (4 tools):
- `postgres_sql_query` - Execute SQL
- `postgres_insert` - Insert data
- `postgres_update` - Update data
- `postgres_delete` - Delete data

**Neo4j** (4 tools):
- `neo4j_cypher_query` - Execute Cypher
- `neo4j_create_node` - Create node
- `neo4j_create_relationship` - Create relationship
- `neo4j_find_node` - Find nodes

---

## Running Demo Scenarios

### Scenario 1: Cross-Team Privacy-Preserving Query

Demonstrates field-level masking and policy enforcement.

```bash
cd submission/examples
python scenario1_privacy.py
```

**What it does**:
1. Registers marketing agent
2. Registers sales PostgreSQL KB
3. Uploads privacy policy (masks email, phone)
4. Queries KB with field-level masking
5. Shows audit trail

### Scenario 3: Real-Time Agent Discovery

Demonstrates NATS pub/sub for real-time notifications.

```bash
cd submission/examples
python scenario3_discovery.py
```

**What it does**:
1. Connects to NATS and subscribes to directory updates
2. Listens for new agent/KB registrations (60 seconds)
3. Queries directory for current state
4. Shows all discovered agents/KBs

**Tip**: While scenario3_discovery.py is running, use Claude Desktop to register new agents and watch the real-time notifications!

### Running All Demo Scenarios

```bash
# Scenario 1
python submission/examples/scenario1_privacy.py

# Scenario 3
python submission/examples/scenario3_discovery.py
```

---

## Service Endpoints

### Knowledge Bases

| Service | Endpoint | Credentials |
|---------|----------|-------------|
| PostgreSQL | `localhost:5432` | User: `admin`<br>Pass: `admin123`<br>DB: `agentmesh` |
| Neo4j (HTTP) | `http://localhost:7474` | User: `neo4j`<br>Pass: `admin123` |
| Neo4j (Bolt) | `bolt://localhost:7687` | User: `neo4j`<br>Pass: `admin123` |

### Mesh Infrastructure

| Service | Endpoint | Purpose |
|---------|----------|---------|
| NATS Client | `nats://localhost:4222` | Agent messaging |
| NATS Monitoring | `http://localhost:8222` | NATS dashboard |
| OPA API | `http://localhost:8181` | Policy engine |
| SQLite DB | `../data/agentmesh.db` | Mesh persistence |

### Demo Agents (optional)

| Service | Endpoint | Framework |
|---------|----------|-----------|
| REST Agents | `http://localhost:8000` | CrewAI, OpenAI |
| gRPC Agents | `localhost:50051` | Langraph, Lyzr |

---

## Troubleshooting

### Services Not Starting

**Problem**: Docker services fail to start

**Solution**:
```bash
# Check if ports are already in use
lsof -i :5432  # PostgreSQL
lsof -i :7474  # Neo4j HTTP
lsof -i :7687  # Neo4j Bolt
lsof -i :4222  # NATS
lsof -i :8181  # OPA

# Stop conflicting services
docker-compose down -v

# Remove all containers and volumes
docker system prune -a --volumes

# Restart
docker-compose up -d
```

### PostgreSQL Connection Refused

**Problem**: `psycopg.OperationalError: connection refused`

**Solution**:
```bash
# Check PostgreSQL health
docker-compose ps postgres

# If not healthy, check logs
docker-compose logs postgres

# Wait for initialization
docker-compose logs -f postgres | grep "ready to accept connections"

# Restart if needed
docker-compose restart postgres
```

### NATS Connection Failed

**Problem**: `nats.errors.Error: nats: connection refused`

**Solution**:
```bash
# Check NATS health
curl http://localhost:8222/healthz

# If not healthy, restart
docker-compose restart nats

# Check logs
docker-compose logs nats
```

### OPA Policy Errors

**Problem**: `OPA policy evaluation failed`

**Solution**:
```bash
# Check OPA health
curl http://localhost:8181/health

# Test policy upload
curl -X PUT http://localhost:8181/v1/policies/agentmesh \
  -H "Content-Type: text/plain" \
  --data-binary @../policies/agentmesh.rego

# Check loaded policies
curl http://localhost:8181/v1/policies
```

### MCP Server Not Connecting

**Problem**: Claude Desktop shows "MCP server error"

**Solution**:

1. **Check paths in config**:
   ```bash
   # Verify virtual environment exists
   ls .venv/bin/agentmesh-mcp

   # Verify agentmesh-mcp exists
   which agentmesh-mcp
   ```

2. **Test MCP server manually**:
   ```bash
   cd /path/to/AgentMesh
   source .venv/bin/activate
   agentmesh-mcp
   ```

3. **Check Claude Desktop logs**:
   - macOS: `~/Library/Logs/Claude/`
   - Windows: `%LOCALAPPDATA%\Claude\logs\`

4. **Common fixes**:
   - Use absolute paths (not `~`)
   - Ensure `.venv` is activated
   - Restart Claude Desktop completely

### Python Import Errors

**Problem**: `ModuleNotFoundError: No module named 'adapters'`

**Solution**:
```bash
# Make sure you're in the project root
cd /path/to/AgentMesh

# Reinstall dependencies
uv sync --all-extras --all-groups

# Activate virtual environment
source .venv/bin/activate

# Verify PYTHONPATH
echo $PYTHONPATH  # Should include project root

# Set if missing
export PYTHONPATH=/path/to/AgentMesh:$PYTHONPATH
```

### Database Locked Errors

**Problem**: `sqlite3.OperationalError: database is locked`

**Solution**:
```bash
# Check for other processes using the DB
lsof data/agentmesh.db

# Kill stale processes
kill -9 <PID>

# If corruption suspected, rebuild
rm data/agentmesh.db
# DB will be recreated on next run
```

---

## Next Steps

### 1. Explore via Claude Desktop

Once MCP integration is working, try these commands in Claude:

```
"Register a sales agent with query and analysis capabilities"

"List all registered knowledge bases"

"Query the PostgreSQL database: SELECT * FROM customers LIMIT 5"

"Upload a policy that allows marketing to query sales but masks PII"
```

### 2. Run Integration Tests

```bash
# Run all scenario tests
pytest tests/scenarios/ -v

# Expected: 16/20 passing (80% coverage)
```

### 3. Build Custom Agents

See `dummy_agents/` for examples of:
- Langraph agents (graph workflows)
- CrewAI agents (multi-agent crews)
- Lyzr agents (workflow automation)
- OpenAI agents (direct API integration)

### 4. Extend with Custom KBs

Create custom KB adapters by implementing:
```python
from adapters.knowledge_base.base import KBAdapter

class MyCustomAdapter(KBAdapter):
    # Implement connect, disconnect, health, execute
    pass
```

---

## Support

### Documentation
- [README.md](README.md) - Project overview
- [ARCHITECTURE.md](ARCHITECTURE.md) - Technical deep dive
- [THINKING.md](THINKING.md) - Design rationale
- [DEMO.md](DEMO.md) - Demo scenarios

### Testing
- Integration tests: `tests/scenarios/`
- Test coverage: 80% (16/20 scenarios)

### Issues
- Check Docker logs: `docker-compose logs -f`
- Check application logs: `tail -f logs/agentmesh.log`
- Verify service health: `docker-compose ps`

---

## Clean Up

### Stop Services (keep data)
```bash
docker-compose down
```

### Stop Services (remove data)
```bash
docker-compose down -v
```

### Remove Python Environment
```bash
rm -rf .venv
```

### Complete Reset
```bash
# Remove all Docker containers, volumes, and images
docker-compose down -v
docker system prune -a --volumes

# Remove Python environment
rm -rf .venv

# Remove database
rm -rf data/

# Rebuild from scratch
docker-compose up -d
uv sync --all-extras --all-groups
```

---

## Production Deployment (Future)

For production deployments, consider:

1. **PostgreSQL for Persistence**:
   - Uncomment PostgreSQL persistence in `docker-compose.yml`
   - Migrate from SQLite to PostgreSQL

2. **NATS Clustering**:
   - Deploy 3+ NATS nodes for high availability
   - Configure NATS JetStream for message persistence

3. **Load Balancing**:
   - Deploy multiple MCP server instances
   - Use NGINX/HAProxy for load balancing

4. **Security**:
   - Enable TLS for NATS
   - Use secret management (Vault, AWS Secrets Manager)
   - Implement proper authentication (OAuth2/OIDC)

5. **Monitoring**:
   - Prometheus metrics for NATS
   - Grafana dashboards for visualization
   - ELK stack for log aggregation

---

**Happy meshing! 🎉**
