-- =====================================================
-- AgentMesh PostgreSQL Initialization Script
-- =====================================================
-- This script runs only once when the database is first created.
-- Data persists across container restarts via Docker volumes.
-- =====================================================

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    role VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create projects table
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    owner_id INTEGER REFERENCES users(id),
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create tasks table (for more complex queries)
CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    project_id INTEGER REFERENCES projects(id),
    assigned_to INTEGER REFERENCES users(id),
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    priority VARCHAR(20) NOT NULL DEFAULT 'medium',
    due_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- Insert sample data
-- =====================================================

-- Insert sample users
INSERT INTO users (username, email, role) VALUES
    ('alice', 'alice@example.com', 'admin'),
    ('bob', 'bob@example.com', 'developer'),
    ('charlie', 'charlie@example.com', 'analyst'),
    ('dana', 'dana@example.com', 'developer')
ON CONFLICT (username) DO NOTHING;

-- Insert sample projects
INSERT INTO projects (name, description, owner_id, status) VALUES
    ('AgentMesh', 'Multi-agent orchestration platform', 1, 'active'),
    ('DataPipeline', 'ETL pipeline system', 2, 'active'),
    ('Analytics', 'Business intelligence dashboard', 3, 'planning')
ON CONFLICT DO NOTHING;

-- Insert sample tasks
INSERT INTO tasks (title, description, project_id, assigned_to, status, priority, due_date) VALUES
    ('Setup PostgreSQL adapter', 'Implement PostgreSQL knowledge base adapter', 1, 2, 'completed', 'high', '2024-01-20'),
    ('Setup Neo4j adapter', 'Implement Neo4j knowledge base adapter', 1, 2, 'completed', 'high', '2024-01-25'),
    ('Create MCP server', 'Build MCP server to expose adapters', 1, 4, 'completed', 'high', '2024-02-01'),
    ('Write documentation', 'Document MCP setup and usage', 1, 1, 'in_progress', 'medium', '2024-02-15'),
    ('Build ETL pipeline', 'Create data extraction pipeline', 2, 2, 'in_progress', 'high', '2024-03-01'),
    ('Design dashboard UI', 'Create wireframes for analytics dashboard', 3, 3, 'pending', 'medium', '2024-03-15'),
    ('Implement API endpoints', 'Build REST API for data access', 2, 4, 'in_progress', 'high', '2024-02-28'),
    ('Setup testing framework', 'Configure pytest and integration tests', 1, 2, 'completed', 'medium', '2024-01-30')
ON CONFLICT DO NOTHING;

-- =====================================================
-- Create useful indexes for better query performance
-- =====================================================

CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_owner ON projects(owner_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority);
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_assigned_to ON tasks(assigned_to);

-- =====================================================
-- Create a view for easier querying
-- =====================================================

CREATE OR REPLACE VIEW project_summary AS
SELECT
    p.id,
    p.name,
    p.description,
    p.status,
    u.username as owner,
    u.email as owner_email,
    COUNT(DISTINCT t.id) as task_count,
    COUNT(DISTINCT CASE WHEN t.status = 'completed' THEN t.id END) as completed_tasks,
    COUNT(DISTINCT CASE WHEN t.status = 'in_progress' THEN t.id END) as in_progress_tasks,
    COUNT(DISTINCT CASE WHEN t.status = 'pending' THEN t.id END) as pending_tasks
FROM projects p
LEFT JOIN users u ON p.owner_id = u.id
LEFT JOIN tasks t ON t.project_id = p.id
GROUP BY p.id, p.name, p.description, p.status, u.username, u.email;

-- =====================================================
-- Grant permissions (optional, for production use)
-- =====================================================

-- Already handled by POSTGRES_USER environment variable
