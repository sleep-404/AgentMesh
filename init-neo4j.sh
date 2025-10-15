#!/bin/bash
# Neo4j initialization script
# This script waits for Neo4j to be ready and then loads initial data

echo "Waiting for Neo4j to be ready..."
until cypher-shell -u neo4j -p admin123 "RETURN 1" > /dev/null 2>&1; do
  echo "Neo4j is unavailable - sleeping"
  sleep 2
done

echo "Neo4j is up - checking if data already exists..."

# Check if data already exists (check for any Person nodes)
NODE_COUNT=$(cypher-shell -u neo4j -p admin123 "MATCH (n:Person) RETURN count(n) as count" --format plain | tail -n 1 | tr -d '[:space:]')

if [ "$NODE_COUNT" = "0" ]; then
  echo "Loading initial data into Neo4j..."
  cypher-shell -u neo4j -p admin123 < /init-data/init-neo4j.cypher
  echo "Initial data loaded successfully!"
else
  echo "Data already exists (found $NODE_COUNT Person nodes). Skipping initialization."
fi
