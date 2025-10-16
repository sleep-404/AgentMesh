# Agentic Tests - Setup Guide

This guide helps you set up the infrastructure needed to run agentic tests.

## Quick Start (Using Docker Compose)

The easiest way to get started:

```bash
# 1. Start all infrastructure services
docker-compose up -d nats opa postgres neo4j

# 2. Wait for services to be ready (about 10 seconds)
sleep 10

# 3. Start the mesh service
python -m services.bootstrap.mesh_service &

# 4. Wait for mesh to initialize
sleep 5

# 5. Run the tests
pytest tests/scenarios_agentic/test_2_policy_enforcement_agentic.py -v
```

## Manual Setup (Step by Step)

If you prefer to run services manually:

### 1. Start NATS Server

```bash
# Install NATS (if not already installed)
# macOS:
brew install nats-server

# Linux:
# Download from https://github.com/nats-io/nats-server/releases

# Start NATS
nats-server --port 4222
```

**Verify:**
```bash
nats-server --version
# Should show version info
```

### 2. Start OPA Server

```bash
# Install OPA (if not already installed)
# macOS:
brew install opa

# Linux:
# Download from https://github.com/open-policy-agent/opa/releases

# Start OPA with policies
cd /Users/jeevan/AgentMesh
opa run --server --addr localhost:8181 ./policies/
```

**Verify:**
```bash
curl http://localhost:8181/health
# Should return: {"status":"ok"}

curl http://localhost:8181/v1/policies
# Should list loaded policies
```

### 3. Start PostgreSQL

```bash
# Using Docker (recommended)
docker run -d \
  --name agentmesh-postgres \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=agentmesh123 \
  -e POSTGRES_DB=agentmesh \
  postgres:15

# Wait for PostgreSQL to be ready
sleep 5
```

**Verify:**
```bash
docker exec agentmesh-postgres pg_isready
# Should return: /var/run/postgresql:5432 - accepting connections
```

**Initialize database schema (optional):**
```bash
docker exec -i agentmesh-postgres psql -U postgres -d agentmesh < db/knowledge_base/postgres/init-postgres.sql
```

### 4. Start Neo4j (Optional - for some tests)

```bash
docker run -d \
  --name agentmesh-neo4j \
  -p 7687:7687 \
  -p 7474:7474 \
  -e NEO4J_AUTH=neo4j/agentmesh123 \
  neo4j:5

# Wait for Neo4j to be ready
sleep 10
```

**Verify:**
```bash
# Should be able to access web UI
open http://localhost:7474
```

### 5. Start AgentMesh Service

```bash
cd /Users/jeevan/AgentMesh

# Activate virtual environment
source .venv/bin/activate

# Start mesh service
python -m services.bootstrap.mesh_service
```

**Verify (in another terminal):**
```bash
# Install NATS CLI (if not already)
brew install nats-io/nats-tools/nats

# Check mesh health
nats req mesh.health "" --server nats://localhost:4222

# Should return JSON with "status": "healthy"
```

### 6. Run Tests

```bash
# In another terminal, with venv activated
cd /Users/jeevan/AgentMesh
source .venv/bin/activate

# Run scenario 2 tests
pytest tests/scenarios_agentic/test_2_policy_enforcement_agentic.py -v

# Or run directly
python tests/scenarios_agentic/test_2_policy_enforcement_agentic.py
```

## Troubleshooting

### NATS Connection Errors

**Problem:** `Failed to connect to NATS`

**Solution:**
```bash
# Check if NATS is running
lsof -i :4222

# If not running, start it
nats-server --port 4222
```

### OPA Not Responding

**Problem:** `OPA client not available`

**Solution:**
```bash
# Check if OPA is running
curl http://localhost:8181/health

# If not running, start it
cd /Users/jeevan/AgentMesh
opa run --server --addr localhost:8181 ./policies/
```

### PostgreSQL Connection Errors

**Problem:** `KB registration failed` or connection timeout

**Solution:**
```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# If not running, start it
docker start agentmesh-postgres

# Or create new container
docker run -d --name agentmesh-postgres \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=agentmesh123 \
  -e POSTGRES_DB=agentmesh \
  postgres:15
```

### Mesh Service Not Responding

**Problem:** `Registration timeout` or `mesh.health` not responding

**Solution:**
```bash
# Check mesh service logs
# Look for errors in the terminal where mesh service is running

# Restart mesh service
pkill -f "services.bootstrap.mesh_service"
python -m services.bootstrap.mesh_service

# Check mesh health
nats req mesh.health "" --server nats://localhost:4222
```

### Policy Not Loading

**Problem:** Tests fail with policy errors

**Solution:**
```bash
# Check OPA policies
curl http://localhost:8181/v1/policies

# Should show "agentmesh" policy loaded

# If not, restart OPA with correct path
cd /Users/jeevan/AgentMesh
opa run --server --addr localhost:8181 ./policies/
```

## Monitoring During Tests

### Monitor all NATS messages:
```bash
nats sub "mesh.>" --server nats://localhost:4222
```

### Monitor KB queries only:
```bash
nats sub "mesh.routing.kb_query" --server nats://localhost:4222
```

### Monitor registrations:
```bash
nats sub "mesh.registry.>" --server nats://localhost:4222
```

### Check OPA decision logs:
```bash
# OPA logs decisions to console
# Watch the terminal where OPA is running
```

## Cleanup

### Stop all services:
```bash
# Stop mesh service
pkill -f "services.bootstrap.mesh_service"

# Stop OPA
pkill -f "opa run"

# Stop NATS
pkill nats-server

# Stop Docker containers
docker stop agentmesh-postgres agentmesh-neo4j
docker rm agentmesh-postgres agentmesh-neo4j
```

### Or use Docker Compose:
```bash
docker-compose down -v
```

## Architecture Overview

```
┌──────────────────┐
│   Test Agent     │  ← Python test using SimpleNATSAgent
│   (Agentic)      │     NO knowledge of mesh internals
└────────┬─────────┘
         │ NATS only
         ↓
┌──────────────────┐
│   NATS Server    │  ← Message broker (localhost:4222)
│   :4222          │
└────────┬─────────┘
         │
         ↓
┌──────────────────┐
│  Mesh Service    │  ← services/bootstrap/mesh_service.py
│  ┌─────────────┐ │
│  │ Router      │ │  ← Handles NATS subscriptions
│  │ Enforcement │ │  ← Calls OPA for policy decisions
│  │ Registry    │ │  ← Manages agents & KBs
│  │ KB Adapters │ │  ← Executes KB operations
│  └─────────────┘ │
└────────┬─────────┘
         │
         ├──────────────────────┐
         ↓                      ↓
┌──────────────────┐  ┌──────────────────┐
│   OPA Server     │  │  SQLite          │
│   :8181          │  │  (persistence)   │
│                  │  └──────────────────┘
│  Policy Rules:   │
│  - agentmesh.rego│
└──────────────────┘
         │
         ↓
┌──────────────────┐
│  PostgreSQL/     │  ← Knowledge bases
│  Neo4j           │
└──────────────────┘
```

## Next Steps

Once scenario 2 tests pass:
1. Convert scenario 1 (Registration & Discovery)
2. Convert scenario 3 (Agent Invocation)
3. Convert scenario 4 (Real-Time Notifications)
4. Convert scenario 5 (KB Request-Reply)
5. Convert scenario 6 (Metadata & Audit)

See `AGENTIC_TODO` for the full conversion roadmap!

