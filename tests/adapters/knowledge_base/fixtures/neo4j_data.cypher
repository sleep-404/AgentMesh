// Sample test data for Neo4j

// Create test nodes
CREATE (alice:Person {name: 'Alice', age: 30, email: 'alice@example.com'})
CREATE (bob:Person {name: 'Bob', age: 25, email: 'bob@example.com'})
CREATE (charlie:Person {name: 'Charlie', age: 35, email: 'charlie@example.com'})

// Create organization nodes
CREATE (acme:Organization {name: 'Acme Corp', industry: 'Technology'})
CREATE (beta:Organization {name: 'Beta Inc', industry: 'Finance'})

// Create relationships
CREATE (alice)-[:WORKS_FOR {since: 2020, position: 'Engineer'}]->(acme)
CREATE (bob)-[:WORKS_FOR {since: 2021, position: 'Designer'}]->(acme)
CREATE (charlie)-[:WORKS_FOR {since: 2019, position: 'Manager'}]->(beta)
CREATE (alice)-[:KNOWS {since: 2018}]->(bob)
CREATE (bob)-[:KNOWS {since: 2021}]->(charlie)

// Create project nodes
CREATE (project1:Project {name: 'Project Alpha', status: 'active'})
CREATE (project2:Project {name: 'Project Beta', status: 'completed'})

// Create project relationships
CREATE (alice)-[:CONTRIBUTES_TO {role: 'lead'}]->(project1)
CREATE (bob)-[:CONTRIBUTES_TO {role: 'developer'}]->(project1)
CREATE (charlie)-[:CONTRIBUTES_TO {role: 'lead'}]->(project2)
