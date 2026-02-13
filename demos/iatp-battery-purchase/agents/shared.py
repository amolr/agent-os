"""
Shared utilities for IATP Battery Purchase Demo agents.

Provides Merkle-chained audit logging, trust handshaking, and DID identity helpers.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import httpx


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Merkle-Chained Audit Log
# ---------------------------------------------------------------------------

@dataclass
class AuditEntry:
    entry_id: str
    agent_id: str
    action: str
    data: Dict[str, Any]
    timestamp: str
    hash: str
    prev_hash: str


class MerkleAuditLog:
    """In-memory Merkle-chained audit log for tamper-evident recording."""

    def __init__(self) -> None:
        self._entries: List[AuditEntry] = []

    def _compute_hash(self, entry_id: str, agent_id: str, action: str,
                      data: str, timestamp: str, prev_hash: str) -> str:
        payload = f"{entry_id}|{agent_id}|{action}|{data}|{timestamp}|{prev_hash}"
        return hashlib.sha256(payload.encode()).hexdigest()

    def add_entry(self, agent_id: str, action: str,
                  data: Optional[Dict[str, Any]] = None) -> AuditEntry:
        entry_id = _uuid()
        timestamp = _now()
        prev_hash = self._entries[-1].hash if self._entries else "0" * 64
        data = data or {}
        data_str = str(sorted(data.items()))
        h = self._compute_hash(entry_id, agent_id, action, data_str,
                               timestamp, prev_hash)
        entry = AuditEntry(
            entry_id=entry_id,
            agent_id=agent_id,
            action=action,
            data=data,
            timestamp=timestamp,
            hash=h,
            prev_hash=prev_hash,
        )
        self._entries.append(entry)
        return entry

    def get_log(self) -> List[Dict[str, Any]]:
        return [
            {
                "entry_id": e.entry_id,
                "agent_id": e.agent_id,
                "action": e.action,
                "data": e.data,
                "timestamp": e.timestamp,
                "hash": e.hash,
                "prev_hash": e.prev_hash,
            }
            for e in self._entries
        ]

    def verify_chain(self) -> bool:
        for i, entry in enumerate(self._entries):
            expected_prev = self._entries[i - 1].hash if i > 0 else "0" * 64
            if entry.prev_hash != expected_prev:
                return False
            data_str = str(sorted(entry.data.items()))
            expected_hash = self._compute_hash(
                entry.entry_id, entry.agent_id, entry.action,
                data_str, entry.timestamp, entry.prev_hash,
            )
            if entry.hash != expected_hash:
                return False
        return True


# ---------------------------------------------------------------------------
# Trust Handshaker
# ---------------------------------------------------------------------------

class TrustHandshaker:
    """Performs IATP handshake with a target sidecar."""

    def __init__(self, audit_log: Optional[MerkleAuditLog] = None,
                 source_agent_id: str = "unknown") -> None:
        self.audit_log = audit_log
        self.source_agent_id = source_agent_id

    async def handshake(self, target_url: str) -> Dict[str, Any]:
        """Fetch manifest from target sidecar and compute trust assessment."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Try sidecar manifest first, fall back to health endpoint
            try:
                resp = await client.get(f"{target_url}/.well-known/agent-manifest")
                resp.raise_for_status()
                manifest = resp.json()
            except Exception:
                # Direct agent mode — build synthetic manifest from health
                try:
                    resp = await client.get(f"{target_url}/health")
                    resp.raise_for_status()
                    health = resp.json()
                    manifest = {
                        "agent_id": health.get("agent_id", "unknown"),
                        "trust_level": "trusted",
                        "capabilities": {"reversibility": "full", "idempotency": True},
                        "privacy_contract": {"retention": "ephemeral"},
                    }
                except Exception:
                    manifest = {"agent_id": "unreachable", "trust_level": "untrusted"}

        trust_score = manifest.get("trust_score")
        if trust_score is None:
            trust_score = self._calculate_trust_score(manifest)

        result = {
            "target_url": target_url,
            "agent_id": manifest.get("agent_id", "unknown"),
            "trust_level": manifest.get("trust_level", "unknown"),
            "trust_score": trust_score,
            "reversibility": manifest.get("capabilities", {}).get("reversibility", "none"),
            "idempotency": manifest.get("capabilities", {}).get("idempotency", False),
            "retention": manifest.get("privacy_contract", {}).get("retention", "unknown"),
            "timestamp": _now(),
        }

        if self.audit_log:
            self.audit_log.add_entry(
                self.source_agent_id, "trust_handshake", result
            )
        return result

    @staticmethod
    def _calculate_trust_score(manifest: Dict[str, Any]) -> int:
        """Mirror the IATP CapabilityManifest.calculate_trust_score logic."""
        score = 5
        trust_map = {
            "verified_partner": 3, "trusted": 2, "standard": 0,
            "unknown": -2, "untrusted": -5,
        }
        score += trust_map.get(manifest.get("trust_level", "standard"), 0)
        caps = manifest.get("capabilities", {})
        if caps.get("idempotency"):
            score += 1
        if caps.get("reversibility") in ("full", "partial"):
            score += 1
        privacy = manifest.get("privacy_contract", {})
        retention = privacy.get("retention", "temporary")
        if retention == "ephemeral":
            score += 2
        elif retention in ("permanent", "forever"):
            score -= 2
        if not privacy.get("human_review", False):
            score += 1
        return max(0, min(10, score))


# ---------------------------------------------------------------------------
# Demo Identity
# ---------------------------------------------------------------------------

@dataclass
class DemoIdentity:
    """Simple DID representation for the demo."""
    did: str
    capabilities: List[str] = field(default_factory=list)
    trust_score: int = 500
    ttl_minutes: int = 15

    @staticmethod
    def generate(agent_name: str, capabilities: Optional[List[str]] = None,
                 trust_score: int = 500) -> "DemoIdentity":
        short_id = _uuid()[:8]
        return DemoIdentity(
            did=f"did:mesh:{agent_name}-{short_id}",
            capabilities=capabilities or [],
            trust_score=trust_score,
            ttl_minutes=15,
        )
