# Contributing to HelpScout Ticket Insights

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/helpscout-ticket-insights.git`
3. Create a branch: `git checkout -b feature/your-feature-name`
4. Set up development environment (see README.md)

## Development Workflow

### Code Style

We use:
- **Black** for code formatting (line length: 100)
- **isort** for import sorting
- **flake8** for linting

Run before committing:
```bash
black src tests
isort src tests
flake8 src tests --max-line-length=100
```

### Testing

- Write tests for new features
- Ensure all tests pass: `pytest tests/ -v`
- Aim for >80% code coverage
- Use fixtures in `tests/conftest.py`

### Commit Messages

Follow conventional commits format:
- `feat: add new feature`
- `fix: resolve bug in syncer`
- `docs: update README`
- `test: add tests for analyzer`
- `refactor: improve database queries`

### Pull Requests

1. Update tests and documentation
2. Ensure CI passes
3. Provide clear description of changes
4. Reference any related issues
5. Request review from maintainers

## Adding New Features

### New LLM Provider

1. Add provider class in `src/analyzer/llm_provider.py`
2. Implement `LLMProvider` interface
3. Add to `get_llm_provider()` factory
4. Add configuration to `.env.example`
5. Add tests in `tests/test_analyzer.py`
6. Update documentation

### New API Endpoint

1. Add route in `src/api/routes.py`
2. Add Pydantic models for request/response
3. Add tests in `tests/test_api.py`
4. Update API documentation

## Code Review Process

1. Maintainers review PRs within 1-3 days
2. Address feedback promptly
3. Once approved, maintainers will merge

## Questions?

Open an issue or start a discussion on GitHub.

Thank you for contributing! 🎉
