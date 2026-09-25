import csv
import io
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Session, select

import openpyxl

from app.models import ImportBatch, Product, Variant, Channel, InventoryLevel
from app.schemas import ImportErrorRow, ImportResult


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Column alias mapping for messy CSV headers
HEADER_ALIASES = {
    "sku": ["sku", "SKU", "Id", "id", "codigo", "Código", "product_sku", "variant_sku"],
    "qty": ["qty", "QTY", "stock", "Stock", "cantidad", "Cantidad", "quantity", "Quantity"],
    "size": ["size", "Size", "talla", "Talla", "tamano", "Tamaño"],
    "color": ["color", "Color", "colour", "Colour"],
    "price": ["price", "Price", "precio", "Precio", "cost", "Cost"],
    "threshold": ["threshold", "Threshold", "umbral", "Umbral", "min_stock", "MinStock"],
    "channel": ["channel", "Channel", "canal", "Canal", "marketplace", "Marketplace"],
    "product_name": ["product_name", "ProductName", "name", "Name", "nombre", "Nombre"],
    "sku_base": ["sku_base", "SkuBase", "base_sku", "BaseSKU", "product_sku_base"],
    "ean": ["ean", "EAN", "barcode", "Barcode", "gtin", "GTIN"],
}


def _normalize_header(h: str) -> str:
    return h.strip().lower().replace(" ", "_").replace("-", "_")


def _find_column(headers: list[str], target: str) -> Optional[int]:
    aliases = [target] + HEADER_ALIASES.get(target, [])
    normalized_aliases = [_normalize_header(a) for a in aliases]
    for i, h in enumerate(headers):
        if _normalize_header(h) in normalized_aliases:
            return i
    return None


def _read_csv(file_bytes: bytes) -> list[dict]:
    text = file_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


def _read_xlsx(file_bytes: bytes) -> list[dict]:
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes))
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(h) if h else "" for h in rows[0]]
    data = []
    for row in rows[1:]:
        d = {}
        for i, val in enumerate(row):
            if i < len(headers):
                d[headers[i]] = val
        data.append(d)
    return data


def parse_file(filename: str, file_bytes: bytes) -> list[dict]:
    if filename.lower().endswith(".csv"):
        return _read_csv(file_bytes)
    elif filename.lower().endswith((".xlsx", ".xls")):
        return _read_xlsx(file_bytes)
    else:
        raise ValueError("Unsupported file format. Use CSV or XLSX.")


def import_stock(
    session: Session,
    filename: str,
    file_bytes: bytes,
    created_by: Optional[str] = None,
) -> ImportResult:
    rows = parse_file(filename, file_bytes)
    if not rows:
        return ImportResult(batch_id=0, total=0, ok=0, errors=0, error_rows=[])

    # Detect columns
    headers = list(rows[0].keys()) if rows else []
    col_sku = _find_column(headers, "sku")
    col_qty = _find_column(headers, "qty")
    col_size = _find_column(headers, "size")
    col_color = _find_column(headers, "color")
    col_price = _find_column(headers, "price")
    col_threshold = _find_column(headers, "threshold")
    col_channel = _find_column(headers, "channel")
    col_product_name = _find_column(headers, "product_name")
    col_sku_base = _find_column(headers, "sku_base")
    col_ean = _find_column(headers, "ean")

    if col_sku is None or col_qty is None:
        raise ValueError("Required columns 'sku' and 'qty' not found in file")

    batch = ImportBatch(filename=filename, total=len(rows), ok=0, errors=0, created_by=created_by)
    session.add(batch)
    session.commit()
    session.refresh(batch)

    error_rows: list[ImportErrorRow] = []

    for idx, row in enumerate(rows, start=1):
        try:
            sku = str(row[list(row.keys())[col_sku]]).strip() if row[list(row.keys())[col_sku]] else ""
            qty_raw = row[list(row.keys())[col_qty]]
            qty = int(float(str(qty_raw).strip())) if qty_raw is not None and str(qty_raw).strip() else 0

            if qty < 0:
                raise ValueError("Negative qty not allowed")

            if not sku:
                raise ValueError("Empty SKU")

            variant = session.exec(select(Variant).where(Variant.sku == sku)).first()
            if not variant:
                # Try to create product + variant from available data
                size = str(row[list(row.keys())[col_size]]).strip() if col_size is not None and row[list(row.keys())[col_size]] else None
                color = str(row[list(row.keys())[col_color]]).strip() if col_color is not None and row[list(row.keys())[col_color]] else None
                price = float(str(row[list(row.keys())[col_price]]).strip()) if col_price is not None and row[list(row.keys())[col_price]] else 0.0
                threshold = int(float(str(row[list(row.keys())[col_threshold]]).strip())) if col_threshold is not None and row[list(row.keys())[col_threshold]] else 5
                product_name = str(row[list(row.keys())[col_product_name]]).strip() if col_product_name is not None and row[list(row.keys())[col_product_name]] else sku
                sku_base = str(row[list(row.keys())[col_sku_base]]).strip() if col_sku_base is not None and row[list(row.keys())[col_sku_base]] else sku.rsplit("-", 1)[0] if "-" in sku else sku
                ean = str(row[list(row.keys())[col_ean]]).strip() if col_ean is not None and row[list(row.keys())[col_ean]] else None

                product = session.exec(select(Product).where(Product.sku_base == sku_base)).first()
                if not product:
                    product = Product(sku_base=sku_base, name=product_name)
                    session.add(product)
                    session.commit()
                    session.refresh(product)

                variant = Variant(
                    product_id=product.id,
                    sku=sku,
                    size=size,
                    color=color,
                    ean=ean,
                    price=price,
                    threshold=threshold,
                )
                session.add(variant)
                session.commit()
                session.refresh(variant)

            channel_code = "amazon"
            if col_channel is not None and row[list(row.keys())[col_channel]]:
                channel_code = str(row[list(row.keys())[col_channel]]).strip().lower()

            channel = session.exec(select(Channel).where(Channel.code == channel_code)).first()
            if not channel:
                raise ValueError(f"Channel '{channel_code}' not found")

            existing = session.exec(
                select(InventoryLevel).where(
                    InventoryLevel.variant_id == variant.id,
                    InventoryLevel.channel_id == channel.id,
                )
            ).first()

            if existing:
                existing.qty = qty
                existing.updated_at = utcnow()
                session.add(existing)
            else:
                session.add(InventoryLevel(
                    variant_id=variant.id,
                    channel_id=channel.id,
                    qty=qty,
                    updated_at=utcnow(),
                ))

            batch.ok += 1

        except Exception as e:
            batch.errors += 1
            error_rows.append(ImportErrorRow(
                row=idx,
                sku=sku if "sku" in locals() else None,
                error=str(e),
            ))

    batch.total = len(rows)
    session.add(batch)
    session.commit()

    return ImportResult(
        batch_id=batch.id,
        total=batch.total,
        ok=batch.ok,
        errors=batch.errors,
        error_rows=error_rows,
    )


def import_from_file_path(
    session: Session,
    file_path: str,
    created_by: Optional[str] = None,
) -> ImportResult:
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    return import_stock(session, file_path, file_bytes, created_by)


async def import_stock_async(
    session: Session,
    filename: str,
    file_bytes: bytes,
    created_by: Optional[str] = None,
) -> ImportResult:
    """Versión async del importador (para uso en worker)."""
    return import_stock(session, filename, file_bytes, created_by)