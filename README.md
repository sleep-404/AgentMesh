# AgentMesh

AgentMesh project.

## Prerequisites

- Python 3.11 or higher
- uv package manager

## Installation

### Install uv (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Setup Project

```bash
# Sync dependencies and create virtual environment automatically
uv sync --all-extras --all-groups

# This will:
# - Create .venv automatically
# - Install all dependencies and dev dependencies
# - Create/update uv.lock file
```

## Development

### Pre-commit Hooks

Set up pre-commit hooks to ensure code quality:

```bash
# Install pre-commit hooks
uv run pre-commit install

# Run hooks manually on all files
uv run pre-commit run --all-files
```

### Code Formatting

```bash
# Format code with black
uv run black .

# Lint code with ruff
uv run ruff check .

# Type check with mypy
uv run mypy .
```

### Running Tests

```bash
uv run pytest
```

### Adding Dependencies

```bash
# Add a production dependency
uv add package-name

# Add a development dependency
uv add --group dev package-name

# Sync after manually editing pyproject.toml
uv sync --all-extras --all-groups
```

## Project Structure

```
.
├── architectures/        # Architecture diagrams
├── knowledge/           # Documentation and knowledge base
├── src/                 # Source code (to be created)
├── tests/              # Test files (to be created)
├── .env                # Environment variables (create this)
├── .gitignore          # Git ignore patterns
├── .pre-commit-config.yaml  # Pre-commit hooks configuration
├── pyproject.toml      # Project dependencies and configuration
└── README.md           # This file
```

## Contributing

1. Create a feature branch
2. Make your changes
3. Run pre-commit hooks: `pre-commit run --all-files`
4. Run tests: `pytest`
5. Commit your changes with conventional commits format
6. Submit a pull request

## License

[Add your license here]
