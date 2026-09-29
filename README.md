# E-Commerce Multi-Channel Inventory & Operations Automator

**[English version →](README.en.md)**

API de sincronización de inventario entre canales de venta, con procesamiento asíncrono
en AWS, control de acceso por roles y observabilidad de producción.

[![CI/CD](https://github.com/jerryszc/ecommerce-inventory-automator/actions/workflows/ci.yml/badge.svg)](https://github.com/jerryszc/ecommerce-inventory-automator/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/jerryszc/ecommerce-inventory-automator/branch/main/graph/badge.svg)](https://codecov.io/gh/jerryszc/ecommerce-inventory-automator)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141+-009688.svg)](https://fastapi.tiangolo.com/)
[![AWS](https://img.shields.io/badge/AWS-S3%20%7C%20SQS%20%7C%20Secrets%20Manager-orange.svg)](https://aws.amazon.com/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED.svg)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/tests-75%20passing-brightgreen.svg)](tests)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

**Stack:** Python 3.12 · FastAPI · SQLModel · PostgreSQL 16 · Redis · AWS (S3, SQS, Secrets Manager) · Docker · GitHub Actions

---

## El problema empresarial

Un comercio que vende en más de un marketplace enfrenta tres fallos que cuestan dinero
y horas de trabajo, y que ninguna spreadsheet resuelve:

| Problema | Costo real para el negocio | Qué lo reemplaza aquí |
| :--- | :--- | :--- |
| **Divergencia de stock entre canales.** Amazon marca 10 unidades, Shopify marca 8, y ninguno sabe cuál es el real | Sobreventa: se venden unidades que no existen. Amazon penaliza la cuenta, y cada sobreventa termina en reembolso, cancelación y pérdida de reputación | Sincronización *last-write-wins* por `updated_at`, con `ConflictLog` inmutable que registra cada discrepancia: existe una fuente de verdad y un historial auditable |
| **Carga manual de catálogos de proveedores.** Archivos CSV/Excel con nombres de columna distintos en cada proveedor, y un SKU por cada variante | Horas de trabajo por lote. Un solo archivo con un encabezado mal escrito, o una fila con cantidad negativa, bloquea la carga completa | Importador tolerante a alias de columna, auto-creación del catálogo, deduplicación y **reporte de errores por fila**: un archivo sucio procesa las filas válidas en lugar de rechazarse entero |
| **Stock bajo no detectado hasta que la venta falla.** El equipo se entera cuando ya se perdió la venta | Ingresos perdidos y reputación de disponibilidad | Umbral configurable por variante y endpoint de alertas con filtro por canal: la reposición se anticipa en lugar de reaccionar |

El cuarto problema es transversal y suele olvidarse: **quién cambió qué y cuándo.** Sin
traza, una discrepancia de inventario es imposible de diagnosticar después de que
ocurrió. El `ConflictLog` y la tabla de auditoría cubren eso.

---

## Impacto verificable

Todo lo que sigue está respaldado por código y por la suite de tests de este repositorio.
No hay métricas de negocio estimadas ni promesas: lo que se implementó, con su prueba.

| Capacidad | Evidencia en el repo |
| :--- | :--- |
| La API no se bloquea durante una carga pesada | Patrón S3 → SQS → worker: la petición encola el trabajo y retorna; el procesamiento ocurre en el worker |
| Cada discrepancia de stock queda registrada | Tabla `conflict_log` con `old_qty`, `new_qty`, `loser_qty`, `variant_id`, `channel_id` |
| Un archivo con errores no se pierde entero | `ImportResult` devuelve `total`, `ok`, `errors` y `error_rows[]` |
| Los secretos no están en el código | AWS Secrets Manager con creación bajo demanda; el resto vía `.env` + `pydantic-settings` |
| Se puede ver qué está pasando en ejecución | Logs JSON con `request_id` y latencia, métricas Prometheus en `/metrics`, health checks con estado de DB y Redis |
| Nadie cambia datos sin dejar rastro | JWT HS256 con rotación de refresh, RBAC `admin`/`operator`, `ConflictLog` inmutable |
| Nadie abusa de la API | Rate limiting global de 100 req/min por IP con headers `X-RateLimit-*` |
| Cambios ajenos no rompen nada | Suite de 75 tests en verde, 7 módulos: routers, sync/import, auth extendido, AWS, observabilidad, modelos, health |

---

## Arquitectura

```
app/
├── main.py              # FastAPI + lifespan (seed de canales y usuarios)
├── core/
│   ├── config.py        # Pydantic Settings (.env)
│   ├── security.py      # JWT + bcrypt
│   ├── deps.py          # require_admin, require_operator_or_admin
│   ├── aws.py           # Secrets Manager, S3, SQS (boto3)
│   └── logging.py       # structlog JSON con request_id
├── db/
│   └── session.py       # SQLModel engine + get_session
├── models/              # Product, Variant, Channel, InventoryLevel,
│                        # ConflictLog, ImportBatch, User
├── schemas/             # Pydantic request/response
├── routers/             # auth, products, variants, channels, inventory,
│                        # imports, alerts
├── services/
│   ├── sync.py          # Last-write-wins + ConflictLog
│   ├── importer.py      # Parser CSV/Excel con alias de columnas
│   └── aws_sqs.py       # Encolado de trabajo asíncrono
└── scripts/
    └── import_csv.py    # CLI: python -m app.scripts.import_csv <archivo>
```

**Principios aplicados**

- **Capas separadas:** `routers → services → models → DB`. La lógica de negocio no vive en los endpoints.
- **Sin credenciales en el código:** todo vía `.env` + `pydantic-settings`, o vía AWS Secrets Manager.
- **Procesos pesados fuera del request path:** el trabajo lento va a SQS, no a un thread.
- **Migraciones versionadas:** Alembic contra la metadata de SQLModel.
- **Entornos reproducibles:** `docker compose up` levanta API + PostgreSQL con healthchecks.

---

## Integraciones de AWS

Las integraciones están implementadas y cubiertas por `tests/test_aws.py` (7 tests).
LocalStack permite ejecutar todo esto en local sin gastar en AWS.

| Servicio | Uso en el proyecto |
| :--- | :--- |
| **Secrets Manager** | Lectura de credenciales y secretos de configuración, con creación bajo demanda si no existen |
| **SQS** | Cola de trabajo para el procesamiento asíncrono de cargas: desacopla el request del trabajo pesado |
| **S3** | Persistencia de archivos subidos y almacenamiento de los payloads de trabajo |
| **LocalStack** | Paridad con AWS en desarrollo y en tests, sin costo ni credenciales reales |

---

## Modelo de datos

| Tabla | Función | Claves relevantes |
| :--- | :--- | :--- |
| `channel` | Canales de venta (amazon, shopify) | `code` UNIQUE |
| `product` | Producto base | `sku_base` UNIQUE |
| `variant` | Variante comercial (talla, color, precio, umbral) | `sku` UNIQUE, FK `product_id` |
| `inventory_level` | Stock por variante y canal | PK compuesta (`variant_id`, `channel_id`) |
| `conflict_log` | Historial de discrepancias de sincronización | `old_qty`, `new_qty`, `loser_qty` |
| `import_batch` | Registro de cada carga de archivo | `filename`, `total`, `ok`, `errors` |
| `user` | Usuarios del sistema | `email` UNIQUE, `role` (`admin`/`operator`) |

**Relaciones:** Product 1→N Variant · Variant 1→N InventoryLevel (por Channel) ·
Channel 1→N InventoryLevel · Variant 1→N ConflictLog

---

## API

Todas las rutas están bajo el prefijo de la aplicación. Los roles se aplican por
dependencia de FastAPI: `admin` escribe, `operator` solo lee.

### Autenticación
| Método | Ruta | Descripción | Acceso |
| :--- | :--- | :--- | :--- |
| POST | `/auth/login` | Login, devuelve access + refresh token | Público |
| POST | `/auth/refresh` | Rota el refresh token | Público |
| POST | `/auth/logout` | Revoca el refresh token | Público |
| GET | `/auth/me` | Usuario autenticado | Bearer |
| POST | `/auth/users/` | Crear usuario (solo admin) | Admin |
| GET | `/auth/users/` | Listar usuarios | Admin |
| GET | `/auth/users/{id}` | Detalle de usuario | Admin |
| PATCH | `/auth/users/{id}` | Actualizar email, rol, estado o password | Admin |
| DELETE | `/auth/users/{id}` | Eliminar usuario | Admin |

### Catálogo
| Método | Ruta | Descripción | Roles |
| :--- | :--- | :--- | :--- |
| POST | `/products/` | Crear producto | Admin |
| GET | `/products/` | Listar (paginado) | Operator, Admin |
| GET | `/products/{id}` | Detalle | Operator, Admin |
| DELETE | `/products/{id}` | Eliminar | Admin |
| POST | `/variants/` | Crear variante | Admin |
| GET | `/variants/` | Listar con filtros (`product_id`, `size`, `color`, `low_stock`) | Operator, Admin |
| GET | `/variants/{id}` | Detalle con producto | Operator, Admin |
| DELETE | `/variants/{id}` | Eliminar | Admin |
| POST | `/channels/` | Crear canal | Admin |
| GET | `/channels/` | Listar canales | Operator, Admin |
| GET | `/channels/{id}` | Detalle | Operator, Admin |
| DELETE | `/channels/{id}` | Eliminar | Admin |

### Inventario
| Método | Ruta | Descripción | Roles |
| :--- | :--- | :--- | :--- |
| GET | `/inventory/` | Stock (`?variant_id=&channel_code=`) | Operator, Admin |
| POST | `/inventory/sync` | Sincroniza cantidad (*last-write-wins*) | Admin |
| GET | `/alerts/low-stock` | Variantes en o por debajo de su umbral | Operator, Admin |

### Importación
| Método | Ruta | Descripción | Roles |
| :--- | :--- | :--- | :--- |
| POST | `/imports/upload` | Subir archivo (multipart) | Admin |
| GET | `/imports/` | Historial de cargas | Operator, Admin |
| GET | `/imports/{id}` | Detalle de carga con errores por fila | Operator, Admin |

### Salud
| Método | Ruta | Descripción |
| :--- | :--- | :--- |
| GET | `/health` | Sonda básica para balanceador |
| GET | `/health/detailed` | Estado de base de datos, Redis y versión |
| GET | `/metrics` | Métricas Prometheus |

---

## Sincronización de stock

**Política:** *last-write-wins* por `updated_at` dentro de cada canal.

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

Si la cantidad cambió, se escribe el registro en `conflict_log` (`conflict_logged: true`).
Si la cantidad es idéntica, no se genera ruido en la auditoría (`conflict_logged: false`).

---

## Importación de CSV / Excel

**Formatos:** CSV (UTF-8, encabezados en la primera fila) y XLSX vía `openpyxl`.

Los proveedores no coinciden en los nombres de las columnas, así que el parser acepta
alias en ambos idiomas:

| Campo estándar | Aliases aceptados |
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

**Comportamiento**

1. Auto-crea `Product` y `Variant` si no existen, derivando `sku_base` del SKU.
2. Rechaza filas con cantidad negativa, SKU vacío o precio no numérico.
3. Deduplica: si un SKU aparece varias veces, gana la última fila.
4. Responde con `ImportResult`: `batch_id`, `total`, `ok`, `errors`, `error_rows[]`.

**Ejemplo de archivo con errores deliberados** (`data/samples/messy_sample.csv`):

```csv
SKU,Stock,Talla,Color,Precio,Umbral,Canal,ProductName,BaseSKU,EAN
TEST-001-M-RED,10,M,RED,29.99,5,amazon,Test Product,TEST-001,840000000001
TEST-002-M-GREEN,-2,M,GREEN,19.99,3,shopify,Another Product,TEST-002,840000000004
TEST-004-M-PURPLE,abc,M,PURPLE,25.00,4,shopify,Fourth Product,TEST-004,840000000006
```

La segunda fila tiene stock negativo y la tercera un precio inválido. Ambas se reportan
en `error_rows` y el resto del lote se procesa.

**Script local:** `python -m app.scripts.import_csv data/samples/messy_sample.csv`

---

## Autenticación y autorización

| Rol | Permisos |
| :--- | :--- |
| `admin` | Escritura total: crear, actualizar, eliminar, sincronizar, importar |
| `operator` | Solo lectura: listar, ver detalle, consultar alertas |

- Access token: 60 minutos (configurable)
- Refresh token: 7 días, con rotación automática y revocación en el logout
- Contraseñas con `bcrypt`
- Secretos de firma y configuración únicamente por `.env`

---

## Seguridad

**Rate limiting:** 100 req/min por IP, configurable con `RATE_LIMIT_REQUESTS` y
`RATE_LIMIT_WINDOW`. Se excluye `/health` para no penalizar las sondas del balanceador.
La respuesta incluye `X-RateLimit-Limit`, `X-RateLimit-Remaining` y `X-RateLimit-Reset`.

**Cabeceras de seguridad (OWASP)**

| Cabecera | Valor |
| :--- | :--- |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `X-XSS-Protection` | `1; mode=block` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Content-Security-Policy` | `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'` |

**CORS:** orígenes configurables por entorno. En desarrollo se permite `*`; en producción
se restringen los dominios concretos.

---

## Observabilidad

**Logging estructurado (structlog)** — logs JSON con `request_id`, timestamp UTC, método,
ruta, código de estado y latencia. Niveles: `INFO` para peticiones, `WARNING` para rate
limit, `ERROR` para excepciones.

**Métricas Prometheus** (`/metrics`)

| Métrica | Tipo | Etiquetas |
| :--- | :--- | :--- |
| `http_requests_total` | Counter | method, endpoint, status_code |
| `http_request_duration_seconds` | Histogram | method, endpoint |
| `active_connections` | Gauge | — |
| `db_query_duration_seconds` | Histogram | operation |

**Health checks:** `/health` para el balanceador y `/health/detailed` que reporta el estado
de la base de datos y de Redis. Los contenedores usan `HEALTHCHECK` propio.

---

## Pruebas

**75 tests** distribuidos en 7 módulos:

| Módulo | Tests | Cubre |
| :--- | :--- | :--- |
| `test_routers.py` | 29 | CRUD de productos, variantes y canales, paginación, filtros |
| `test_inventory_sync_import.py` | 18 | Sincronización *last-write-wins*, `ConflictLog`, importación CSV, deduplicación, errores por fila |
| `test_auth_extended.py` | 9 | Login, rotación de refresh, revocación, control de acceso por rol |
| `test_aws.py` | 7 | Secrets Manager, SQS (encolar y recibir), S3 (subir y descargar), Redis, rate limiting |
| `test_observability.py` | 6 | Logging estructurado, métricas Prometheus, health checks |
| `test_models.py` | 5 | Modelos SQLModel, constraints, relaciones |
| `test_health.py` | 1 | Sonda de salud |

```bash
# Suite completa
docker compose exec api pytest -q

# Con cobertura
docker compose exec api pytest --cov=app --cov-report=term-missing

# Módulo específico
docker compose exec api pytest -q tests/test_aws.py
```

---

## Integración continua

Cada push y cada pull request ejecutan, en jobs separados:

1. **Lint** — `ruff check` y `ruff format --check`
2. **Tests** — `pytest` con reporte de cobertura
3. **Build de imagen** — construcción de la imagen Docker

Además hay `pre-commit` configurado, y el repositorio incluye `CONTRIBUTING.md`,
`CODE_OF_CONDUCT.md` y `CHANGELOG.md`.

---

## Puesta en marcha

**Requisitos:** Docker Desktop en ejecución y una terminal (Git Bash en Windows o cualquier shell Unix).

```bash
# 1. Clonar y entrar
git clone https://github.com/jerryszc/ecommerce-inventory-automator.git
cd ecommerce-inventory-automator

# 2. Configurar entorno
cp .env.example .env

# 3. Levantar API + PostgreSQL
docker compose up --build -d

# 4. Verificar
curl http://localhost:8000/health
# {"status":"ok","env":"dev"}

# 5. Autenticarse
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=admin123!"
# {"access_token":"eyJ...","token_type":"bearer"}

# 6. Usar el token
TOKEN="<access_token_del_paso_5>"
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/products/

# 7. Importar un archivo con datos sucios
curl -X POST http://localhost:8000/imports/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@data/samples/messy_sample.csv"

# 8. Consultar alertas de stock bajo
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/alerts/low-stock
```

**Documentación interactiva:** `http://localhost:8000/docs` (Swagger) y `/redoc`.

Usuarios creados en el arranque, configurables en `.env`:
`admin@example.com` / `operator@example.com`.

**Detener el entorno**

```bash
docker compose down      # Conserva los datos
docker compose down -v   # Elimina también el volumen
```

### Desarrollo local sin Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # ajustar DATABASE_URL a tu PostgreSQL local
alembic upgrade head
uvicorn app.main:app --reload
```

### Migraciones

```bash
docker compose exec api alembic revision --autogenerate -m "descripcion"
docker compose exec api alembic upgrade head
docker compose exec api alembic current
```

---

## Variables de entorno

| Variable | Por defecto | Descripción |
| :--- | :--- | :--- |
| `APP_ENV` | `dev` | Entorno de ejecución |
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@db:5432/inventory` | Cadena de conexión a PostgreSQL |
| `REDIS_URL` | `redis://redis:6379/0` | Conexión a Redis para rate limiting |
| `JWT_SECRET` | `change-me-in-env` | **Cambiar en producción** |
| `JWT_ALGORITHM` | `HS256` | Algoritmo de firma |
| `JWT_EXPIRE_MINUTES` | `60` | Vigencia del access token |
| `RATE_LIMIT_REQUESTS` | `100` | Requests por ventana de rate limit |
| `RATE_LIMIT_WINDOW` | `60` | Segundos de la ventana de rate limit |
| `ADMIN_EMAIL` | `admin@example.com` | Email del usuario admin inicial |
| `ADMIN_PASSWORD` | `admin123!` | Password del usuario admin inicial |
| `OPERATOR_EMAIL` | `operator@example.com` | Email del usuario operator inicial |
| `OPERATOR_PASSWORD` | `operator123!` | Password del usuario operator inicial |

> Antes de desplegar: cambia `JWT_SECRET`, usa contraseñas fuertes, y restringe los
> orígenes CORS a los dominios reales.

---

## Licencia

MIT — uso libre comercial y educativo. Ver [LICENSE](LICENSE).
