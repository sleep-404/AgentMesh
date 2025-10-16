# Database Configuration

This directory contains database-related initialization scripts and volume configurations.

## Structure

```
db/
├── knowledge_base/          # Knowledge base layer databases
│   ├── neo4j/              # Neo4j graph database
│   │   ├── init-neo4j.cypher    # Cypher script for initial data
│   │   └── init-neo4j.sh        # Shell script for initialization
│   └── postgres/           # PostgreSQL relational database
│       └── init-postgres.sql    # SQL script for initial data
└── persistence/            # Persistence layer (future)
```

## Knowledge Base Layer

### Neo4j
- **Purpose**: Graph database for storing relationships and graph-based knowledge
- **Init Scripts**:
  - `init-neo4j.cypher`: Contains Cypher queries to create initial nodes and relationships
  - `init-neo4j.sh`: Shell script that waits for Neo4j to be ready and loads initial data

### PostgreSQL
- **Purpose**: Relational database for structured data storage
- **Init Script**:
  - `init-postgres.sql`: Contains SQL statements to create tables, indexes, and insert initial data

## Persistence Layer

Reserved for future persistence layer implementation.

## Usage

These init scripts are mounted into their respective Docker containers via `docker-compose.yaml`:

- Neo4j scripts run once when the container is first created
- PostgreSQL scripts run automatically via Docker's `docker-entrypoint-initdb.d` mechanism
- Data persists across container restarts via Docker volumes
