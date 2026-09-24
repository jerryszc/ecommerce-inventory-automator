# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- GitHub Actions CI/CD pipeline with lint, typecheck, test, build stages
- Multi-stage Dockerfile with non-root user for security
- Development override compose file for hot reload
- Code quality tools: ruff, black, mypy, pre-commit
- Comprehensive test suite (53 tests, 80%+ coverage)
- Badges in README (CI, coverage, license, Python version)
- LICENSE (MIT), CONTRIBUTING.md, CODE_OF_CONDUCT.md
- Issue templates (bug report, feature request) and PR template
- pyproject.toml with modern tool configuration

### Changed
- Updated Dockerfile to multi-stage build with non-root user
- Split docker-compose.yml (base + development override)
- Improved README with badges and updated demo commands

### Security
- Non-root user in Docker container
- No hardcoded secrets, all via environment variables
- JWT tokens with configurable expiration

## [1.0.0] - 2026-09-24

### Added
- Initial release of E-Commerce Multi-Channel Inventory & Operations Automator
- FastAPI + PostgreSQL 16 + SQLModel + Alembic + Docker Compose stack
- JWT Authentication with roles (admin/operator)
- Product, Variant (size/color), Channel models
- Inventory sync with last-write-wins + conflict log
- CSV/Excel import with auto-detection, deduplication, error reporting
- Low-stock alerts with configurable thresholds
- Seed data for channels (amazon, shopify) and users (admin, operator)
- Comprehensive test suite (health, models, auth, CRUD, sync, import, alerts)
- README.md SOP bilingual (ES/EN) with 5-min demo

---

### Template for future releases:

## [X.Y.Z] - YYYY-MM-DD

### Added
- 

### Changed
- 

### Deprecated
- 

### Removed
- 

### Fixed
- 

### Security
-