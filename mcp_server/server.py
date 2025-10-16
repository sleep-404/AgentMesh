import asyncio
import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, TextContent, Tool

from adapters.knowledge_base.neo4j.adapter import Neo4jAdapter
from adapters.knowledge_base.postgres.adapter import PostgresAdapter
from adapters.persistence.sqlite.adapter import SQLitePersistenceAdapter
from services.registry import (
    AgentService,
    DirectoryService,
    HealthService,
    KBService,
)
from services.registry.schemas import (
    AgentListRequest,
    AgentRegistrationRequest,
    HealthCheckRequest,
    KBListRequest,
    KBRegistrationRequest,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize server
app = Server("agentmesh-mcp")

# Global adapter instances
postgres_adapter: PostgresAdapter | None = None
neo4j_adapter: Neo4jAdapter | None = None

# Global service instances
persistence_adapter: SQLitePersistenceAdapter | None = None
agent_service: AgentService | None = None
kb_service: KBService | None = None
directory_service: DirectoryService | None = None
health_service: HealthService | None = None


async def initialize_adapters():
    """Initialize database adapters and services"""
    global postgres_adapter, neo4j_adapter
    global persistence_adapter, agent_service, kb_service, directory_service, health_service

    logger.info("Initializing persistence adapter...")
    persistence_adapter = SQLitePersistenceAdapter(
        "adapters/persistence/sqlite/config.yaml"
    )
    await persistence_adapter.connect()

    logger.info("Initializing PostgreSQL adapter...")
    postgres_adapter = PostgresAdapter("adapters/knowledge_base/postgres/config.yaml")
    await postgres_adapter.connect()

    logger.info("Initializing Neo4j adapter...")
    neo4j_adapter = Neo4jAdapter("adapters/knowledge_base/neo4j/config.yaml")
    await neo4j_adapter.connect()

    logger.info("Initializing registry services...")
    agent_service = AgentService(persistence_adapter)
    kb_service = KBService(persistence_adapter)
    directory_service = DirectoryService(persistence_adapter)
    health_service = HealthService(persistence_adapter)

    logger.info("Starting health monitoring...")
    await health_service.start_monitoring(interval_seconds=30)

    logger.info("All adapters and services initialized successfully")


async def cleanup_adapters():
    """Cleanup database connections and services"""
    if health_service:
        await health_service.stop_monitoring()
    if postgres_adapter:
        await postgres_adapter.disconnect()
    if neo4j_adapter:
        await neo4j_adapter.disconnect()
    if persistence_adapter:
        await persistence_adapter.disconnect()


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Dynamically generate tools from adapter operations and registry services"""
    tools = []

    # Registry tools
    tools.extend(
        [
            Tool(
                name="register_agent",
                description="Register a new agent with the mesh",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "identity": {
                            "type": "string",
                            "description": "Unique identifier like 'sales-agent-1'",
                        },
                        "version": {
                            "type": "string",
                            "description": "Semantic version like '1.0.0'",
                        },
                        "capabilities": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "What the agent can do",
                        },
                        "operations": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Supported operations (publish/query/subscribe/invoke)",
                        },
                        "health_endpoint": {
                            "type": "string",
                            "description": "URL to check agent health",
                        },
                        "schemas": {
                            "type": "object",
                            "description": "Input/output schemas (optional)",
                        },
                        "metadata": {
                            "type": "object",
                            "description": "Additional metadata (optional)",
                        },
                    },
                    "required": [
                        "identity",
                        "version",
                        "capabilities",
                        "operations",
                        "health_endpoint",
                    ],
                },
            ),
            Tool(
                name="register_kb",
                description="Register a knowledge base with the mesh",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "kb_id": {
                            "type": "string",
                            "description": "Unique identifier like 'sales-kb-1'",
                        },
                        "kb_type": {
                            "type": "string",
                            "description": "KB type (postgres, neo4j, etc.)",
                        },
                        "endpoint": {
                            "type": "string",
                            "description": "Connection string",
                        },
                        "operations": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Supported operations",
                        },
                        "kb_schema": {
                            "type": "object",
                            "description": "Data structure schema (optional)",
                        },
                        "credentials": {
                            "type": "object",
                            "description": "Authentication credentials with 'username' and 'password' keys (optional)",
                        },
                        "metadata": {
                            "type": "object",
                            "description": "Owner, description, etc. (optional)",
                        },
                    },
                    "required": ["kb_id", "kb_type", "endpoint", "operations"],
                },
            ),
            Tool(
                name="list_agents",
                description="View all registered agents",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "capability_filter": {
                            "type": "string",
                            "description": "Filter by specific capability (optional)",
                        },
                        "status_filter": {
                            "type": "string",
                            "description": "Filter by status: active/degraded/offline (optional)",
                        },
                        "limit": {
                            "type": "number",
                            "description": "Maximum results (default: 100)",
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="list_kbs",
                description="View all registered knowledge bases",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "type_filter": {
                            "type": "string",
                            "description": "Filter by KB type (optional)",
                        },
                        "status_filter": {
                            "type": "string",
                            "description": "Filter by health status (optional)",
                        },
                        "limit": {
                            "type": "number",
                            "description": "Maximum results (default: 100)",
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="get_agent_details",
                description="Get detailed information about a specific agent",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "agent_id": {
                            "type": "string",
                            "description": "Agent identity",
                        },
                    },
                    "required": ["agent_id"],
                },
            ),
            Tool(
                name="get_kb_details",
                description="Get detailed information about a specific KB",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "kb_id": {
                            "type": "string",
                            "description": "KB identifier",
                        },
                    },
                    "required": ["kb_id"],
                },
            ),
            Tool(
                name="check_health",
                description="Manually trigger health check for agent or KB",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "Agent identity or KB ID",
                        },
                        "entity_type": {
                            "type": "string",
                            "description": "'agent' or 'kb'",
                        },
                    },
                    "required": ["entity_id", "entity_type"],
                },
            ),
            Tool(
                name="deregister_agent",
                description="Remove an agent from the mesh registry",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "identity": {
                            "type": "string",
                            "description": "Agent identity to remove",
                        },
                    },
                    "required": ["identity"],
                },
            ),
            Tool(
                name="deregister_kb",
                description="Remove a KB from the mesh registry",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "kb_id": {
                            "type": "string",
                            "description": "KB ID to remove",
                        },
                    },
                    "required": ["kb_id"],
                },
            ),
        ]
    )

    # PostgreSQL tools
    if postgres_adapter:
        pg_ops = postgres_adapter.get_operations()
        for op_name, op_metadata in pg_ops.items():
            tools.append(
                Tool(
                    name=f"postgres_{op_name}",
                    description=f"PostgreSQL: {op_metadata.description}",
                    inputSchema={
                        "type": "object",
                        "properties": op_metadata.input_schema.get("properties", {}),
                        "required": op_metadata.input_schema.get("required", []),
                    },
                )
            )

    # Neo4j tools
    if neo4j_adapter:
        neo4j_ops = neo4j_adapter.get_operations()
        for op_name, op_metadata in neo4j_ops.items():
            tools.append(
                Tool(
                    name=f"neo4j_{op_name}",
                    description=f"Neo4j: {op_metadata.description}",
                    inputSchema={
                        "type": "object",
                        "properties": op_metadata.input_schema.get("properties", {}),
                        "required": op_metadata.input_schema.get("required", []),
                    },
                )
            )

    return tools


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Execute tool by routing to appropriate adapter or service"""
    try:
        # Handle registry tools
        if name == "register_agent":
            if not agent_service:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"error": "Agent service not initialized"}),
                    )
                ]
            result = await agent_service.register_agent(
                AgentRegistrationRequest(**arguments)
            )
            return [TextContent(type="text", text=result.model_dump_json())]

        elif name == "register_kb":
            if not kb_service:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"error": "KB service not initialized"}),
                    )
                ]
            result = await kb_service.register_kb(KBRegistrationRequest(**arguments))  # type: ignore[assignment]
            return [TextContent(type="text", text=result.model_dump_json())]

        elif name == "list_agents":
            if not directory_service:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"error": "Directory service not initialized"}),
                    )
                ]
            result = await directory_service.list_agents(AgentListRequest(**arguments))  # type: ignore[assignment]
            return [TextContent(type="text", text=result.model_dump_json())]

        elif name == "list_kbs":
            if not directory_service:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"error": "Directory service not initialized"}),
                    )
                ]
            result = await directory_service.list_kbs(KBListRequest(**arguments))  # type: ignore[assignment]
            return [TextContent(type="text", text=result.model_dump_json())]

        elif name == "get_agent_details":
            if not agent_service:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"error": "Agent service not initialized"}),
                    )
                ]
            result = await agent_service.get_agent_details(arguments["agent_id"])  # type: ignore[assignment]
            return [TextContent(type="text", text=result.model_dump_json())]

        elif name == "get_kb_details":
            if not kb_service:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"error": "KB service not initialized"}),
                    )
                ]
            result = await kb_service.get_kb_details(arguments["kb_id"])  # type: ignore[assignment]
            return [TextContent(type="text", text=result.model_dump_json())]

        elif name == "check_health":
            if not health_service:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"error": "Health service not initialized"}),
                    )
                ]
            result = await health_service.check_health(HealthCheckRequest(**arguments))  # type: ignore[assignment]
            return [TextContent(type="text", text=result.model_dump_json())]

        elif name == "deregister_agent":
            if not agent_service:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"error": "Agent service not initialized"}),
                    )
                ]
            await agent_service.deregister_agent(arguments["identity"])
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": True,
                            "message": f"Agent '{arguments['identity']}' removed successfully",
                        }
                    ),
                )
            ]

        elif name == "deregister_kb":
            if not kb_service:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"error": "KB service not initialized"}),
                    )
                ]
            await kb_service.deregister_kb(arguments["kb_id"])
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": True,
                            "message": f"KB '{arguments['kb_id']}' removed successfully",
                        }
                    ),
                )
            ]

        # Handle KB adapter tools
        else:
            # Parse database type and operation
            adapter: PostgresAdapter | Neo4jAdapter | None
            if name.startswith("postgres_"):
                adapter = postgres_adapter
                operation = name.replace("postgres_", "")
            elif name.startswith("neo4j_"):
                adapter = neo4j_adapter
                operation = name.replace("neo4j_", "")
            else:
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": f"Unknown tool {name}"})
                    )
                ]

            if not adapter:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {"error": f"Adapter not initialized for {name}"}
                        ),
                    )
                ]

            # Execute operation
            result = await adapter.execute(operation, **arguments)

            # Format response - handle both Pydantic models and dicts
            if hasattr(result, "model_dump"):
                response = result.model_dump()
            else:
                response = {"data": result}

            return [TextContent(type="text", text=json.dumps(response))]

    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}", exc_info=True)
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


