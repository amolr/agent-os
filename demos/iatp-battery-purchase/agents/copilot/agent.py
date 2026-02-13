"""
Copilot Orchestrator Agent — coordinates the battery purchase flow.

Runs on port 8000. Uses SAGA pattern for distributed transaction coordination.
Communicates with Payment, Amazon, and Shipping agents via their IATP sidecars.
"""

from __future__ import annotations

import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Allow importing shared module from parent package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared import DemoIdentity, MerkleAuditLog, TrustHandshaker

AGENT_NAME = "copilot-orchestrator"
# When USE_SIDECARS=false (default for local dev), talk directly to agents
USE_SIDECARS = os.getenv("USE_SIDECARS", "false").lower() == "true"
PAYMENT_SIDECAR = os.getenv("PAYMENT_SIDECAR_URL", "http://localhost:8011" if USE_SIDECARS else "http://localhost:8010")
AMAZON_SIDECAR = os.getenv("AMAZON_SIDECAR_URL", "http://localhost:8021" if USE_SIDECARS else "http://localhost:8020")
SHIPPING_SIDECAR = os.getenv("SHIPPING_SIDECAR_URL", "http://localhost:8031" if USE_SIDECARS else "http://localhost:8030")

audit_log = MerkleAuditLog()
trust = TrustHandshaker(audit_log=audit_log, source_agent_id=AGENT_NAME)
identity = DemoIdentity.generate(AGENT_NAME, ["orchestrate", "purchase"], trust_score=900)

# Transaction stats
stats: Dict[str, int] = {"total": 0, "success": 0, "failed": 0, "rolled_back": 0}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(msg: str) -> None:
    print(f"[{AGENT_NAME}] {_now()} {msg}", flush=True)


# ---------------------------------------------------------------------------
# SAGA Transaction
# ---------------------------------------------------------------------------

@dataclass
class SAGAStep:
    name: str
    forward_result: Any
    compensate_fn: Optional[Callable[[], Coroutine]] = None


class SAGATransaction:
    """Simple SAGA coordinator — records forward steps and compensates on failure."""

    def __init__(self, tx_id: Optional[str] = None) -> None:
        self.tx_id = tx_id or str(uuid.uuid4())
        self.steps: List[SAGAStep] = []
        self.committed = False
        self.rolled_back = False

    def add_step(self, name: str, forward_result: Any,
                 compensate_fn: Optional[Callable[[], Coroutine]] = None) -> None:
        self.steps.append(SAGAStep(name=name, forward_result=forward_result,
                                   compensate_fn=compensate_fn))

    async def rollback(self) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for step in reversed(self.steps):
            if step.compensate_fn:
                try:
                    r = await step.compensate_fn()
                    results.append({"step": step.name, "compensated": True, "result": r})
                    _log(f"  ↩ Compensated '{step.name}'")
                except Exception as exc:
                    results.append({"step": step.name, "compensated": False, "error": str(exc)})
                    _log(f"  ✗ Compensation failed for '{step.name}': {exc}")
        self.rolled_back = True
        return results

    def commit(self) -> None:
        self.committed = True


# ---------------------------------------------------------------------------
# Helpers — HTTP calls through sidecars
# ---------------------------------------------------------------------------

async def _sidecar_call(sidecar_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    endpoint = "/proxy" if USE_SIDECARS else "/process"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{sidecar_url}{endpoint}",
            json=payload,
            headers={"X-User-Override": "true"},
        )
        return resp.json()


async def _cancel_payment(escrow_id: str) -> Dict[str, Any]:
    return await _sidecar_call(PAYMENT_SIDECAR, {
        "action": "cancel", "escrow_id": escrow_id,
    })


async def _cancel_reservation(reservation_id: str) -> Dict[str, Any]:
    return await _sidecar_call(AMAZON_SIDECAR, {
        "action": "cancel_reservation", "reservation_id": reservation_id,
    })


# ---------------------------------------------------------------------------
# Purchase flow
# ---------------------------------------------------------------------------

