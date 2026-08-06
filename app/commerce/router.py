from fastapi import APIRouter, Depends, Query
from typing import Optional

from app.auth.dependencies import require_auth
from app.core.database import get_cursor
from . import service

router = APIRouter(prefix="/commerce", tags=["commerce"])


# ── Companies ──────────────────────────────────────────────

@router.get("/company")
def get_company(user=Depends(require_auth), cursor=Depends(get_cursor)):
    return service.get_my_company(cursor, user["id"])


@router.post("/company")
def create_company(data: dict, user=Depends(require_auth), cursor=Depends(get_cursor)):
    return service.create_company(cursor, user["id"], data)


# ── Store ──────────────────────────────────────────────────

@router.get("/store")
def get_store(user=Depends(require_auth), cursor=Depends(get_cursor)):
    return service.get_store(cursor, user["id"])


@router.put("/store")
def upsert_store(data: dict, user=Depends(require_auth), cursor=Depends(get_cursor)):
    return service.upsert_store(cursor, user["id"], data)


# ── Categories ─────────────────────────────────────────────

@router.get("/categories")
def list_categories(user=Depends(require_auth), cursor=Depends(get_cursor)):
    return service.list_categories(cursor, user["id"])


@router.post("/categories")
def create_category(data: dict, user=Depends(require_auth), cursor=Depends(get_cursor)):
    return service.create_category(cursor, user["id"], data)


@router.put("/categories/{category_id}")
def update_category(category_id: str, data: dict, user=Depends(require_auth), cursor=Depends(get_cursor)):
    return service.update_category(cursor, user["id"], category_id, data)


@router.delete("/categories/{category_id}")
def delete_category(category_id: str, user=Depends(require_auth), cursor=Depends(get_cursor)):
    service.delete_category(cursor, user["id"], category_id)
    return {"ok": True}


# ── Products ───────────────────────────────────────────────

@router.get("/products")
def list_products(
    category_id: Optional[str] = Query(None),
    user=Depends(require_auth),
    cursor=Depends(get_cursor)
):
    return service.list_products(cursor, user["id"], category_id)


@router.get("/products/{product_id}")
def get_product(product_id: str, user=Depends(require_auth), cursor=Depends(get_cursor)):
    return service.get_product(cursor, user["id"], product_id)


@router.post("/products")
def create_product(data: dict, user=Depends(require_auth), cursor=Depends(get_cursor)):
    return service.create_product(cursor, user["id"], data)


@router.put("/products/{product_id}")
def update_product(product_id: str, data: dict, user=Depends(require_auth), cursor=Depends(get_cursor)):
    return service.update_product(cursor, user["id"], product_id, data)


@router.delete("/products/{product_id}")
def delete_product(product_id: str, user=Depends(require_auth), cursor=Depends(get_cursor)):
    service.delete_product(cursor, user["id"], product_id)
    return {"ok": True}


# ── Customers ──────────────────────────────────────────────

@router.get("/customers")
def list_customers(user=Depends(require_auth), cursor=Depends(get_cursor)):
    return service.list_customers(cursor, user["id"])


@router.get("/customers/{customer_id}")
def get_customer(customer_id: str, user=Depends(require_auth), cursor=Depends(get_cursor)):
    return service.get_customer(cursor, user["id"], customer_id)


@router.post("/customers")
def upsert_customer(data: dict, user=Depends(require_auth), cursor=Depends(get_cursor)):
    return service.upsert_customer(cursor, user["id"], data)


# ── Orders ─────────────────────────────────────────────────

@router.get("/orders")
def list_orders(
    status: Optional[str] = Query(None),
    user=Depends(require_auth),
    cursor=Depends(get_cursor)
):
    return service.list_orders(cursor, user["id"], status)


@router.get("/orders/{order_id}")
def get_order(order_id: str, user=Depends(require_auth), cursor=Depends(get_cursor)):
    return service.get_order(cursor, user["id"], order_id)


@router.post("/orders")
def create_order(data: dict, user=Depends(require_auth), cursor=Depends(get_cursor)):
    return service.create_order(cursor, user["id"], data)


@router.patch("/orders/{order_id}/status")
def update_order_status(order_id: str, data: dict, user=Depends(require_auth), cursor=Depends(get_cursor)):
    return service.update_order_status(cursor, user["id"], order_id, data["status"])


# ── Connectors ─────────────────────────────────────────────

@router.get("/connectors")
def list_connectors(user=Depends(require_auth), cursor=Depends(get_cursor)):
    return service.list_connectors(cursor, user["id"])


@router.put("/connectors/{provider}")
def upsert_connector(provider: str, data: dict, user=Depends(require_auth), cursor=Depends(get_cursor)):
    return service.upsert_connector(cursor, user["id"], provider, data["credentials"])


@router.delete("/connectors/{provider}")
def delete_connector(provider: str, user=Depends(require_auth), cursor=Depends(get_cursor)):
    service.delete_connector(cursor, user["id"], provider)
    return {"ok": True}
