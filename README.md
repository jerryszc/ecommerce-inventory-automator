# E-Commerce Multi-Channel Inventory & Operations Automator

> **SOP (Standard Operating Procedure)** — Guía para fundadores no técnicos y equipo técnico.
> **Versión:** 1.0 | **Stack:** Python 3.12, FastAPI, PostgreSQL 16, SQLModel, Alembic, Docker Compose

---

## 📋 Tabla de Contenidos / Table of Contents

1. [Demo Rápida 5 min / Quick 5-min Demo](#demo-rápida-5-min--quick-5-min-demo)
2. [Arquitectura / Architecture](#arquitectura--architecture)
3. [Modelo de Datos / Data Model](#modelo-de-datos--data-model)
4. [Endpoints API](#endpoints-api)
5. [Autenticación y Roles / Auth & Roles](#autenticación-y-roles--auth--roles)
6. [Importación CSV/Excel / CSV/Excel Import](#importación-csvexcel--csvexcel-import)
7. [Sincronización de Stock / Stock Sync](#sincronización-de-stock--stock-sync)
8. [Alertas de Stock Bajo / Low Stock Alerts](#alertas-de-stock-bajo--low-stock-alerts)
9. [Desarrollo Local / Local Development](#desarrollo-local--local-development)
10. [Tests / Testing](#tests--testing)
11. [Variables de Entorno / Environment Variables](#variables-de-entorno--environment-variables)
12. [Solución de Problemas / Troubleshooting](#solución-de-problemas--troubleshooting)

---

## 🚀 Demo Rápida 5 min / Quick 5-min Demo

### Prerrequisitos / Prerequisites
- Docker Desktop instalado y corriendo / Docker Desktop installed & running
- Git Bash (Windows) o terminal Unix / Git Bash (Windows) or Unix terminal

### Pasos / Steps

```bash
# 1. Clonar y entrar al proyecto
git clone <repo-url> && cd Proyecto4

# 2. Copiar variables de entorno
cp .env.example .env

# 3. Levantar stack completo (API + PostgreSQL)
docker compose up --build -d

# 4. Verificar salud
curl http://localhost:8000/health
# {"status":"ok","env":"dev"}

# 5. Login como admin
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=admin123!"
# {"access_token":"eyJ...","token_type":"bearer"}

# 6. Usar token en requests posteriores
TOKEN="<access_token_del_paso_5>"
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/products/

# 7. Importar CSV de prueba (datos sucios incluidos)
curl -X POST http://localhost:8000/imports/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@data/samples/messy_sample.csv"

# 8. Ver alertas de stock bajo
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/alerts/low-stock
```

✅ **¡Listo!** Tienes un sistema multi-canal funcionando con autenticación, importación, sincronización y alertas.

---

## 🏗️ Arquitectura / Architecture

```
proyecto4/
├── app/
│   ├── main.py              # FastAPI app + lifespan (seed channels/users)
│   ├── core/
│   │   ├── config.py        # Pydantic Settings (.env)
│   │   ├── security.py      # JWT + bcrypt
│   │   └── deps.py          # Dependencias auth (require_admin, require_operator_or_admin)
│   ├── db/
│   │   └── session.py       # SQLModel engine + get_session
│   ├── models/              # SQLModel tables (Product, Variant, Channel, InventoryLevel, ConflictLog, ImportBatch, User)
│   ├── schemas/             # Pydantic request/response models
│   ├── routers/             # API endpoints (auth, products, variants, channels, inventory, imports, alerts)
│   ├── services/
│   │   ├── sync.py          # Last-write-wins + ConflictLog
│   │   └── importer.py      # CSV/Excel parser con alias de columnas
│   └── scripts/
│       └── import_csv.py    # CLI local: python -m app.scripts.import_csv <file>
├── alembic/                 # Migraciones DB
├── data/samples/            # CSV de prueba (messy_sample.csv)
├── tests/                   # pytest suite (53 tests)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

**Principios / Principles:**
- **Capas separadas**: routers → services → models → DB
- **Sin credenciales hardcodeadas**: todo via `.env` + `pydantic-settings`
- **Contenedorizado**: `docker compose up` levanta API + DB con healthchecks
- **Migraciones versionadas**: Alembic + SQLModel metadata

---

## 🗄️ Modelo de Datos / Data Model

| Tabla | Descripción | Claves |
|-------|-------------|--------|
| `channel` | Canales de venta (amazon, shopify) | `code` UNIQUE |
| `product` | Producto base | `sku_base` UNIQUE |
| `variant` | Variante (talla, color, precio, umbral) | `sku` UNIQUE, FK `product_id` |
| `inventory_level` | Stock por variante/canal | PK compuesta (`variant_id`, `channel_id`) |
| `conflict_log` | Historial de conflictos sync (last-write-wins) | `variant_id`, `channel_id`, `old_qty`, `new_qty`, `loser_qty` |
| `import_batch` | Registro de cada carga CSV/Excel | `filename`, `total`, `ok`, `errors` |
| `user` | Usuarios con roles | `email` UNIQUE, `role` (admin/operator) |

**Relaciones clave:**
- Product 1→N Variant
- Variant 1→N InventoryLevel (por Channel)
- Channel 1→N InventoryLevel
- Variant 1→N ConflictLog

---

## 🔌 Endpoints API

### Auth
| Método | Ruta | Descripción | Auth |
|--------|------|-------------|------|
| POST | `/auth/login` | Login → JWT | Público |
| GET | `/auth/me` | Usuario actual | Bearer |

### Products (CRUD)
| Método | Ruta | Descripción | Roles |
|--------|------|-------------|-------|
| POST | `/products/` | Crear producto | Admin |
| GET | `/products/` | Listar (paginado) | Operator, Admin |
| GET | `/products/{id}` | Detalle | Operator, Admin |
| DELETE | `/products/{id}` | Eliminar | Admin |

### Variants (CRUD + filtros)
| Método | Ruta | Descripción | Roles |
|--------|------|-------------|-------|
| POST | `/variants/` | Crear variante | Admin |
| GET | `/variants/` | Listar (`?product_id=&size=&color=&low_stock=`) | Operator, Admin |
| GET | `/variants/{id}` | Detalle + producto | Operator, Admin |
| DELETE | `/variants/{id}` | Eliminar | Admin |

### Channels (CRUD)
| Método | Ruta | Descripción | Roles |
|--------|------|-------------|-------|
| POST | `/channels/` | Crear canal | Admin |
| GET | `/channels/` | Listar | Operator, Admin |
| GET | `/channels/{id}` | Detalle | Operator, Admin |
| DELETE | `/channels/{id}` | Eliminar | Admin |

### Inventory Sync
| Método | Ruta | Descripción | Roles |
|--------|------|-------------|-------|
| GET | `/inventory/` | Stock (`?variant_id=&channel_code=`) | Operator, Admin |
| POST | `/inventory/sync` | Sync qty (last-write-wins) | Admin |

### Imports (CSV/Excel)
| Método | Ruta | Descripción | Roles |
|--------|------|-------------|-------|
| POST | `/imports/upload` | Subir archivo (multipart) | Admin |
| GET | `/imports/` | Historial batches | Operator, Admin |
| GET | `/imports/{id}` | Detalle batch + errores | Operator, Admin |

**Script local:** `python -m app.scripts.import_csv data/samples/messy_sample.csv`

### Alerts
| Método | Ruta | Descripción | Roles |
|--------|------|-------------|-------|
| GET | `/alerts/low-stock` | Variantes con `qty <= threshold` | Operator, Admin |

---

## 🔐 Autenticación y Roles / Auth & Roles

| Rol | Permisos |
|-----|----------|
| **admin** | Escritura total (create/update/delete), sync, imports |
| **operator** | Solo lectura (list/get), alerts |

**Usuarios seed (configurables en `.env`):**
- `admin@example.com` / `admin123!` → role=admin
- `operator@example.com` / `operator123!` → role=operator

**Flujo:**
1. `POST /auth/login` con `username` (email) + `password` → `access_token`
2. Header `Authorization: Bearer <token>` en cada request
3. Dependencias FastAPI validan rol automáticamente

---

## 📥 Importación CSV/Excel / CSV/Excel Import

### Formato soportado
- **CSV** (UTF-8, headers en primera fila)
- **XLSX** (openpyxl)

### Columnas detectadas (alias tolerantes)
| Campo estándar | Aliases aceptados |
|----------------|-------------------|
| `sku` | SKU, Id, codigo, product_sku, variant_sku |
| `qty` | QTY, stock, Stock, cantidad, Cantidad, quantity |
| `size` | Size, talla, Talla, tamaño, Tamaño |
| `color` | Color, colour, Colour |
| `price` | Price, precio, Precio, cost, Cost |
| `threshold` | Threshold, umbral, Umbral, min_stock, MinStock |
| `channel` | Channel, canal, Canal, marketplace, Marketplace |
| `product_name` | ProductName, name, Name, nombre, Nombre |
| `sku_base` | SkuBase, base_sku, BaseSKU, product_sku_base |
| `ean` | EAN, barcode, Barcode, gtin, GTIN |

### Comportamiento
1. **Auto-crea** Product + Variant si no existen (usa `sku_base` derivado del SKU)
2. **Rechaza** filas con `qty < 0`, SKU vacío, precio no numérico
3. **Deduplicación**: última fila por SKU gana (actualiza stock)
4. **Respuesta**: `ImportResult` con `batch_id`, `total`, `ok`, `errors`, `error_rows[]`

### Ejemplo `messy_sample.csv` (incluye errores a propósito)
```csv
SKU,Stock,Talla,Color,Precio,Umbral,Canal,ProductName,BaseSKU,EAN
TEST-001-M-RED,10,M,RED,29.99,5,amazon,Test Product,TEST-001,840000000001
TEST-002-M-GREEN,-2,M,GREEN,19.99,3,shopify,Another Product,TEST-002,840000000004
TEST-004-M-PURPLE,abc,M,PURPLE,25.00,4,shopify,Fourth Product,TEST-004,840000000006
```

---

## 🔄 Sincronización de Stock / Stock Sync

**Política:** **Last-Write-Wins** por `updated_at` por canal.

```bash
# Sincronizar stock
curl -X POST http://localhost:8000/inventory/sync \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"variant_id": 1, "channel_code": "amazon", "qty": 25}'
```

**Respuesta:**
```json
{
  "variant_id": 1,
  "channel_code": "amazon",
  "qty": 25,
  "updated_at": "2026-09-24T19:00:00Z",
  "conflict_logged": false
}
```

- Si `qty` cambió → se escribe en `conflict_log` (`conflict_logged: true`)
- Si `qty` igual → no hay log (`conflict_logged: false`)

---

## ⚠️ Alertas de Stock Bajo / Low Stock Alerts

```bash
# Todas las alertas
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/alerts/low-stock

# Filtrar por canal
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/alerts/low-stock?channel_code=amazon"
```

**Respuesta:**
```json
[
  {
    "variant_id": 1,
    "variant_sku": "TEST-001-M-RED",
    "product_name": "Test Product",
    "size": "M",
    "color": "RED",
    "channel_code": "amazon",
    "qty": 3,
    "threshold": 10
  }
]
```

**Regla:** `InventoryLevel.qty <= Variant.threshold` (umbral por variante, default 5).

---

## 🛠️ Desarrollo Local / Local Development

### Con Docker (recomendado)
```bash
docker compose up --build -d
docker compose logs -f api
docker compose exec api pytest -q
```

### Sin Docker (requiere PostgreSQL local)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Editar .env con DATABASE_URL local
alembic upgrade head
uvicorn app.main:app --reload
```

### Migraciones
```bash
# Crear migración tras cambios en modelos
docker compose exec api alembic revision --autogenerate -m "descripcion"

# Aplicar
docker compose exec api alembic upgrade head

# Ver estado
docker compose exec api alembic current
```

---

## 🧪 Tests / Testing

```bash
# Suite completa
docker compose exec api pytest -q

# Solo tests de routers
docker compose exec api pytest -q tests/test_routers.py

# Solo tests de sync/import/alerts
docker compose exec api pytest -q tests/test_inventory_sync_import.py

# Con coverage
docker compose exec api pytest --cov=app --cov-report=term-missing
```

**Cobertura actual:** 53 tests (health, models, CRUD, auth, sync, import, alerts)

---

## ⚙️ Variables de Entorno / Environment Variables

| Variable | Default | Descripción |
|----------|---------|-------------|
| `APP_ENV` | `dev` | Entorno |
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@db:5432/inventory` | Conexión PG |
| `JWT_SECRET` | `change-me-in-env` | **Cambiar en producción** |
| `JWT_ALGORITHM` | `HS256` | Algoritmo JWT |
| `JWT_EXPIRE_MINUTES` | `60` | Expiración token |
| `ADMIN_EMAIL` | `admin@example.com` | Email admin seed |
| `ADMIN_PASSWORD` | `admin123!` | Pass admin seed |
| `OPERATOR_EMAIL` | `operator@example.com` | Email operator seed |
| `OPERATOR_PASSWORD` | `operator123!` | Pass operator seed |

> ⚠️ **Producción:** Cambia `JWT_SECRET`, usa contraseñas fuertes, PostgreSQL managed, HTTPS/TLS.

---

## 🐛 Solución de Problemas / Troubleshooting

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| `docker compose up` falla "npipe" | Docker Desktop no corriendo | Iniciar Docker Desktop |
| `alembic check` falla "host db" | Ejecutado fuera de red Docker | Usar `docker compose exec api alembic ...` |
| `401 Unauthorized` en tests | Token expirado o mal formado | Re-login: `POST /auth/login` |
| `403 Forbidden` en write | Usuario es operator | Usar credenciales admin |
| `psycopg.OperationalError` | DB no lista | Esperar healthcheck `pg_isready` |
| CSV import 0 OK | Headers no detectados | Verificar aliases en `HEADER_ALIASES` |
| `ValueError: Datetime values must have timezone` | `datetime.utcnow()` obsoleto | Usar `datetime.now(timezone.utc)` |

---

## 📝 Licencia / License

MIT — Uso libre para fines comerciales y educativos.

---

## 🤝 Contribución / Contributing

1. Fork → feature branch → PR
2. `pytest -q` + `docker compose up --build` pasan
3. Actualizar README si cambias endpoints/modelos

---

**Última actualización:** 2026-09-24 | **Versión API:** v1 | **Stack:** Python 3.12, FastAPI 0.141, PostgreSQL 16, SQLModel 0.0.47