@app.list_resources()
async def list_resources() -> list[Resource]:
    """List available resources for metadata discovery"""
    return [
        Resource(
            uri="agentmesh://databases",
            name="Available Databases",
            mimeType="application/json",
            description="List of connected databases and their status",
        ),
        Resource(
            uri="agentmesh://operations/postgres",
            name="PostgreSQL Operations",
            mimeType="application/json",
            description="Available PostgreSQL operations and schemas",
        ),
        Resource(
            uri="agentmesh://operations/neo4j",
            name="Neo4j Operations",
            mimeType="application/json",
            description="Available Neo4j operations and schemas",
        ),
        Resource(
            uri="agentmesh://schema/postgres",
            name="PostgreSQL Schema",
            mimeType="application/json",
            description="PostgreSQL database schema",
        ),
    ]


@app.read_resource()
async def read_resource(uri: str) -> str:
    """Read resource content based on URI"""
    try:
        if uri == "agentmesh://databases":
            databases = []

            if postgres_adapter:
                health = await postgres_adapter.health()
                databases.append(
                    {
                        "name": "PostgreSQL",
                        "type": "postgres",
                        "status": health.status.value,
                        "operations": list(postgres_adapter.get_operations().keys()),
                    }
                )

            if neo4j_adapter:
                health = await neo4j_adapter.health()
                databases.append(
                    {
                        "name": "Neo4j",
                        "type": "neo4j",
                        "status": health.status.value,
                        "operations": list(neo4j_adapter.get_operations().keys()),
                    }
                )

            return json.dumps({"databases": databases})

        elif uri == "agentmesh://operations/postgres":
            if postgres_adapter:
                ops = postgres_adapter.get_operations()
                ops_dict = {
                    name: {
                        "description": meta.description,
                        "input_schema": meta.input_schema,
                        "output_schema": meta.output_schema,
                    }
                    for name, meta in ops.items()
                }
                return json.dumps({"operations": ops_dict})
            return json.dumps({"error": "PostgreSQL adapter not available"})

        elif uri == "agentmesh://operations/neo4j":
            if neo4j_adapter:
                ops = neo4j_adapter.get_operations()
                ops_dict = {
                    name: {
                        "description": meta.description,
                        "input_schema": meta.input_schema,
                        "output_schema": meta.output_schema,
                    }
                    for name, meta in ops.items()
                }
                return json.dumps({"operations": ops_dict})
            return json.dumps({"error": "Neo4j adapter not available"})

        elif uri == "agentmesh://schema/postgres":
            if postgres_adapter:
                # Query PostgreSQL schema
                result = await postgres_adapter.execute(
                    "sql_query",
                    query="""
                    SELECT table_name, column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                    ORDER BY table_name, ordinal_position
                    """,
                )
                return json.dumps({"schema": result.rows})
            return json.dumps({"error": "PostgreSQL adapter not available"})

        else:
            return json.dumps({"error": f"Unknown resource: {uri}"})

    except Exception as e:
        logger.error(f"Error reading resource {uri}: {e}", exc_info=True)
        return json.dumps({"error": str(e)})


async def async_main():
    """Async main entry point for MCP server"""
    try:
        # Initialize adapters
        await initialize_adapters()

        # Run server
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream, write_stream, app.create_initialization_options()
            )
    finally:
        # Cleanup
        await cleanup_adapters()


def main():
    """Synchronous entry point for MCP server (for setuptools)"""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
