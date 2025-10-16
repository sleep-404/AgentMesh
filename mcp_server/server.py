import asyncio
import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, TextContent, Tool

from adapters.knowledge_base.neo4j.adapter import Neo4jAdapter
from adapters.knowledge_base.postgres.adapter import PostgresAdapter
from adapters.messaging.nats_client import NATSWrapper
from adapters.persistence.sqlite.adapter import SQLitePersistenceAdapter
from adapters.policy.opa_client import OPAClient
from services.enforcement import EnforcementService
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
from services.routing import (
    AgentInvokeRequest,
    KBQueryRequest,
    RequestRouter,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize server
app = Server("agentmesh-mcp")

# Global adapter instances
postgres_adapter: PostgresAdapter | None = None
neo4j_adapter: Neo4jAdapter | None = None
nats_client: NATSWrapper | None = None
opa_client: OPAClient | None = None

# Global service instances
persistence_adapter: SQLitePersistenceAdapter | None = None
agent_service: AgentService | None = None
kb_service: KBService | None = None
directory_service: DirectoryService | None = None
health_service: HealthService | None = None
enforcement_service: EnforcementService | None = None
request_router: RequestRouter | None = None


async def initialize_adapters():
    """Initialize database adapters and services"""
    global postgres_adapter, neo4j_adapter, nats_client, opa_client
    global persistence_adapter, agent_service, kb_service, directory_service, health_service
    global enforcement_service, request_router

    logger.info("Initializing persistence adapter...")
    persistence_adapter = SQLitePersistenceAdapter(
        "adapters/persistence/sqlite/config.yaml"
    )
    await persistence_adapter.connect()

    # Initialize NATS client FIRST (optional - will fail silently if NATS not available)
    logger.info("Initializing NATS client...")
    nats_client = NATSWrapper()
    try:
        await nats_client.connect()
        logger.info("NATS client connected successfully")
    except Exception as e:
        logger.warning(f"NATS client not available: {e}")
        logger.warning("Registry services will work without real-time notifications")
        nats_client = None

    # Now initialize KB adapters WITH NATS client
    logger.info("Initializing PostgreSQL adapter...")
    postgres_adapter = PostgresAdapter(
        "adapters/knowledge_base/postgres/config.yaml",
        nats_client=nats_client,
        kb_id="postgres-kb-1",  # Default KB ID for demo
    )
    await postgres_adapter.connect()

    logger.info("Initializing Neo4j adapter...")
    neo4j_adapter = Neo4jAdapter(
        "adapters/knowledge_base/neo4j/config.yaml",
        nats_client=nats_client,
        kb_id="neo4j-kb-1",  # Default KB ID for demo
    )
    await neo4j_adapter.connect()

    # Initialize OPA client (optional - will fail silently if OPA not available)
    logger.info("Initializing OPA client...")
    opa_client = OPAClient()
    try:
        is_healthy = await opa_client.health_check()
        if is_healthy:
            logger.info("OPA client connected successfully")
        else:
            logger.warning("OPA health check failed")
            opa_client = None
    except Exception as e:
        logger.warning(f"OPA client not available: {e}")
        logger.warning("Enforcement service will use fallback policy evaluation")
        opa_client = None

    logger.info("Initializing registry services...")
    agent_service = AgentService(persistence_adapter, nats_client)
    kb_service = KBService(persistence_adapter, nats_client)
    directory_service = DirectoryService(persistence_adapter)
    health_service = HealthService(persistence_adapter)

    logger.info("Initializing enforcement and routing services...")
    # KB adapters map for enforcement service
    kb_adapters = {
        "postgres": postgres_adapter,
        "neo4j": neo4j_adapter,
    }

    # Initialize enforcement service (works with or without OPA)
    if opa_client:
        enforcement_service = EnforcementService(
            opa_client=opa_client,
            persistence=persistence_adapter,
            kb_adapters=kb_adapters,
            nats_client=nats_client,  # Pass NATS for message broker pattern
        )
        logger.info("Enforcement service initialized with OPA and NATS")
    else:
        logger.warning("Enforcement service not available without OPA")

    # Initialize request router (requires NATS and enforcement)
    if nats_client and enforcement_service:
        request_router = RequestRouter(
            enforcement=enforcement_service,
            persistence=persistence_adapter,
            nats_client=nats_client,
        )
        await request_router.start()
        logger.info("Request router started")
    else:
        logger.warning("Request router not available (requires NATS and OPA)")

    # Start KB adapters listening on NATS (message broker pattern)
    if nats_client:
        logger.info("Starting KB adapters on NATS...")
        if postgres_adapter:
            await postgres_adapter.start_listening()
        if neo4j_adapter:
            await neo4j_adapter.start_listening()
        logger.info("KB adapters listening on NATS subjects")
    else:
        logger.warning("KB adapters not listening on NATS (NATS not available)")

    logger.info("Starting health monitoring...")
    await health_service.start_monitoring(interval_seconds=30)

    logger.info("All adapters and services initialized successfully")


async def cleanup_adapters():
    """Cleanup database connections and services"""
    if request_router:
        await request_router.stop()
    if health_service:
        await health_service.stop_monitoring()
    if opa_client:
        await opa_client.close()
    if nats_client:
        await nats_client.disconnect()
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

    # Routing tools (governance layer)
    if request_router:
        tools.extend(
            [
                Tool(
                    name="query_kb_governed",
                    description="Query a KB through the governance layer (enforces policies, applies masking, logs audit)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "requester_id": {
                                "type": "string",
                                "description": "Agent/user requesting access",
                            },
                            "kb_id": {
                                "type": "string",
                                "description": "Target KB identifier",
                            },
                            "operation": {
                                "type": "string",
                                "description": "Operation to perform (e.g., 'sql_query', 'cypher_query')",
                            },
                            "params": {
                                "type": "object",
                                "description": "Operation parameters (e.g., {'query': 'SELECT ...'})",
                            },
                        },
                        "required": ["requester_id", "kb_id", "operation"],
                    },
                ),
                Tool(
                    name="invoke_agent_governed",
                    description="Invoke an agent through the governance layer (enforces policies, tracks invocation, logs audit)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "source_agent_id": {
                                "type": "string",
                                "description": "Agent requesting invocation",
                            },
                            "target_agent_id": {
                                "type": "string",
                                "description": "Target agent to invoke",
                            },
                            "operation": {
                                "type": "string",
                                "description": "Operation to perform on target",
                            },
                            "payload": {
                                "type": "object",
                                "description": "Operation payload",
                            },
                        },
                        "required": ["source_agent_id", "target_agent_id", "operation"],
                    },
                ),
                Tool(
                    name="get_invocation_status",
                    description="Get status of an agent invocation by tracking ID",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "tracking_id": {
                                "type": "string",
                                "description": "Tracking ID of the invocation",
                            },
                        },
                        "required": ["tracking_id"],
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

        # Handle routing tools (governance layer)
        elif name == "query_kb_governed":
            if not request_router:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "error": "Request router not available (requires NATS and OPA)"
                            }
                        ),
                    )
                ]

            kb_request = KBQueryRequest(
                requester_id=str(arguments.get("requester_id", "")),
                kb_id=str(arguments.get("kb_id", "")),
                operation=str(arguments.get("operation", "")),
                params=arguments.get("params", {}),
            )
            kb_response = await request_router.route_kb_query(kb_request)
            return [TextContent(type="text", text=json.dumps(kb_response.model_dump()))]

        elif name == "invoke_agent_governed":
            if not request_router:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "error": "Request router not available (requires NATS and OPA)"
                            }
                        ),
                    )
                ]

            agent_request = AgentInvokeRequest(
                source_agent_id=str(arguments.get("source_agent_id", "")),
                target_agent_id=str(arguments.get("target_agent_id", "")),
                operation=str(arguments.get("operation", "")),
                payload=arguments.get("payload", {}),
            )
            agent_response = await request_router.route_agent_invoke(agent_request)
            return [
                TextContent(type="text", text=json.dumps(agent_response.model_dump()))
            ]

        elif name == "get_invocation_status":
            if not request_router:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "error": "Request router not available (requires NATS and OPA)"
                            }
                        ),
                    )
                ]

            invocation_tracking_id = str(arguments.get("tracking_id", ""))
            invocation_response = await request_router.get_invocation_status(
                invocation_tracking_id
            )
            if invocation_response:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(invocation_response.model_dump()),
                    )
                ]
            else:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {"error": f"Invocation {invocation_tracking_id} not found"}
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
