# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-09-25

### Added
- **User Management**: CRUD endpoints (`POST/GET/PATCH/DELETE /auth/users/`), admin-only
- **Refresh Token Flow**: Access (60min) + Refresh (7d) tokens with rotation & revocation
- **Rate Limiting**: Global 100 req/min per IP via slowapi (configurable)
- **Security Headers**: OWASP headers (X-Content-Type-Options, X-Frame-Options, CSP, etc.)
- **CORS**: Configurable origins (default `*` for dev)
- **Structured Logging**: structlog with JSON, request ID, latency, structured context
- **Prometheus Metrics**: `/metrics` endpoint (requests, duration, DB queries, connections)
- **Health Checks**: `/health` (basic) + `/health/detailed` (DB status, timestamp)
- **User Management API**: Admin-only CRUD for users with role assignment
- **Refresh Token Flow**: Access (60min) + Refresh (7d) with rotation & revocation on logout
- **Tests**: 12 new tests for user management, refresh tokens, logout
- **AWS Integrations (LocalStack ready)**:
  - **Secrets Manager**: JWT_SECRET, DATABASE_URL rotados, cero en código
  - **CloudWatch Logs**: Structured JSON logs con request ID, latency
  - **SQS + Lambda**: Imports asíncronos (S3 → SQS → Lambda worker)
  - **S3**: Upload/download de archivos de importación
  - **ElastiCache Redis**: Rate limiting distribuido multi-instancia
  - **ECS Fargate + ECR**: Deploy zero-downtime via GitHub Actions OIDC
- **Tests**: 12 new tests para user management, refresh tokens, logout + 8 tests AWS

### Changed
- Updated Dockerfile to multi-stage build with non-root user (UID 10001)
- Added rate limiting (100 req/min global) via slowapi
- Added OWASP security headers middleware
- Added structured JSON logging with structlog
- Added Prometheus metrics endpoint (`/metrics`)
- Added detailed health check (`/health/detailed`)
- Updated README with new badges, sections (User Management, Rate Limiting, Observability, Security, AWS)
- Updated CHANGELOG with v1.1.0

### Security
- Rate limiting: 100 req/min global (configurable)
- OWASP security headers (CSP, X-Frame-Options, X-Content-Type-Options, etc.)
- CORS configurable (default `*` for dev)
- Non-root user in Docker container (UID 10001)
- Refresh token rotation & revocation on logout
- JWT access (60min) + Refresh (7d) tokens
- Secrets rotados via AWS Secrets Manager

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