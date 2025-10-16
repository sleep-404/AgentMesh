# Real Agent Implementations

**REAL** implementations of 4 different agent types using their actual frameworks, with API endpoints to spawn, execute, and terminate agents.

## Agents

1. **Langraph Agent** ✅ - Uses real `langgraph` library with StateGraph
2. **OpenAI Agent** ✅ - Uses real `openai` SDK (supports mock mode without API key)
3. **CrewAI Agent** ✅ - Uses real `crewai` library (supports mock mode without API key)
4. **Lyzr Agent** ⚠️ - Compatibility mode (lyzr-automata has dependency conflicts)

## Features

- ✅ **Real Framework Integration**: Uses actual langgraph, openai, and crewai libraries
- ✅ **Mock Mode Support**: OpenAI, CrewAI, and Lyzr agents work without API keys for testing
- ✅ **Spawn on Demand**: Agents are created per request and terminated after execution
- ✅ **Dual API Support**: Both gRPC and REST endpoints available

## Architecture

- **gRPC Server** (port 50051): Langraph and Lyzr agents
- **REST API Server** (port 8000): CrewAI and OpenAI agents

## Setup

1. Install dependencies:
```bash
# Using uv (recommended)
uv pip install langgraph langchain-core langchain-openai crewai openai grpcio grpcio-tools fastapi uvicorn requests

# Or using pip
pip install langgraph langchain-core langchain-openai crewai openai grpcio grpcio-tools fastapi uvicorn requests
```

2. Generate gRPC Python code:
```bash
python dummy_agents/generate_grpc.py
```

3. (Optional) Configure OpenAI API key for real execution:
```bash
# Copy the example file
cp dummy_agents/.env.example dummy_agents/.env

# Edit .env and add your OpenAI API key
# OR export directly:
export OPENAI_API_KEY="your-api-key-here"
```

**Note**: Without an API key, OpenAI and CrewAI agents will run in **mock mode** (still functional for testing).

## Running the Servers

### Start gRPC Server
```bash
python dummy_agents/grpc_server.py
```

The gRPC server will start on port 50051 with the following endpoints:
- `ExecuteLangraphAgent`
- `ExecuteLyzrAgent`

### Start REST API Server
```bash
python dummy_agents/rest_server.py
```

The REST API server will start on port 8000 with the following endpoints:
- `POST /api/agents/crewai`
- `POST /api/agents/openai`

## Usage Examples

### gRPC Client (Python)

```python
import grpc
from dummy_agents.protos import agent_service_pb2, agent_service_pb2_grpc

# Create channel
channel = grpc.insecure_channel('localhost:50051')
stub = agent_service_pb2_grpc.AgentServiceStub(channel)

# Execute Langraph agent
request = agent_service_pb2.AgentRequest(task="Analyze sales data")
response = stub.ExecuteLangraphAgent(request)
print(f"Result: {response.result}")

# Execute Lyzr agent
request = agent_service_pb2.AgentRequest(task="Generate report")
response = stub.ExecuteLyzrAgent(request)
print(f"Result: {response.result}")
```

### REST API Client (curl)

```bash
# Execute CrewAI agent
curl -X POST "http://localhost:8000/api/agents/crewai" \
  -H "Content-Type: application/json" \
  -d '{"task": "Analyze market trends"}'

# Execute OpenAI agent
curl -X POST "http://localhost:8000/api/agents/openai" \
  -H "Content-Type: application/json" \
  -d '{"task": "Summarize document"}'
```

### REST API Client (Python)

```python
import requests

# Execute CrewAI agent
response = requests.post(
    "http://localhost:8000/api/agents/crewai",
    json={"task": "Analyze market trends"}
)
print(response.json())

# Execute OpenAI agent
response = requests.post(
    "http://localhost:8000/api/agents/openai",
    json={"task": "Summarize document"}
)
print(response.json())
```

## API Documentation

Once the REST server is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Agent Behavior

Each agent:
1. **Spawns on request** - New instance per API call
2. **Executes the given task** - Uses real framework (or mock mode)
3. **Returns structured result** - JSON response with execution details
4. **Terminates** - No persistent state, clean shutdown

All agents are **stateless** and exist only for the duration of the request.

## Agent Details

### Langraph Agent ✅
- **Framework**: Real `langgraph` StateGraph
- **Features**: Actual graph-based workflow with nodes and edges
- **Requirements**: No API key needed
- **Status**: Fully functional

### OpenAI Agent ✅
- **Framework**: Real `openai` SDK
- **Features**: Direct OpenAI API integration
- **Requirements**: `OPENAI_API_KEY` environment variable for real mode
- **Mock Mode**: Yes (works without API key for testing)
- **Status**: Fully functional

### CrewAI Agent ✅
- **Framework**: Real `crewai` library
- **Features**: Agent roles, tasks, and crew orchestration
- **Requirements**: `OPENAI_API_KEY` environment variable for real mode
- **Mock Mode**: Yes (works without API key for testing)
- **Status**: Fully functional

### Lyzr Agent ⚠️
- **Framework**: `lyzr-automata` (when available)
- **Issue**: Dependency conflict - requires `openai==1.3.4` (incompatible with other packages)
- **Current Mode**: Compatibility mode (simulated)
- **Workaround**: Can run in separate virtual environment with only lyzr-automata installed
- **Status**: Works in compatibility mode
