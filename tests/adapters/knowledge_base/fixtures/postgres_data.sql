-- Sample test data for PostgreSQL

-- Create test table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert sample data
INSERT INTO users (username, email, role) VALUES
    ('admin', 'admin@example.com', 'admin'),
    ('user1', 'user1@example.com', 'user'),
    ('user2', 'user2@example.com', 'user'),
    ('moderator', 'mod@example.com', 'moderator');

-- Create test table for articles
CREATE TABLE IF NOT EXISTS articles (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT,
    author_id INTEGER REFERENCES users(id),
    published BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert sample articles
INSERT INTO articles (title, content, author_id, published) VALUES
    ('First Article', 'This is the first article content', 1, true),
    ('Draft Article', 'This is a draft', 2, false),
    ('Second Article', 'This is the second article content', 1, true);
