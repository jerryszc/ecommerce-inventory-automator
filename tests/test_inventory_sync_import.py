import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.main import app
from app.db.session import engine
from app.models import Product, Variant, Channel, InventoryLevel, ConflictLog, ImportBatch
from app.services.sync import sync_inventory
from app.services.importer import import_stock


client = TestClient(app)


def _unique_sku(base: str) -> str:
    import uuid
    return f"{base}-{uuid.uuid4().hex[:8]}"


def get_admin_token() -> str:
    """Get admin JWT token"""
    resp = client.post("/auth/login", data={"username": "admin@example.com", "password": "admin123!"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def get_operator_token() -> str:
    """Get operator JWT token"""
    resp = client.post("/auth/login", data={"username": "operator@example.com", "password": "operator123!"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def auth_header_admin() -> dict:
    return {"Authorization": f"Bearer {get_admin_token()}"}


def auth_header_operator() -> dict:
    return {"Authorization": f"Bearer {get_operator_token()}"}


class TestInventorySync:
    def test_sync_creates_new_inventory(self):
        sku = _unique_sku("SYNC")
        prod = client.post("/products/", json={"sku_base": sku, "name": "Sync Parent"}, headers=auth_header_admin()).json()
        variant_sku = _unique_sku("VSYNC")
        variant = client.post("/variants/", json={
            "product_id": prod["id"],
            "sku": variant_sku,
            "size": "M",
            "color": "RED",
            "price": 19.99,
            "threshold": 10,
        }, headers=auth_header_admin()).json()

        resp = client.post("/inventory/sync", json={
            "variant_id": variant["id"],
            "channel_code": "amazon",
            "qty": 25,
        }, headers=auth_header_admin())
        assert resp.status_code == 200
        data = resp.json()
        assert data["qty"] == 25
        assert data["conflict_logged"] is False

        # Verify in DB
        with Session(engine) as session:
            amazon = session.exec(select(Channel).where(Channel.code == "amazon")).first()
            inv = session.get(InventoryLevel, (variant["id"], amazon.id))
            assert inv is not None
            assert inv.qty == 25

    def test_sync_operator_forbidden(self):
        sku = _unique_sku("SYNCOP")
        prod = client.post("/products/", json={"sku_base": sku, "name": "Sync Parent"}, headers=auth_header_admin()).json()
        variant = client.post("/variants/", json={
            "product_id": prod["id"],
            "sku": _unique_sku("VSYNCOP"),
            "size": "M",
            "color": "RED",
            "price": 19.99,
            "threshold": 10,
        }, headers=auth_header_admin()).json()

        resp = client.post("/inventory/sync", json={
            "variant_id": variant["id"],
            "channel_code": "amazon",
            "qty": 25,
        }, headers=auth_header_operator())
        assert resp.status_code == 403

    def test_sync_updates_existing_no_conflict_log(self):
        sku = _unique_sku("SYNC2")
        prod = client.post("/products/", json={"sku_base": sku, "name": "Sync Parent 2"}, headers=auth_header_admin()).json()
        variant_sku = _unique_sku("VSYNC2")
        variant = client.post("/variants/", json={
            "product_id": prod["id"],
            "sku": variant_sku,
            "size": "L",
            "color": "BLUE",
            "price": 29.99,
            "threshold": 5,
        }, headers=auth_header_admin()).json()

        # First sync
        client.post("/inventory/sync", json={"variant_id": variant["id"], "channel_code": "amazon", "qty": 10}, headers=auth_header_admin())
        # Second sync with same qty
        resp = client.post("/inventory/sync", json={"variant_id": variant["id"], "channel_code": "amazon", "qty": 10}, headers=auth_header_admin())
        assert resp.status_code == 200
        data = resp.json()
        assert data["conflict_logged"] is False

    def test_sync_updates_different_qty_logs_conflict(self):
        sku = _unique_sku("SYNC3")
        prod = client.post("/products/", json={"sku_base": sku, "name": "Sync Parent 3"}, headers=auth_header_admin()).json()
        variant_sku = _unique_sku("VSYNC3")
        variant = client.post("/variants/", json={
            "product_id": prod["id"],
            "sku": variant_sku,
            "size": "XL",
            "color": "GREEN",
            "price": 39.99,
            "threshold": 5,
        }, headers=auth_header_admin()).json()

        # First sync
        client.post("/inventory/sync", json={"variant_id": variant["id"], "channel_code": "amazon", "qty": 10}, headers=auth_header_admin())
        # Second sync with different qty
        resp = client.post("/inventory/sync", json={"variant_id": variant["id"], "channel_code": "amazon", "qty": 20}, headers=auth_header_admin())
        assert resp.status_code == 200
        data = resp.json()
        assert data["conflict_logged"] is True

        # Verify ConflictLog
        with Session(engine) as session:
            logs = session.exec(select(ConflictLog).where(ConflictLog.variant_id == variant["id"])).all()
            assert len(logs) == 1
            assert logs[0].old_qty == 10
            assert logs[0].new_qty == 20
            assert logs[0].loser_qty == 10

    def test_sync_invalid_variant_returns_404(self):
        resp = client.post("/inventory/sync", json={"variant_id": 999999, "channel_code": "amazon", "qty": 10}, headers=auth_header_admin())
        assert resp.status_code == 404

    def test_sync_invalid_channel_returns_404(self):
        sku = _unique_sku("SYNC4")
        prod = client.post("/products/", json={"sku_base": sku, "name": "Sync Parent 4"}, headers=auth_header_admin()).json()
        variant = client.post("/variants/", json={"product_id": prod["id"], "sku": _unique_sku("VSYNC4"), "price": 10}, headers=auth_header_admin()).json()
        resp = client.post("/inventory/sync", json={"variant_id": variant["id"], "channel_code": "nonexistent", "qty": 10}, headers=auth_header_admin())
        assert resp.status_code == 404

    def test_list_inventory_with_filters(self):
        sku = _unique_sku("LIST")
        prod = client.post("/products/", json={"sku_base": sku, "name": "List Parent"}, headers=auth_header_admin()).json()
        variant = client.post("/variants/", json={"product_id": prod["id"], "sku": _unique_sku("VLIST"), "price": 10}, headers=auth_header_admin()).json()
        client.post("/inventory/sync", json={"variant_id": variant["id"], "channel_code": "amazon", "qty": 5}, headers=auth_header_admin())
        client.post("/inventory/sync", json={"variant_id": variant["id"], "channel_code": "shopify", "qty": 15}, headers=auth_header_admin())

        resp = client.get(f"/inventory/?variant_id={variant['id']}", headers=auth_header_operator())
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

        resp = client.get("/inventory/?channel_code=amazon", headers=auth_header_operator())
        assert resp.status_code == 200
        data = resp.json()
        # Get amazon channel ID dynamically
        with Session(engine) as session:
            amazon = session.exec(select(Channel).where(Channel.code == "amazon")).first()
            assert all(d["channel_id"] == amazon.id for d in data)


class TestImports:
    def test_upload_csv_creates_products_variants_inventory(self):
        csv_content = b"SKU,Stock,Talla,Color,Precio,Umbral,Canal,ProductName,BaseSKU,EAN\nTEST-IMP-001,10,M,RED,29.99,5,amazon,Import Product,TEST-IMP,840000000001\n"
        files = {"file": ("test.csv", csv_content, "text/csv")}
        resp = client.post("/imports/upload", files=files, headers=auth_header_admin())
        assert resp.status_code == 201
        data = resp.json()
        assert data["total"] == 1
        assert data["ok"] == 1
        assert data["errors"] == 0
        assert data["batch_id"] > 0

    def test_upload_csv_operator_forbidden(self):
        csv_content = b"SKU,Stock\nTEST-OP,10\n"
        files = {"file": ("op.csv", csv_content, "text/csv")}
        resp = client.post("/imports/upload", files=files, headers=auth_header_operator())
        assert resp.status_code == 403

    def test_upload_csv_handles_errors(self):
        csv_content = b"SKU,Stock\nBAD-SKU,-5\n"
        files = {"file": ("bad.csv", csv_content, "text/csv")}
        resp = client.post("/imports/upload", files=files, headers=auth_header_admin())
        assert resp.status_code == 201
        data = resp.json()
        assert data["total"] == 1
        assert data["errors"] == 1
        assert len(data["error_rows"]) == 1
        assert "Negative qty not allowed" in data["error_rows"][0]["error"]

    def test_upload_csv_duplicate_sku_deduplicates(self):
        csv_content = b"SKU,Stock\nTEST-DUP-001,10\nTEST-DUP-001,20\n"
        files = {"file": ("dup.csv", csv_content, "text/csv")}
        resp = client.post("/imports/upload", files=files, headers=auth_header_admin())
        assert resp.status_code == 201
        data = resp.json()
        assert data["ok"] == 2  # Both rows processed, second updates first
        assert data["errors"] == 0

    def test_list_imports(self):
        resp = client.get("/imports/", headers=auth_header_operator())
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_list_imports_unauthorized(self):
        resp = client.get("/imports/")
        assert resp.status_code == 401

    def test_get_import_batch(self):
        # First create an import
        csv_content = b"SKU,Stock\nTEST-GET-001,5\n"
        files = {"file": ("get.csv", csv_content, "text/csv")}
        create = client.post("/imports/upload", files=files, headers=auth_header_admin()).json()
        batch_id = create["batch_id"]

        resp = client.get(f"/imports/{batch_id}", headers=auth_header_operator())
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == batch_id
        assert data["filename"] == "get.csv"


class TestAlerts:
    def test_low_stock_alert_triggered(self):
        sku = _unique_sku("ALERT")
        prod = client.post("/products/", json={"sku_base": sku, "name": "Alert Parent"}, headers=auth_header_admin()).json()
        variant = client.post("/variants/", json={
            "product_id": prod["id"],
            "sku": _unique_sku("VALERT"),
            "size": "M",
            "color": "RED",
            "price": 15.0,
            "threshold": 10,
        }, headers=auth_header_admin()).json()
        # Sync with qty below threshold
        client.post("/inventory/sync", json={"variant_id": variant["id"], "channel_code": "amazon", "qty": 5}, headers=auth_header_admin())

        resp = client.get("/alerts/low-stock", headers=auth_header_operator())
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        alert = next(a for a in data if a["variant_id"] == variant["id"])
        assert alert["qty"] == 5
        assert alert["threshold"] == 10
        assert alert["channel_code"] == "amazon"

    def test_low_stock_alert_unauthorized(self):
        resp = client.get("/alerts/low-stock")
        assert resp.status_code == 401

    def test_low_stock_alert_not_triggered_above_threshold(self):
        sku = _unique_sku("NOALERT")
        prod = client.post("/products/", json={"sku_base": sku, "name": "No Alert Parent"}, headers=auth_header_admin()).json()
        variant = client.post("/variants/", json={
            "product_id": prod["id"],
            "sku": _unique_sku("VNOALERT"),
            "price": 15.0,
            "threshold": 5,
        }, headers=auth_header_admin()).json()
        # Sync with qty above threshold
        client.post("/inventory/sync", json={"variant_id": variant["id"], "channel_code": "amazon", "qty": 10}, headers=auth_header_admin())

        resp = client.get("/alerts/low-stock", headers=auth_header_operator())
        assert resp.status_code == 200
        data = resp.json()
        alert = next((a for a in data if a["variant_id"] == variant["id"]), None)
        assert alert is None

    def test_low_stock_alert_filter_by_channel(self):
        sku = _unique_sku("ALERTCH")
        prod = client.post("/products/", json={"sku_base": sku, "name": "Alert Channel Parent"}, headers=auth_header_admin()).json()
        variant = client.post("/variants/", json={
            "product_id": prod["id"],
            "sku": _unique_sku("VALERTCH"),
            "price": 15.0,
            "threshold": 10,
        }, headers=auth_header_admin()).json()
        client.post("/inventory/sync", json={"variant_id": variant["id"], "channel_code": "amazon", "qty": 3}, headers=auth_header_admin())
        client.post("/inventory/sync", json={"variant_id": variant["id"], "channel_code": "shopify", "qty": 20}, headers=auth_header_admin())

        resp = client.get("/alerts/low-stock?channel_code=amazon", headers=auth_header_operator())
        assert resp.status_code == 200
        data = resp.json()
        alert = next((a for a in data if a["variant_id"] == variant["id"]), None)
        assert alert is not None
        assert alert["channel_code"] == "amazon"
        assert alert["qty"] == 3

        resp = client.get("/alerts/low-stock?channel_code=shopify", headers=auth_header_operator())
        assert resp.status_code == 200
        data = resp.json()
        alert = next((a for a in data if a["variant_id"] == variant["id"]), None)
        assert alert is None  # shopify has 20 > 10