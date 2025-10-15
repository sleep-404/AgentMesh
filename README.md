# AgentMesh

AgentMesh project.

## Prerequisites

- Python 3.11 or higher
- uv (recommended package manager)

## Installation

### Install uv (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Setup Project

```bash
# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dev dependencies (for pre-commit, linting, formatting)
uv pip install -e ".[dev]"
```

## Development

### Pre-commit Hooks

Set up pre-commit hooks to ensure code quality:

```bash
# Activate virtual environment first
source .venv/bin/activate

# Install pre-commit hooks
pre-commit install

# Run hooks manually on all files
pre-commit run --all-files
```

### Code Formatting

```bash
# Format code with black
black .

# Lint code with ruff
ruff check .

# Type check with mypy
mypy .
```

### Running Tests

```bash
pytest
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
