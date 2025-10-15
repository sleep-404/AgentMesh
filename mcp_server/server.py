import asyncio
import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, TextContent, Tool

from adapters.knowledge_base.neo4j.adapter import Neo4jAdapter
from adapters.knowledge_base.postgres.adapter import PostgresAdapter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize server
app = Server("agentmesh-mcp")

# Global adapter instances
postgres_adapter: PostgresAdapter | None = None
neo4j_adapter: Neo4jAdapter | None = None


async def initialize_adapters():
    """Initialize database adapters"""
    global postgres_adapter, neo4j_adapter

    logger.info("Initializing PostgreSQL adapter...")
    postgres_adapter = PostgresAdapter("adapters/knowledge_base/postgres/config.yaml")
    await postgres_adapter.connect()

    logger.info("Initializing Neo4j adapter...")
    neo4j_adapter = Neo4jAdapter("adapters/knowledge_base/neo4j/config.yaml")
    await neo4j_adapter.connect()

    logger.info("All adapters initialized successfully")


async def cleanup_adapters():
    """Cleanup database connections"""
    if postgres_adapter:
        await postgres_adapter.disconnect()
    if neo4j_adapter:
        await neo4j_adapter.disconnect()


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Dynamically generate tools from adapter operations"""
    tools = []

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
    """Execute tool by routing to appropriate adapter"""
    try:
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
                    text=json.dumps({"error": f"Adapter not initialized for {name}"}),
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
