"""
Amazon Marketplace Agent — simulates inventory and order management.

Runs on port 8020. Manages inventory, reservations, and delegates shipping quotes.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared import MerkleAuditLog

AGENT_NAME = "amazon-agent"
USE_SIDECARS = os.getenv("USE_SIDECARS", "false").lower() == "true"
SHIPPING_SIDECAR = os.getenv("SHIPPING_SIDECAR_URL", "http://localhost:8031" if USE_SIDECARS else "http://localhost:8030")
INVENTORY_FAIL = os.getenv("INVENTORY_FAIL", "false").lower() == "true"

audit_log = MerkleAuditLog()

# Pre-loaded inventory
inventory: Dict[str, Dict[str, Any]] = {
    "B07XYZ": {"name": "Duracell Battery Pack", "price": 49.99, "stock": 10},
}

reservations: Dict[str, Dict[str, Any]] = {}
orders: Dict[str, Dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(msg: str) -> None:
    print(f"[{AGENT_NAME}] {_now()} {msg}", flush=True)


# ---------------------------------------------------------------------------
# Domain logic
# ---------------------------------------------------------------------------

def check_inventory(item_id: str) -> Dict[str, Any]:
    if item_id not in inventory:
        return {"status": "error", "error": f"Item {item_id} not found"}
    item = inventory[item_id]
    available = item["stock"] > 0 and not INVENTORY_FAIL
    _log(f"CHECK_INVENTORY item={item_id} stock={item['stock']} available={available}")
    return {
        "status": "ok",
        "item_id": item_id,
        "name": item["name"],
        "price": item["price"],
        "stock": item["stock"],
        "available": available,
    }


def reserve(item_id: str, quantity: int) -> Dict[str, Any]:
    if INVENTORY_FAIL:
        _log(f"RESERVE FAILED (simulated out-of-stock) item={item_id}")
        return {"status": "error", "error": "Out of stock (simulated)"}
    if item_id not in inventory:
        return {"status": "error", "error": f"Item {item_id} not found"}
    item = inventory[item_id]
    if item["stock"] < quantity:
        return {"status": "error", "error": f"Insufficient stock: {item['stock']} < {quantity}"}
    item["stock"] -= quantity
    reservation_id = str(uuid.uuid4())
    reservations[reservation_id] = {
        "item_id": item_id,
        "quantity": quantity,
        "status": "reserved",
        "created_at": _now(),
    }
    _log(f"RESERVED reservation={reservation_id} item={item_id} qty={quantity}")
    audit_log.add_entry(AGENT_NAME, "reserve", {
        "reservation_id": reservation_id, "item_id": item_id, "quantity": quantity,
    })
    return {
        "status": "reserved",
        "reservation_id": reservation_id,
        "item_id": item_id,
        "quantity": quantity,
        "remaining_stock": item["stock"],
    }


def confirm(reservation_id: str) -> Dict[str, Any]:
    if reservation_id not in reservations:
        return {"status": "error", "error": f"Reservation {reservation_id} not found"}
    res = reservations[reservation_id]
    if res["status"] != "reserved":
        return {"status": "error", "error": f"Reservation status is '{res['status']}'"}
    res["status"] = "confirmed"
    res["confirmed_at"] = _now()
    order_id = str(uuid.uuid4())
    orders[order_id] = {
        "reservation_id": reservation_id,
        "item_id": res["item_id"],
        "quantity": res["quantity"],
        "status": "confirmed",
        "created_at": _now(),
    }
    _log(f"CONFIRMED reservation={reservation_id} order={order_id}")
    audit_log.add_entry(AGENT_NAME, "confirm", {
        "reservation_id": reservation_id, "order_id": order_id,
    })
    return {"status": "confirmed", "order_id": order_id, "reservation_id": reservation_id}


def cancel_reservation(reservation_id: str) -> Dict[str, Any]:
    if reservation_id not in reservations:
        return {"status": "error", "error": f"Reservation {reservation_id} not found"}
    res = reservations[reservation_id]
    if res["status"] != "reserved":
        return {"status": "error", "error": f"Cannot cancel reservation in status '{res['status']}'"}
    # Restore stock
    item_id = res["item_id"]
    if item_id in inventory:
        inventory[item_id]["stock"] += res["quantity"]
    res["status"] = "cancelled"
    res["cancelled_at"] = _now()
    _log(f"CANCEL_RESERVATION reservation={reservation_id} (stock restored)")
    audit_log.add_entry(AGENT_NAME, "cancel_reservation", {
        "reservation_id": reservation_id,
    })
    return {"status": "cancelled", "reservation_id": reservation_id}


async def get_shipping_quote(item_id: str, quantity: int,
                             method: str = "standard",
                             create_label: bool = False) -> Dict[str, Any]:
    """Delegate to Shipping agent sidecar — demonstrates delegation chain."""
    _log(f"SHIPPING_QUOTE delegating to shipping sidecar method={method}")
    payload: Dict[str, Any] = {
        "action": "create_label" if create_label else "quote",
        "weight_lbs": quantity * 0.5,
        "destination": "US",
        "method": method,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{SHIPPING_SIDECAR}{'/proxy' if USE_SIDECARS else '/process'}",
                json=payload,
                headers={"X-User-Override": "true"},
            )
            result = resp.json()
        audit_log.add_entry(AGENT_NAME, "shipping_delegation", {
            "method": method, "create_label": create_label, "result_status": result.get("status"),
        })
        return result
    except Exception as exc:
        _log(f"Shipping delegation failed: {exc}")
        return {"status": "error", "error": str(exc)}


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(title="Amazon Marketplace Agent", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


@app.get("/health")
async def health():
    return {"status": "healthy", "agent": AGENT_NAME, "items": len(inventory)}


@app.post("/process")
async def process(request: Request):
    body = await request.json()
    action = body.get("action")
    _log(f"Processing action={action}")

    if action == "check_inventory":
        return JSONResponse(content=check_inventory(body.get("item_id", "")))
    elif action == "reserve":
        return JSONResponse(content=reserve(
            body.get("item_id", ""), body.get("quantity", 1),
        ))
    elif action == "confirm":
        return JSONResponse(content=confirm(body.get("reservation_id", "")))
    elif action == "cancel_reservation":
        return JSONResponse(content=cancel_reservation(body.get("reservation_id", "")))
    elif action == "get_shipping_quote":
        result = await get_shipping_quote(
            item_id=body.get("item_id", ""),
            quantity=body.get("quantity", 1),
            method=body.get("method", "standard"),
            create_label=body.get("create_label", False),
        )
        return JSONResponse(content=result)
    else:
        return JSONResponse(
            content={"status": "error", "error": f"Unknown action: {action}"},
            status_code=400,
        )


@app.get("/inventory")
async def get_inventory():
    return {"inventory": inventory, "reservations": reservations, "orders": orders}
