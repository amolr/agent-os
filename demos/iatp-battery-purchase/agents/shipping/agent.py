"""
Shipping Agent — simulates UPS/FedEx shipping services.

Runs on port 8030. Provides quotes, label creation, and tracking.
"""

from __future__ import annotations

import os
import random
import string
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared import MerkleAuditLog

AGENT_NAME = "shipping-agent"

audit_log = MerkleAuditLog()
labels: Dict[str, Dict[str, Any]] = {}

RATES = {
    "standard": 8.99,
    "express": 14.99,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(msg: str) -> None:
    print(f"[{AGENT_NAME}] {_now()} {msg}", flush=True)


def _tracking_number() -> str:
    prefix = "1Z"
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=16))
    return f"{prefix}{suffix}"


# ---------------------------------------------------------------------------
# Domain logic
# ---------------------------------------------------------------------------

def quote(weight_lbs: float, destination: str = "US",
          method: str = "standard") -> Dict[str, Any]:
    cost = RATES.get(method, RATES["standard"])
    # Add weight surcharge for heavy packages
    if weight_lbs > 5:
        cost += (weight_lbs - 5) * 1.50
    _log(f"QUOTE method={method} weight={weight_lbs}lbs dest={destination} cost={cost}")
    return {
        "status": "quoted",
        "method": method,
        "cost": round(cost, 2),
        "weight_lbs": weight_lbs,
        "destination": destination,
        "estimated_days": 5 if method == "standard" else 2,
    }


def create_label(weight_lbs: float, destination: str = "US",
                 method: str = "standard") -> Dict[str, Any]:
    """Create shipping label — NOTE: this is NON-REVERSIBLE."""
    tracking = _tracking_number()
    cost = RATES.get(method, RATES["standard"])
    if weight_lbs > 5:
        cost += (weight_lbs - 5) * 1.50
    label_id = str(uuid.uuid4())
    labels[label_id] = {
        "tracking_number": tracking,
        "method": method,
        "cost": round(cost, 2),
        "weight_lbs": weight_lbs,
        "destination": destination,
        "status": "created",
        "created_at": _now(),
    }
    _log(f"LABEL CREATED label={label_id} tracking={tracking} (NON-REVERSIBLE)")
    audit_log.add_entry(AGENT_NAME, "create_label", {
        "label_id": label_id, "tracking_number": tracking,
    })
    return {
        "status": "label_created",
        "label_id": label_id,
        "tracking_number": tracking,
        "cost": round(cost, 2),
        "reversible": False,
    }


def track(tracking_number: str) -> Dict[str, Any]:
    # Find label by tracking number
    for lid, label in labels.items():
        if label["tracking_number"] == tracking_number:
            _log(f"TRACK tracking={tracking_number} status={label['status']}")
            return {
                "status": "ok",
                "tracking_number": tracking_number,
                "shipping_status": label["status"],
                "estimated_delivery": "3-5 business days",
                "events": [
                    {"time": label["created_at"], "event": "Label created"},
                    {"time": _now(), "event": "In transit"},
                ],
            }
    # Fake tracking for unknown numbers
    _log(f"TRACK tracking={tracking_number} (not found, returning fake)")
    return {
        "status": "ok",
        "tracking_number": tracking_number,
        "shipping_status": "in_transit",
        "estimated_delivery": "3-5 business days",
        "events": [{"time": _now(), "event": "Package in transit"}],
    }


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(title="Shipping Agent", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


@app.get("/health")
async def health():
    return {"status": "healthy", "agent": AGENT_NAME, "labels_created": len(labels)}


@app.post("/process")
async def process(request: Request):
    body = await request.json()
    action = body.get("action")
    _log(f"Processing action={action}")

    if action == "quote":
        return JSONResponse(content=quote(
            weight_lbs=body.get("weight_lbs", 1.0),
            destination=body.get("destination", "US"),
            method=body.get("method", "standard"),
        ))
    elif action == "create_label":
        return JSONResponse(content=create_label(
            weight_lbs=body.get("weight_lbs", 1.0),
            destination=body.get("destination", "US"),
            method=body.get("method", "standard"),
        ))
    elif action == "track":
        return JSONResponse(content=track(body.get("tracking_number", "")))
    else:
        return JSONResponse(
            content={"status": "error", "error": f"Unknown action: {action}"},
            status_code=400,
        )
