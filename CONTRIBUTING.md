# Contributing to E-Commerce Inventory Automator

Thank you for your interest in contributing! This document outlines the process for contributing to this project.

## Table of Contents
- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Standards](#code-standards)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Reporting Issues](#reporting-issues)

---

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

---

## Getting Started

### Prerequisites
- Python 3.12+
- Docker Desktop
- Git

### Local Setup
```bash
# 1. Fork and clone
git clone https://github.com/jerryszc/ecommerce-inventory-automator.git
cd ecommerce-inventory-automator

# 2. Set up environment
cp .env.example .env

# 3. Install pre-commit hooks
pip install pre-commit
pre-commit install

# 4. Start development stack
docker compose -f docker-compose.yml -f docker-compose.override.yml up --build -d

# 5. Run tests
docker compose exec api pytest -q
```

---

## Development Workflow

### Branching Strategy
- `main` — Production-ready code, protected branch
- `feature/*` — New features
- `fix/*` — Bug fixes
- `docs/*` — Documentation updates
- `refactor/*` — Code refactoring

### Commit Messages
Follow [Conventional Commits](https://www.conventionalcommits.org/):
```
<type>[optional scope]: <description>

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`

Examples:
```
feat(auth): add refresh token endpoint
fix(inventory): resolve race condition in sync
docs(readme): update demo commands
```

### Pre-commit Hooks
Run automatically on commit:
```bash
# Lint & format
ruff check --fix app tests
ruff format app tests

# Type check
mypy app

# Quick test
pytest -q
```

---

## Code Standards

### Python Style
- **Formatter:** `black` (line-length=100)
- **Linter:** `ruff` (target py312)
- **Type checker:** `mypy` (strict mode)
- **Import sorter:** `isort` (black profile)

### Type Hints
- All public functions must have type hints
- Use `from __future__ import annotations` for forward references
- Prefer `|` union syntax over `Union[]` (Python 3.10+)

### Documentation
- Docstrings for all public modules, classes, functions (Google style)
- Keep README.md updated with new endpoints/config
- Update OpenAPI docs via FastAPI auto-generation

---

## Testing

### Running Tests
```bash
# All tests
docker compose exec api pytest -q

# With coverage
docker compose exec api pytest --cov=app --cov-report=term-missing

# Specific module
docker compose exec api pytest -q tests/test_routers.py

# Watch mode (local)
pytest -q --watch
```

### Coverage Requirements
- Minimum **80%** overall coverage
- New code must have **100%** coverage
- Run `pytest --cov-fail-under=80` in CI

### Test Categories
| Marker | Description |
|--------|-------------|
| (none) | Unit tests, fast |
| `integration` | DB/external service tests |
| `slow` | Performance/load tests |

---

## Pull Request Process

1. **Create branch** from `main`
2. **Implement changes** with tests
3. **Run quality checks** locally:
   ```bash
   ruff check app tests
   ruff format --check app tests
   mypy app
   pytest -q --cov-fail-under=80
   ```
4. **Push branch** and create PR
5. **PR Requirements:**
   - All CI checks pass (lint, typecheck, test, build)
   - Coverage ≥ 80%
   - At least 1 approval from maintainer
   - Conventional commit messages
   - Updated documentation if needed
6. **Merge** via squash-and-merge to keep history clean

---

## Reporting Issues

### Bug Reports
Use the [Bug Report template](.github/ISSUE_TEMPLATE/bug_report.yml) with:
- Clear description
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python, Docker versions)
- Logs/screenshots

### Feature Requests
Use the [Feature Request template](.github/ISSUE_TEMPLATE/feature_request.yml) with:
- Problem statement
- Proposed solution
- Alternatives considered
- Implementation complexity estimate

### Security Issues
**Do not** open public issues for security vulnerabilities.
Email security@jerry.example.com directly.

---

## Release Process

Releases are automated via CI on push to `main`:
1. CI builds, tests, and creates Docker image
2. `requirements-lock.txt` generated and attached
3. GitHub Release created with tag `v{build_number}`
4. Changelog updated automatically from commit messages

---

## Questions?

Open a [Discussion](https://github.com/jerryszc/ecommerce-inventory-automator/discussions) or contact the maintainers.

---

**Thank you for contributing!** 🎉