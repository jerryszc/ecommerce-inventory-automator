import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.main import app
from app.db.session import engine
from app.models import Product, Variant, Channel, User
from app.core.security import hash_password


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


class TestAuth:
    def test_admin_login(self):
        resp = client.post("/auth/login", data={"username": "admin@example.com", "password": "admin123!"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_operator_login(self):
        resp = client.post("/auth/login", data={"username": "operator@example.com", "password": "operator123!"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data

    def test_invalid_login(self):
        resp = client.post("/auth/login", data={"username": "admin@example.com", "password": "wrong"})
        assert resp.status_code == 401

    def test_me_endpoint(self):
        resp = client.get("/auth/me", headers=auth_header_admin())
        assert resp.status_code == 200
        assert resp.json()["email"] == "admin@example.com"
        assert resp.json()["role"] == "admin"


class TestProductsCRUD:
    def test_create_product(self):
        sku = _unique_sku("PROD")
        resp = client.post("/products/", json={"sku_base": sku, "name": "Test Product"}, headers=auth_header_admin())
        assert resp.status_code == 201
        data = resp.json()
        assert data["sku_base"] == sku
        assert data["name"] == "Test Product"
        assert "id" in data
        assert "created_at" in data

    def test_create_product_operator_forbidden(self):
        sku = _unique_sku("OPFORB")
        resp = client.post("/products/", json={"sku_base": sku, "name": "Op Forbidden"}, headers=auth_header_operator())
        assert resp.status_code == 403

    def test_create_product_duplicate_sku_fails(self):
        sku = _unique_sku("DUP")
        client.post("/products/", json={"sku_base": sku, "name": "First"}, headers=auth_header_admin())
        resp = client.post("/products/", json={"sku_base": sku, "name": "Second"}, headers=auth_header_admin())
        assert resp.status_code == 400

    def test_list_products(self):
        sku = _unique_sku("LIST")
        create_resp = client.post("/products/", json={"sku_base": sku, "name": "List Test"}, headers=auth_header_admin())
        pid = create_resp.json()["id"]
        resp = client.get("/products/", headers=auth_header_operator())
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Verify created product is accessible via GET by ID
        get_resp = client.get(f"/products/{pid}", headers=auth_header_operator())
        assert get_resp.status_code == 200
        assert get_resp.json()["sku_base"] == sku

    def test_list_products_unauthorized(self):
        resp = client.get("/products/")
        assert resp.status_code == 401

    def test_get_product(self):
        sku = _unique_sku("GET")
        create = client.post("/products/", json={"sku_base": sku, "name": "Get Test"}, headers=auth_header_admin())
        pid = create.json()["id"]
        resp = client.get(f"/products/{pid}", headers=auth_header_operator())
        assert resp.status_code == 200
        assert resp.json()["sku_base"] == sku

    def test_get_product_not_found(self):
        resp = client.get("/products/999999", headers=auth_header_operator())
        assert resp.status_code == 404

    def test_delete_product(self):
        sku = _unique_sku("DEL")
        create = client.post("/products/", json={"sku_base": sku, "name": "Delete Me"}, headers=auth_header_admin())
        pid = create.json()["id"]
        resp = client.delete(f"/products/{pid}", headers=auth_header_admin())
        assert resp.status_code == 204
        assert client.get(f"/products/{pid}", headers=auth_header_operator()).status_code == 404

    def test_delete_product_operator_forbidden(self):
        sku = _unique_sku("DELOP")
        create = client.post("/products/", json={"sku_base": sku, "name": "Delete Me"}, headers=auth_header_admin())
        pid = create.json()["id"]
        resp = client.delete(f"/products/{pid}", headers=auth_header_operator())
        assert resp.status_code == 403


class TestVariantsCRUD:
    def test_create_variant(self):
        sku = _unique_sku("VAR")
        prod = client.post("/products/", json={"sku_base": sku, "name": "Var Parent"}, headers=auth_header_admin()).json()
        variant_sku = _unique_sku("VSKU")
        resp = client.post("/variants/", json={
            "product_id": prod["id"],
            "sku": variant_sku,
            "size": "M",
            "color": "RED",
            "price": 19.99,
            "threshold": 10,
        }, headers=auth_header_admin())
        assert resp.status_code == 201
        data = resp.json()
        assert data["sku"] == variant_sku
        assert data["size"] == "M"
        assert data["color"] == "RED"
        assert data["price"] == 19.99
        assert data["threshold"] == 10

    def test_create_variant_operator_forbidden(self):
        sku = _unique_sku("VAROP")
        prod = client.post("/products/", json={"sku_base": sku, "name": "Var Parent"}, headers=auth_header_admin()).json()
        resp = client.post("/variants/", json={
            "product_id": prod["id"],
            "sku": _unique_sku("VOP"),
            "price": 10,
        }, headers=auth_header_operator())
        assert resp.status_code == 403

    def test_create_variant_invalid_product_fails(self):
        resp = client.post("/variants/", json={
            "product_id": 999999,
            "sku": _unique_sku("BAD"),
            "price": 10,
        }, headers=auth_header_admin())
        assert resp.status_code == 404

    def test_create_variant_duplicate_sku_fails(self):
        sku = _unique_sku("VARDUP")
        prod = client.post("/products/", json={"sku_base": sku, "name": "Dup Parent"}, headers=auth_header_admin()).json()
        vsku = _unique_sku("VDUP")
        client.post("/variants/", json={"product_id": prod["id"], "sku": vsku, "price": 10}, headers=auth_header_admin())
        resp = client.post("/variants/", json={"product_id": prod["id"], "sku": vsku, "price": 20}, headers=auth_header_admin())
        assert resp.status_code == 400

    def test_list_variants_with_filters(self):
        sku = _unique_sku("VFILT")
        prod = client.post("/products/", json={"sku_base": sku, "name": "Filter Parent"}, headers=auth_header_admin()).json()
        client.post("/variants/", json={"product_id": prod["id"], "sku": _unique_sku("V1"), "size": "M", "color": "RED", "price": 10}, headers=auth_header_admin())
        client.post("/variants/", json={"product_id": prod["id"], "sku": _unique_sku("V2"), "size": "L", "color": "BLUE", "price": 20}, headers=auth_header_admin())
        resp = client.get("/variants/?size=M", headers=auth_header_operator())
        assert resp.status_code == 200
        data = resp.json()
        assert all(v["size"] == "M" for v in data)

    def test_get_variant_with_product(self):
        sku = _unique_sku("VGET")
        prod = client.post("/products/", json={"sku_base": sku, "name": "Get Variant Parent"}, headers=auth_header_admin()).json()
        vsku = _unique_sku("VG")
        create = client.post("/variants/", json={"product_id": prod["id"], "sku": vsku, "size": "S", "price": 15}, headers=auth_header_admin())
        vid = create.json()["id"]
        resp = client.get(f"/variants/{vid}", headers=auth_header_operator())
        assert resp.status_code == 200
        data = resp.json()
        assert data["sku"] == vsku
        assert "product" in data
        assert data["product"]["id"] == prod["id"]

    def test_delete_variant(self):
        sku = _unique_sku("VDEL")
        prod = client.post("/products/", json={"sku_base": sku, "name": "Del Parent"}, headers=auth_header_admin()).json()
        vsku = _unique_sku("VD")
        create = client.post("/variants/", json={"product_id": prod["id"], "sku": vsku, "price": 10}, headers=auth_header_admin())
        vid = create.json()["id"]
        resp = client.delete(f"/variants/{vid}", headers=auth_header_admin())
        assert resp.status_code == 204
        assert client.get(f"/variants/{vid}", headers=auth_header_operator()).status_code == 404

    def test_delete_variant_operator_forbidden(self):
        sku = _unique_sku("VDELOP")
        prod = client.post("/products/", json={"sku_base": sku, "name": "Del Parent"}, headers=auth_header_admin()).json()
        vsku = _unique_sku("VDOP")
        create = client.post("/variants/", json={"product_id": prod["id"], "sku": vsku, "price": 10}, headers=auth_header_admin())
        vid = create.json()["id"]
        resp = client.delete(f"/variants/{vid}", headers=auth_header_operator())
        assert resp.status_code == 403


class TestChannelsCRUD:
    def test_list_channels_seeded(self):
        resp = client.get("/channels/", headers=auth_header_operator())
        assert resp.status_code == 200
        data = resp.json()
        codes = {c["code"] for c in data}
        assert "amazon" in codes
        assert "shopify" in codes

    def test_list_channels_unauthorized(self):
        resp = client.get("/channels/")
        assert resp.status_code == 401

    def test_create_channel(self):
        import uuid
        code = f"etsy-{uuid.uuid4().hex[:8]}"
        resp = client.post("/channels/", json={"code": code, "name": "Etsy"}, headers=auth_header_admin())
        assert resp.status_code == 201
        assert resp.json()["code"] == code

    def test_create_channel_operator_forbidden(self):
        resp = client.post("/channels/", json={"code": "newchan", "name": "New"}, headers=auth_header_operator())
        assert resp.status_code == 403

    def test_create_channel_duplicate_fails(self):
        resp = client.post("/channels/", json={"code": "amazon", "name": "Amazon Dup"}, headers=auth_header_admin())
        assert resp.status_code == 400

    def test_get_channel(self):
        resp = client.get("/channels/", headers=auth_header_operator())
        chan = resp.json()[0]
        cid = chan["id"]
        resp = client.get(f"/channels/{cid}", headers=auth_header_operator())
        assert resp.status_code == 200
        assert resp.json()["code"] == chan["code"]

    def test_delete_channel(self):
        resp = client.post("/channels/", json={"code": "testdel", "name": "To Delete"}, headers=auth_header_admin())
        cid = resp.json()["id"]
        assert client.delete(f"/channels/{cid}", headers=auth_header_admin()).status_code == 204
        assert client.get(f"/channels/{cid}", headers=auth_header_operator()).status_code == 404

    def test_delete_channel_operator_forbidden(self):
        import uuid
        code = f"testdel2-{uuid.uuid4().hex[:8]}"
        resp = client.post("/channels/", json={"code": code, "name": "To Delete 2"}, headers=auth_header_admin())
        cid = resp.json()["id"]
        resp = client.delete(f"/channels/{cid}", headers=auth_header_operator())
        assert resp.status_code == 403