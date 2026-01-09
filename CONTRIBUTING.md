# Contributing to Multi-Provider Router

Thank you for your interest in contributing to Multi-Provider Router! We welcome contributions from the community.

## How to Contribute

### Reporting Bugs

Before creating bug reports, please check existing issues to avoid duplicates. When creating a bug report, include:

- **Clear title and description**: Summarize the issue
- **Steps to reproduce**: Detailed steps to recreate the bug
- **Expected behavior**: What you expected to happen
- **Actual behavior**: What actually happened
- **Environment**: OS, Python version, package version
- **Logs**: Relevant error messages or logs

### Suggesting Enhancements

Enhancement suggestions are welcome! Please provide:

- **Clear title**: Describe the enhancement
- **Problem description**: What problem does it solve?
- **Proposed solution**: How should it work?
- **Alternatives considered**: Other approaches you've considered

### Pull Requests

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes**:
   - Write clean, readable code
   - Add tests for new functionality
   - Update documentation
4. **Run tests**: `pytest`
5. **Commit your changes**: Use clear commit messages
6. **Push to your branch**: `git push origin feature/amazing-feature`
7. **Create a Pull Request**: Describe your changes

## Development Setup

### Prerequisites

- Python 3.10 or higher
- Git
- Redis (for testing)
- Virtual environment (recommended)

### Setup

```bash
# Clone your fork
git clone https://github.com/yourusername/multi-provider-router.git
cd multi-provider-router

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest
```

### Code Style

We use:
- **Black** for code formatting
- **Ruff** for linting
- **mypy** for type checking

```bash
# Format code
black multi_provider_router tests examples

# Run linter
ruff check multi_provider_router tests examples

# Type checking
mypy multi_provider_router
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=multi_provider_router --cov-report=html

# Run specific test file
pytest tests/test_routing.py

# Run integration tests
pytest -m integration
```

## Project Structure

```
multi-provider-router/
├── multi_provider_router/      # Main package
│   ├── providers/              # Provider implementations
│   ├── routing/                # Routing engine
│   ├── utils/                  # Utilities (cache, rate limiter, etc.)
│   └── monitoring/             # Monitoring and metrics
├── tests/                      # Test suite
├── examples/                   # Usage examples
├── docs/                       # Documentation
└── config/                     # Configuration files
```

## Coding Guidelines

### Python Code

- Follow PEP 8 style guide
- Use type hints where appropriate
- Write docstrings for all public functions and classes
- Keep functions focused and modular
- Use meaningful variable and function names

### Documentation

- Update README.md for user-facing changes
- Add docstrings for new functions/classes
- Update CHANGELOG.md for significant changes
- Add examples for new features

### Commit Messages

Use clear, descriptive commit messages:

```
feat: add support for new provider
fix: resolve race condition in cache
docs: update installation instructions
test: add integration tests for routing
refactor: simplify provider selection logic
```

## Feature Guidelines

### Small Features
- Create a feature branch
- Implement and test
- Submit PR with description

### Large Features
1. **Discuss first**: Open an issue to discuss
2. **Proposal**: Create a design document
3. **Implementation**: Break into smaller PRs
4. **Documentation**: Update all relevant docs
5. **Tests**: Comprehensive test coverage

### Core Changes
- Core routing logic
- Provider abstractions
- Configuration system
- Monitoring/metrics

These require more discussion and review.

## Getting Help

- **Discussions**: Use GitHub Discussions for questions
- **Issues**: Use GitHub Issues for bugs and features
- **Email**: contact@multi-provider-router.dev

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Code of Conduct

Be respectful, constructive, and inclusive. We're all here to build something great together.

---

Thank you for contributing to Multi-Provider Router! 🚀
