"""
Payment Agent — simulates Stripe-like payment processing.

Runs on port 8010. Manages escrows for authorization/capture/cancel/refund.
"""

from __future__ import annotations

import os
import random
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared import MerkleAuditLog

AGENT_NAME = "payment-agent"
_payment_fail_rate = float(os.getenv("PAYMENT_FAIL_RATE", "0.0"))

audit_log = MerkleAuditLog()
escrows: Dict[str, Dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(msg: str) -> None:
    print(f"[{AGENT_NAME}] {_now()} {msg}", flush=True)


# ---------------------------------------------------------------------------
# Domain logic
# ---------------------------------------------------------------------------

def authorize(amount: float, currency: str = "USD",
              description: str = "") -> Dict[str, Any]:
    if amount > 10000:
        _log(f"REJECT authorize — amount {amount} exceeds limit")
        return {"status": "error", "error": "Amount exceeds limit of $10,000"}
    escrow_id = str(uuid.uuid4())
    escrows[escrow_id] = {
        "amount": amount,
        "currency": currency,
        "description": description,
        "status": "authorized",
        "created_at": _now(),
    }
    _log(f"AUTHORIZED escrow={escrow_id} amount={amount} {currency}")
    audit_log.add_entry(AGENT_NAME, "authorize", {
        "escrow_id": escrow_id, "amount": amount,
    })
    return {"status": "authorized", "escrow_id": escrow_id, "amount": amount}


def capture(escrow_id: str) -> Dict[str, Any]:
    if escrow_id not in escrows:
        return {"status": "error", "error": f"Escrow {escrow_id} not found"}
    esc = escrows[escrow_id]
    if esc["status"] != "authorized":
        return {"status": "error", "error": f"Escrow status is '{esc['status']}', expected 'authorized'"}
    # Configurable failure
    if _payment_fail_rate > 0 and random.random() < _payment_fail_rate:
        _log(f"CAPTURE FAILED (simulated) escrow={escrow_id}")
        return {"status": "error", "error": "Payment capture failed (processor declined)"}
    esc["status"] = "captured"
    esc["captured_at"] = _now()
    _log(f"CAPTURED escrow={escrow_id} amount={esc['amount']}")
    audit_log.add_entry(AGENT_NAME, "capture", {"escrow_id": escrow_id})
    return {"status": "captured", "escrow_id": escrow_id, "amount": esc["amount"]}


def cancel(escrow_id: str) -> Dict[str, Any]:
    if escrow_id not in escrows:
        return {"status": "error", "error": f"Escrow {escrow_id} not found"}
    esc = escrows[escrow_id]
    if esc["status"] not in ("authorized",):
        return {"status": "error", "error": f"Cannot cancel escrow in status '{esc['status']}'"}
    esc["status"] = "cancelled"
    esc["cancelled_at"] = _now()
    _log(f"CANCELLED escrow={escrow_id}")
    audit_log.add_entry(AGENT_NAME, "cancel", {"escrow_id": escrow_id})
    return {"status": "cancelled", "escrow_id": escrow_id}


def refund(escrow_id: str) -> Dict[str, Any]:
    if escrow_id not in escrows:
        return {"status": "error", "error": f"Escrow {escrow_id} not found"}
    esc = escrows[escrow_id]
    if esc["status"] != "captured":
        return {"status": "error", "error": f"Cannot refund escrow in status '{esc['status']}'"}
    esc["status"] = "refunded"
    esc["refunded_at"] = _now()
    _log(f"REFUNDED escrow={escrow_id} amount={esc['amount']}")
    audit_log.add_entry(AGENT_NAME, "refund", {"escrow_id": escrow_id})
    return {"status": "refunded", "escrow_id": escrow_id, "amount": esc["amount"]}


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(title="Payment Agent", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


@app.get("/health")
async def health():
    return {"status": "healthy", "agent": AGENT_NAME,
            "active_escrows": sum(1 for e in escrows.values() if e["status"] == "authorized")}


@app.post("/process")
async def process(request: Request):
    body = await request.json()
    action = body.get("action")
    _log(f"Processing action={action}")

    if action == "authorize":
        return JSONResponse(content=authorize(
            amount=body.get("amount", 0),
            currency=body.get("currency", "USD"),
            description=body.get("description", ""),
        ))
    elif action == "capture":
        return JSONResponse(content=capture(body.get("escrow_id", "")))
    elif action == "cancel":
        return JSONResponse(content=cancel(body.get("escrow_id", "")))
    elif action == "refund":
        return JSONResponse(content=refund(body.get("escrow_id", "")))
    else:
        return JSONResponse(
            content={"status": "error", "error": f"Unknown action: {action}"},
            status_code=400,
        )


@app.get("/escrows")
async def list_escrows():
    return {"escrows": escrows}


@app.post("/config")
async def config(request: Request):
    """Dynamically adjust agent config (used by demo orchestrator)."""
    global _payment_fail_rate
    body = await request.json()
    if "fail_rate" in body:
        _payment_fail_rate = float(body["fail_rate"])
        _log(f"CONFIG updated fail_rate={_payment_fail_rate}")
    return {"fail_rate": _payment_fail_rate}