async def run_purchase(item_id: str, quantity: int, amount: float,
                       shipping_method: str = "standard") -> Dict[str, Any]:
    tx = SAGATransaction()
    stats["total"] += 1
    _log(f"▶ Starting purchase tx={tx.tx_id} item={item_id} qty={quantity} amt={amount}")
    audit_log.add_entry(AGENT_NAME, "purchase_start", {
        "tx_id": tx.tx_id, "item_id": item_id, "quantity": quantity, "amount": amount,
    })

    try:
        # --- Step 1: Handshake with Payment sidecar ---
        _log("  1. Handshake → Payment sidecar")
        pay_hs = await trust.handshake(PAYMENT_SIDECAR)
        _log(f"     trust_score={pay_hs['trust_score']} level={pay_hs['trust_level']}")
        if pay_hs["trust_score"] < 3:
            raise ValueError(f"Payment agent trust too low ({pay_hs['trust_score']})")

        # --- Step 2: Authorize payment ---
        _log("  2. Authorize payment")
        auth_resp = await _sidecar_call(PAYMENT_SIDECAR, {
            "action": "authorize", "amount": amount, "currency": "USD",
            "description": f"Battery purchase {item_id} x{quantity}",
        })
        if auth_resp.get("status") == "error" or "error" in auth_resp:
            raise RuntimeError(f"Payment authorization failed: {auth_resp}")
        escrow_id = auth_resp.get("escrow_id")
        _log(f"     escrow_id={escrow_id}")
        tx.add_step("authorize_payment", auth_resp,
                     lambda eid=escrow_id: _cancel_payment(eid))

        # --- Step 3: Handshake with Amazon sidecar ---
        _log("  3. Handshake → Amazon sidecar")
        amz_hs = await trust.handshake(AMAZON_SIDECAR)
        _log(f"     trust_score={amz_hs['trust_score']} level={amz_hs['trust_level']}")

        # --- Step 4: Reserve inventory ---
        _log("  4. Reserve inventory")
        reserve_resp = await _sidecar_call(AMAZON_SIDECAR, {
            "action": "reserve", "item_id": item_id, "quantity": quantity,
        })
        if reserve_resp.get("status") == "error" or "error" in reserve_resp:
            raise RuntimeError(f"Inventory reservation failed: {reserve_resp}")
        reservation_id = reserve_resp.get("reservation_id")
        _log(f"     reservation_id={reservation_id}")
        tx.add_step("reserve_inventory", reserve_resp,
                     lambda rid=reservation_id: _cancel_reservation(rid))

        # --- Step 5: Shipping quote (delegated via Amazon) ---
        _log("  5. Get shipping quote")
        quote_resp = await _sidecar_call(AMAZON_SIDECAR, {
            "action": "get_shipping_quote", "item_id": item_id,
            "quantity": quantity, "method": shipping_method,
        })
        shipping_cost = quote_resp.get("cost", 8.99)
        _log(f"     shipping={shipping_cost}")
        tx.add_step("shipping_quote", quote_resp)

        # --- Step 6: Commit — capture payment, confirm order, create label ---
        _log("  6. Commit — capture payment")
        capture_resp = await _sidecar_call(PAYMENT_SIDECAR, {
            "action": "capture", "escrow_id": escrow_id,
        })
        if capture_resp.get("status") == "error" or "error" in capture_resp:
            raise RuntimeError(f"Payment capture failed: {capture_resp}")
        tx.add_step("capture_payment", capture_resp)

        _log("     Confirm order")
        confirm_resp = await _sidecar_call(AMAZON_SIDECAR, {
            "action": "confirm", "reservation_id": reservation_id,
        })
        tx.add_step("confirm_order", confirm_resp)

        _log("     Create shipping label")
        label_resp = await _sidecar_call(AMAZON_SIDECAR, {
            "action": "get_shipping_quote",  # label creation via shipping
            "item_id": item_id, "quantity": quantity, "method": shipping_method,
            "create_label": True,
        })
        tx.add_step("create_label", label_resp)

        tx.commit()
        stats["success"] += 1
        _log(f"  ✔ Purchase committed tx={tx.tx_id}")
        audit_log.add_entry(AGENT_NAME, "purchase_committed", {"tx_id": tx.tx_id})

        return {
            "status": "success",
            "tx_id": tx.tx_id,
            "escrow_id": escrow_id,
            "reservation_id": reservation_id,
            "shipping_cost": shipping_cost,
            "total": amount + shipping_cost,
            "steps": [s.name for s in tx.steps],
        }

    except Exception as exc:
        _log(f"  ✗ Purchase failed: {exc}")
        audit_log.add_entry(AGENT_NAME, "purchase_failed", {
            "tx_id": tx.tx_id, "error": str(exc),
        })
        compensations = await tx.rollback()
        stats["failed"] += 1
        stats["rolled_back"] += 1
        return {
            "status": "failed",
            "tx_id": tx.tx_id,
            "error": str(exc),
            "compensations": compensations,
        }


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(title="Copilot Orchestrator Agent", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


@app.get("/health")
async def health():
    return {"status": "healthy", "agent": AGENT_NAME, "did": identity.did}


@app.post("/process")
async def process(request: Request):
    """Main entry point — receives proxied requests from the sidecar."""
    body = await request.json()
    action = body.get("action", "purchase")
    if action == "purchase":
        result = await run_purchase(
            item_id=body.get("item_id", "B07XYZ"),
            quantity=body.get("quantity", 1),
            amount=body.get("amount", 49.99),
            shipping_method=body.get("shipping_method", "standard"),
        )
        return JSONResponse(content=result)
    return JSONResponse(content={"error": f"Unknown action: {action}"}, status_code=400)


@app.post("/purchase")
async def purchase_endpoint(request: Request):
    """Direct purchase endpoint (called by demo orchestrator)."""
    body = await request.json()
    result = await run_purchase(
        item_id=body.get("item_id", "B07XYZ"),
        quantity=body.get("quantity", 1),
        amount=body.get("amount", 49.99),
        shipping_method=body.get("shipping_method", "standard"),
    )
    return JSONResponse(content=result)


@app.get("/audit")
async def get_audit():
    return {
        "chain_valid": audit_log.verify_chain(),
        "entries": audit_log.get_log(),
    }


@app.get("/stats")
async def get_stats():
    return stats
