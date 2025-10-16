# AgentMesh: 5-Minute Quickstart

Get AgentMesh running in 5 minutes with minimal setup.

---

## Step 1: Start Infrastructure (2 minutes)

```bash
# Navigate to project root
cd /path/to/AgentMesh

# Start all services (PostgreSQL, Neo4j, NATS, OPA)
docker-compose up -d

# Wait for services to be healthy (~30 seconds)
docker-compose ps
```

Expected: All services show "Up" status

---

## Step 2: Install Dependencies (1 minute)

```bash
# Make sure you're in the project root
cd /path/to/AgentMesh

# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate
```

**Note**: The project uses `uv` for dependency management. If `.venv` already exists, `uv sync` will use it.

---

## Step 3: Run Demo (1 minute)

```bash
cd submission/examples

# Run privacy-preserving query scenario
python scenario1_privacy.py
```

**You should see**:
- ✅ Marketing agent registered
- ✅ Sales KB registered
- ✅ Privacy policy uploaded
- ✅ Query executed with field masking (email, phone masked)
- ✅ Audit trail logged

---

## Step 4: Try with Claude Desktop (1 minute)

### Configure Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

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

**Replace `/path/to/AgentMesh` with your actual path**

### Restart Claude Desktop

Quit and relaunch Claude Desktop

### Try It

In Claude Desktop:

```
User: "List all registered agents"
```

Claude will use the `mcp_agentmesh_list_agents` tool automatically!

---

## What Just Happened?

1. **Infrastructure Started**: PostgreSQL (KB), Neo4j (KB), NATS (messaging), OPA (policies)
2. **Agent Registered**: Marketing agent with query capabilities
3. **KB Registered**: Sales PostgreSQL database
4. **Policy Uploaded**: Marketing can query but PII is masked
5. **Query Executed**: Mesh intercepted response and masked email/phone fields
6. **Audit Logged**: Access recorded with masked fields

---

## Next Steps

### Explore More Scenarios

```bash
# Real-time agent discovery (pub/sub)
python submission/examples/scenario3_discovery.py
```

### Run Integration Tests

```bash
# Run all scenario tests
pytest tests/scenarios/ -v

# Expected: 16/20 tests passing (80% coverage)
```

### Read Documentation

- **README.md** - Project overview and features
- **ARCHITECTURE.md** - Technical deep dive
- **DEMO.md** - Visual walkthroughs with examples
- **SETUP.md** - Detailed installation guide
- **EVALUATION_MAPPING.md** - Evidence for each criterion

---

## Troubleshooting

### Services Not Starting?

```bash
# Check if ports are already in use
lsof -i :5432  # PostgreSQL
lsof -i :7474  # Neo4j
lsof -i :4222  # NATS
lsof -i :8181  # OPA

# Stop conflicting services
docker-compose down -v

# Restart
docker-compose up -d
```

### Python Import Errors?

```bash
# Make sure you're in the right directory
cd /path/to/AgentMesh

# Activate virtual environment
source .venv/bin/activate

# Set PYTHONPATH
export PYTHONPATH=/path/to/AgentMesh:$PYTHONPATH
```

### Claude Desktop Not Connecting?

1. Use **absolute paths** (not `~`) in config
2. Verify virtual environment exists: `ls .venv/bin/uv`
3. Restart Claude Desktop completely
4. Check logs: `~/Library/Logs/Claude/`

---

## Service Endpoints

| Service | Endpoint | Credentials |
|---------|----------|-------------|
| PostgreSQL | `localhost:5432` | admin / admin123 |
| Neo4j HTTP | `localhost:7474` | neo4j / admin123 |
| Neo4j Bolt | `localhost:7687` | neo4j / admin123 |
| NATS | `localhost:4222` | (no auth) |
| NATS Monitor | `localhost:8222` | (dashboard) |
| OPA | `localhost:8181` | (no auth) |

---

## Key Features Demonstrated

✅ **Ease of Integration**: Agent/KB registration in <30 seconds
✅ **Data Privacy**: Field-level masking (email, phone)
✅ **Policy Enforcement**: OPA evaluation in <10ms
✅ **Audit Trail**: Immutable logs with masked fields
✅ **Real-Time**: NATS pub/sub for instant discovery
✅ **MCP Integration**: 17 auto-generated tools
✅ **Zero-Copy**: Mesh doesn't store customer data

---

## Clean Up

```bash
# Stop services (keep data)
docker-compose down

# Stop services (remove data)
docker-compose down -v
```

---

**You're ready to explore AgentMesh! 🚀**

For detailed documentation, see the other files in this directory.
