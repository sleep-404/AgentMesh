// Create sample Person nodes
CREATE (alice:Person {name: 'Alice Johnson', age: 32, email: 'alice@example.com', role: 'admin'});
CREATE (bob:Person {name: 'Bob Smith', age: 28, email: 'bob@example.com', role: 'developer'});
CREATE (charlie:Person {name: 'Charlie Davis', age: 35, email: 'charlie@example.com', role: 'analyst'});
CREATE (dana:Person {name: 'Dana Lee', age: 30, email: 'dana@example.com', role: 'developer'});

// Create sample Project nodes
CREATE (agentmesh:Project {name: 'AgentMesh', description: 'Multi-agent orchestration platform', status: 'active', created_at: datetime()});
CREATE (pipeline:Project {name: 'DataPipeline', description: 'ETL pipeline system', status: 'active', created_at: datetime()});
CREATE (analytics:Project {name: 'Analytics', description: 'Business intelligence dashboard', status: 'planning', created_at: datetime()});

// Create sample Technology nodes
CREATE (python:Technology {name: 'Python', type: 'language', version: '3.11'});
CREATE (neo4j:Technology {name: 'Neo4j', type: 'database', version: '5.15'});
CREATE (postgres:Technology {name: 'PostgreSQL', type: 'database', version: '16'});

// Create relationships between People and Projects (OWNS, WORKS_ON)
MATCH (alice:Person {name: 'Alice Johnson'})
MATCH (agentmesh:Project {name: 'AgentMesh'})
CREATE (alice)-[:OWNS {since: date('2024-01-15')}]->(agentmesh);

MATCH (bob:Person {name: 'Bob Smith'})
MATCH (pipeline:Project {name: 'DataPipeline'})
CREATE (bob)-[:OWNS {since: date('2024-02-01')}]->(pipeline);

MATCH (charlie:Person {name: 'Charlie Davis'})
MATCH (analytics:Project {name: 'Analytics'})
CREATE (charlie)-[:OWNS {since: date('2024-03-10')}]->(analytics);

MATCH (bob:Person {name: 'Bob Smith'})
MATCH (agentmesh:Project {name: 'AgentMesh'})
CREATE (bob)-[:WORKS_ON {role: 'backend_developer', since: date('2024-01-20')}]->(agentmesh);

MATCH (dana:Person {name: 'Dana Lee'})
MATCH (agentmesh:Project {name: 'AgentMesh'})
CREATE (dana)-[:WORKS_ON {role: 'frontend_developer', since: date('2024-02-01')}]->(agentmesh);

// Create relationships between People (KNOWS)
MATCH (alice:Person {name: 'Alice Johnson'})
MATCH (bob:Person {name: 'Bob Smith'})
CREATE (alice)-[:KNOWS {since: date('2023-06-15'), relationship: 'colleague'}]->(bob);

MATCH (bob:Person {name: 'Bob Smith'})
MATCH (dana:Person {name: 'Dana Lee'})
CREATE (bob)-[:KNOWS {since: date('2024-01-10'), relationship: 'colleague'}]->(dana);

MATCH (alice:Person {name: 'Alice Johnson'})
MATCH (charlie:Person {name: 'Charlie Davis'})
CREATE (alice)-[:KNOWS {since: date('2023-08-20'), relationship: 'friend'}]->(charlie);

// Create relationships between Projects and Technologies (USES)
MATCH (agentmesh:Project {name: 'AgentMesh'})
MATCH (python:Technology {name: 'Python'})
CREATE (agentmesh)-[:USES {purpose: 'core_implementation'}]->(python);

MATCH (agentmesh:Project {name: 'AgentMesh'})
MATCH (neo4j:Technology {name: 'Neo4j'})
CREATE (agentmesh)-[:USES {purpose: 'graph_storage'}]->(neo4j);

MATCH (agentmesh:Project {name: 'AgentMesh'})
MATCH (postgres:Technology {name: 'PostgreSQL'})
CREATE (agentmesh)-[:USES {purpose: 'relational_storage'}]->(postgres);

MATCH (pipeline:Project {name: 'DataPipeline'})
MATCH (python:Technology {name: 'Python'})
CREATE (pipeline)-[:USES {purpose: 'core_implementation'}]->(python);

MATCH (analytics:Project {name: 'Analytics'})
MATCH (postgres:Technology {name: 'PostgreSQL'})
CREATE (analytics)-[:USES {purpose: 'data_warehouse'}]->(postgres);
