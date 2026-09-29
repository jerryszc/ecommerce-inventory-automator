# E-Commerce Multi-Channel Inventory & Operations Automator

**[Versión en español →](README.md)**

Inventory synchronisation API across sales channels, with asynchronous processing on AWS,
role-based access control and production-grade observability.

[![CI/CD](https://github.com/jerryszc/ecommerce-inventory-automator/actions/workflows/ci.yml/badge.svg)](https://github.com/jerryszc/ecommerce-inventory-automator/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/jerryszc/ecommerce-inventory-automator/branch/main/graph/badge.svg)](https://codecov.io/gh/jerryszc/ecommerce-inventory-automator)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141+-009688.svg)](https://fastapi.tiangolo.com/)
[![AWS](https://img.shields.io/badge/AWS-S3%20%7C%20SQS%20%7C%20Secrets%20Manager-orange.svg)](https://aws.amazon.com/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED.svg)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/tests-75%20passing-brightgreen.svg)](tests)

**Stack:** Python 3.12 · FastAPI · SQLModel · PostgreSQL 16 · Redis · AWS (S3, SQS, Secrets Manager) · Docker · GitHub Actions

---

## The business problem

A retailer selling on more than one marketplace hits three failures that cost money and
hours of manual work, and that no spreadsheet fixes:

| Problem | Real cost to the business | What replaces it here |
| :--- | :--- | :--- |
| **Stock divergence across channels.** Amazon shows 10 units, Shopify shows 8, and neither is authoritative | Overselling: units that do not exist get sold. The marketplace penalises the account, and every oversell becomes a refund, a cancellation and a reputational hit | *Last-write-wins* sync by `updated_at`, with an immutable `ConflictLog` recording every discrepancy: one source of truth plus an auditable history |
| **Manual catalogue loading from suppliers.** CSV/Excel files where every provider names its columns differently, one row per SKU | Hours per batch. A single mislabelled header, or one row with a negative quantity, blocks the entire upload | Alias-tolerant column parser, automatic catalogue creation, deduplication, and **per-row error reporting**: a messy file still processes its valid rows instead of being rejected whole |
| **Low stock undetected until a sale fails.** The team finds out after the revenue is already lost | Lost sales and an availability reputation | Per-variant configurable thresholds plus a low-stock endpoint with a channel filter: replenishment becomes proactive instead of reactive |

A fourth problem is cross-cutting and often forgotten: **who changed what, and when.**
Without a trail, an inventory discrepancy is impossible to diagnose after the fact. The
`ConflictLog` and the audit table cover that.

---

## Verifiable impact

Everything below is backed by code and by this repository's test suite. There are no
estimated business metrics and no promises: what was implemented, with its proof.

| Capability | Evidence in the repo |
| :--- | :--- |
| The API does not block during a heavy upload | S3 → SQS → worker pattern: the request enqueues the job and returns; processing happens in the worker |
| Every stock discrepancy is recorded | `conflict_log` table with `old_qty`, `new_qty`, `loser_qty`, `variant_id`, `channel_id` |
| A file with bad rows is not lost entirely | `ImportResult` returns `total`, `ok`, `errors` and `error_rows[]` |
| Secrets are not in the codebase | AWS Secrets Manager with on-demand creation; everything else via `.env` + `pydantic-settings` |
| Runtime behaviour is observable | JSON logs with `request_id` and latency, Prometheus metrics at `/metrics`, health checks reporting DB and Redis state |
| No data changes without a trail | JWT HS256 with refresh rotation, `admin`/`operator` RBAC, immutable `ConflictLog` |
| The API cannot be abused | Global rate limit of 100 req/min per IP with `X-RateLimit-*` headers |
| External changes break nothing | 75 passing tests across 7 modules: routers, sync/import, extended auth, AWS, observability, models, health |

---

## Architecture

```
app/
├── main.py              # FastAPI + lifespan (channel and user seeding)
├── core/
│   ├── config.py        # Pydantic Settings (.env)
│   ├── security.py      # JWT + bcrypt
│   ├── deps.py          # require_admin, require_operator_or_admin
│   ├── aws.py           # Secrets Manager, S3, SQS (boto3)
│   └── logging.py       # structlog JSON with request_id
├── db/
│   └── session.py       # SQLModel engine + get_session
├── models/              # Product, Variant, Channel, InventoryLevel,
│                        # ConflictLog, ImportBatch, User
├── schemas/             # Pydantic request/response
├── routers/             # auth, products, variants, channels, inventory,
│                        # imports, alerts
├── services/
│   ├── sync.py          # Last-write-wins + ConflictLog
│   ├── importer.py      # CSV/Excel parser with column aliases
│   └── aws_sqs.py       # Asynchronous job enqueueing
└── scripts/
    └── import_csv.py    # CLI: python -m app.scripts.import_csv <file>
```

**Principles applied**

- **Separated layers:** `routers → services → models → DB`. Business logic does not live in endpoints.
- **No credentials in code:** everything via `.env` + `pydantic-settings`, or via AWS Secrets Manager.
- **Heavy work off the request path:** slow jobs go to SQS, not to a thread.
- **Versioned migrations:** Alembic against SQLModel metadata.
- **Reproducible environments:** `docker compose up` brings up API + PostgreSQL with healthchecks.

---

## AWS integrations

The integrations are implemented and covered by `tests/test_aws.py` (7 tests). LocalStack
lets all of this run locally without spending anything on AWS.

| Service | Use in this project |
| :--- | :--- |
| **Secrets Manager** | Reading credentials and configuration secrets, creating them on demand if absent |
| **SQS** | Job queue for asynchronous upload processing: decouples the request from the heavy work |
| **S3** | Persistence of uploaded files and storage of job payloads |
| **LocalStack** | AWS parity in development and tests, with no real credentials or cost |

---

## Data model

| Table | Purpose | Relevant keys |
| :--- | :--- | :--- |
| `channel` | Sales channels (amazon, shopify) | `code` UNIQUE |
| `product` | Base product | `sku_base` UNIQUE |
| `variant` | Commercial variant (size, colour, price, threshold) | `sku` UNIQUE, FK `product_id` |
| `inventory_level` | Stock per variant and channel | composite PK (`variant_id`, `channel_id`) |
| `conflict_log` | Sync discrepancy history | `old_qty`, `new_qty`, `loser_qty` |
| `import_batch` | Record of every file upload | `filename`, `total`, `ok`, `errors` |
| `user` | System users | `email` UNIQUE, `role` (`admin`/`operator`) |

**Relationships:** Product 1→N Variant · Variant 1→N InventoryLevel (per Channel) ·
Channel 1→N InventoryLevel · Variant 1→N ConflictLog

---

## API

Roles are enforced through FastAPI dependencies: `admin` writes, `operator` reads only.

### Authentication
| Method | Path | Description | Access |
| :--- | :--- | :--- | :--- |
| POST | `/auth/login` | Login, returns access + refresh token | Public |
| POST | `/auth/refresh` | Rotates the refresh token | Public |
| POST | `/auth/logout` | Revokes the refresh token | Public |
| GET | `/auth/me` | Authenticated user | Bearer |
| POST | `/auth/users/` | Create user (admin only) | Admin |
| GET | `/auth/users/` | List users | Admin |
| GET | `/auth/users/{id}` | User detail | Admin |
| PATCH | `/auth/users/{id}` | Update email, role, status or password | Admin |
| DELETE | `/auth/users/{id}` | Delete user | Admin |

### Catalogue
| Method | Path | Description | Roles |
| :--- | :--- | :--- | :--- |
| POST | `/products/` | Create product | Admin |
| GET | `/products/` | List (paginated) | Operator, Admin |
| GET | `/products/{id}` | Detail | Operator, Admin |
| DELETE | `/products/{id}` | Delete | Admin |
| POST | `/variants/` | Create variant | Admin |
| GET | `/variants/` | List with filters (`product_id`, `size`, `color`, `low_stock`) | Operator, Admin |
| GET | `/variants/{id}` | Detail with product | Operator, Admin |
| DELETE | `/variants/{id}` | Delete | Admin |
| POST | `/channels/` | Create channel | Admin |
| GET | `/channels/` | List channels | Operator, Admin |
| GET | `/channels/{id}` | Detail | Operator, Admin |
| DELETE | `/channels/{id}` | Delete | Admin |

### Inventory
| Method | Path | Description | Roles |
| :--- | :--- | :--- | :--- |
| GET | `/inventory/` | Stock (`?variant_id=&channel_code=`) | Operator, Admin |
| POST | `/inventory/sync` | Sync quantity (*last-write-wins*) | Admin |
| GET | `/alerts/low-stock` | Variants at or below their threshold | Operator, Admin |

### Imports
| Method | Path | Description | Roles |
| :--- | :--- | :--- | :--- |
| POST | `/imports/upload` | Upload file (multipart) | Admin |
| GET | `/imports/` | Upload history | Operator, Admin |
| GET | `/imports/{id}` | Upload detail with per-row errors | Operator, Admin |

### Health
| Method | Path | Description |
| :--- | :--- | :--- |
| GET | `/health` | Basic probe for the load balancer |
| GET | `/health/detailed` | Database, Redis and version state |
| GET | `/metrics` | Prometheus metrics |

---

## Stock synchronisation

**Policy:** *last-write-wins* by `updated_at` within each channel.

```bash
curl -X POST http://localhost:8000/inventory/sync \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"variant_id": 1, "channel_code": "amazon", "qty": 25}'
```

```json
{
  "variant_id": 1,
  "channel_code": "amazon",
  "qty": 25,
  "updated_at": "2026-09-24T19:00:00Z",
  "conflict_logged": true
}
```

If the quantity changed, a record is written to `conflict_log` (`conflict_logged: true`).
If the quantity is identical, no audit noise is generated (`conflict_logged: false`).

---

## CSV / Excel import

**Formats:** CSV (UTF-8, headers on the first row) and XLSX via `openpyxl`.

Providers never agree on column names, so the parser accepts aliases in both languages:

| Standard field | Accepted aliases |
| :--- | :--- |
| `sku` | SKU, Id, codigo, product_sku, variant_sku |
| `qty` | QTY, stock, Stock, cantidad, Cantidad, quantity |
| `size` | Size, talla, Talla, tamano, Tamaño |
| `color` | Color, colour, Colour |
| `price` | Price, precio, Precio, cost, Cost |
| `threshold` | Threshold, umbral, Umbral, min_stock, MinStock |
| `channel` | Channel, canal, Canal, marketplace, Marketplace |
| `product_name` | ProductName, name, Name, nombre, Nombre |
| `sku_base` | SkuBase, base_sku, BaseSKU, product_sku_base |
| `ean` | EAN, barcode, Barcode, gtin, GTIN |

**Behaviour**

1. Auto-creates `Product` and `Variant` if missing, deriving `sku_base` from the SKU.
2. Rejects rows with negative quantity, empty SKU or non-numeric price.
3. Deduplicates: if a SKU appears more than once, the last row wins.
4. Returns `ImportResult`: `batch_id`, `total`, `ok`, `errors`, `error_rows[]`.

**Example file with deliberate errors** (`data/samples/messy_sample.csv`):

```csv
SKU,Stock,Talla,Color,Precio,Umbral,Canal,ProductName,BaseSKU,EAN
TEST-001-M-RED,10,M,RED,29.99,5,amazon,Test Product,TEST-001,840000000001
TEST-002-M-GREEN,-2,M,GREEN,19.99,3,shopify,Another Product,TEST-002,840000000004
TEST-004-M-PURPLE,abc,M,PURPLE,25.00,4,shopify,Fourth Product,TEST-004,840000000006
```

Row two has negative stock and row three an invalid price. Both are reported in
`error_rows` and the rest of the batch is processed.

**Local script:** `python -m app.scripts.import_csv data/samples/messy_sample.csv`

---

## Authentication and authorisation

| Role | Permissions |
| :--- | :--- |
| `admin` | Full write: create, update, delete, sync, import |
| `operator` | Read only: list, detail, alerts |

- Access token: 60 minutes (configurable)
- Refresh token: 7 days, with automatic rotation and revocation on logout
- Passwords hashed with `bcrypt`
- Signing key and configuration secrets only via `.env`

---

## Security

**Rate limiting:** 100 req/min per IP, configurable through `RATE_LIMIT_REQUESTS` and
`RATE_LIMIT_WINDOW`. `/health` is excluded so load balancer probes are not throttled.
Responses include `X-RateLimit-Limit`, `X-RateLimit-Remaining` and `X-RateLimit-Reset`.

**Security headers (OWASP)**

| Header | Value |
| :--- | :--- |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `X-XSS-Protection` | `1; mode=block` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Content-Security-Policy` | `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'` |

**CORS:** origins configurable per environment. `*` in development; restrict to concrete
domains in production.

---

## Observability

**Structured logging (structlog)** — JSON logs with `request_id`, UTC timestamp, method,
path, status code and latency. Levels: `INFO` for requests, `WARNING` for rate limiting,
`ERROR` for exceptions.

**Prometheus metrics** (`/metrics`)

| Metric | Type | Labels |
| :--- | :--- | :--- |
| `http_requests_total` | Counter | method, endpoint, status_code |
| `http_request_duration_seconds` | Histogram | method, endpoint |
| `active_connections` | Gauge | — |
| `db_query_duration_seconds` | Histogram | operation |

**Health checks:** `/health` for the load balancer and `/health/detailed` reporting
database and Redis state. Containers carry their own `HEALTHCHECK`.

---

## Tests

**75 tests** across 7 modules:

| Module | Tests | Covers |
| :--- | :--- | :--- |
| `test_routers.py` | 29 | Product, variant and channel CRUD, pagination, filters |
| `test_inventory_sync_import.py` | 18 | *Last-write-wins* sync, `ConflictLog`, CSV import, deduplication, per-row errors |
| `test_auth_extended.py` | 9 | Login, refresh rotation, revocation, role-based access control |
| `test_aws.py` | 7 | Secrets Manager, SQS (enqueue and receive), S3 (upload and download), Redis, rate limiting |
| `test_observability.py` | 6 | Structured logging, Prometheus metrics, health checks |
| `test_models.py` | 5 | SQLModel models, constraints, relationships |
| `test_health.py` | 1 | Health probe |

```bash
# Full suite
docker compose exec api pytest -q

# With coverage
docker compose exec api pytest --cov=app --cov-report=term-missing

# Single module
docker compose exec api pytest -q tests/test_aws.py
```

---

## Continuous integration

Every push and pull request runs, as separate jobs:

1. **Lint** — `ruff check` and `ruff format --check`
2. **Tests** — `pytest` with coverage reporting
3. **Image build** — Docker image build

`pre-commit` is also configured, and the repository ships `CONTRIBUTING.md`,
`CODE_OF_CONDUCT.md` and `CHANGELOG.md`.

---

## Quick start

**Requirements:** Docker Desktop running and a terminal (Git Bash on Windows, or any Unix shell).

```bash
# 1. Clone and enter
git clone https://github.com/jerryszc/ecommerce-inventory-automator.git
cd ecommerce-inventory-automator

# 2. Configure the environment
cp .env.example .env

# 3. Bring up API + PostgreSQL
docker compose up --build -d

# 4. Verify
curl http://localhost:8000/health
# {"status":"ok","env":"dev"}

# 5. Authenticate
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=admin123!"
# {"access_token":"eyJ...","token_type":"bearer"}

# 6. Use the token
TOKEN="<access_token_from_step_5>"
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/products/

# 7. Import a file with messy data
curl -X POST http://localhost:8000/imports/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@data/samples/messy_sample.csv"

# 8. Check low-stock alerts
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/alerts/low-stock
```

**Interactive docs:** `http://localhost:8000/docs` (Swagger) and `/redoc`.

Seeded on startup, configurable through `.env`:
`admin@example.com` / `operator@example.com`.

**Tear down**

```bash
docker compose down      # Keep data
docker compose down -v   # Also drop the volume
```

### Local development without Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # point DATABASE_URL at your local PostgreSQL
alembic upgrade head
uvicorn app.main:app --reload
```

### Migrations

```bash
docker compose exec api alembic revision --autogenerate -m "description"
docker compose exec api alembic upgrade head
docker compose exec api alembic current
```

---

## Environment variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `APP_ENV` | `dev` | Runtime environment |
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@db:5432/inventory` | PostgreSQL connection string |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection for rate limiting |
| `JWT_SECRET` | `change-me-in-env` | **Change in production** |
| `JWT_ALGORITHM` | `HS256` | Signing algorithm |
| `JWT_EXPIRE_MINUTES` | `60` | Access token lifetime |
| `RATE_LIMIT_REQUESTS` | `100` | Requests per rate limit window |
| `RATE_LIMIT_WINDOW` | `60` | Rate limit window in seconds |
| `ADMIN_EMAIL` | `admin@example.com` | Seeded admin email |
| `ADMIN_PASSWORD` | `admin123!` | Seeded admin password |
| `OPERATOR_EMAIL` | `operator@example.com` | Seeded operator email |
| `OPERATOR_PASSWORD` | `operator123!` | Seeded operator password |

> Before deploying: change `JWT_SECRET`, use strong passwords, and restrict CORS origins
> to the real domains.

---

## License

MIT — free for commercial and educational use. See [LICENSE](LICENSE).
