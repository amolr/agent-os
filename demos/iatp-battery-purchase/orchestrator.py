#!/usr/bin/env python3
"""
Demo orchestrator — runs 3 scenarios against the IATP battery purchase agents.

Usage:
    python orchestrator.py              # Uses default URLs (local dev)
    COPILOT_URL=http://... python orchestrator.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time

import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
COPILOT_URL = os.getenv("COPILOT_URL", "http://localhost:8000")
USE_SIDECARS = os.getenv("USE_SIDECARS", "false").lower() == "true"
PAYMENT_URL = os.getenv("PAYMENT_URL", "http://localhost:8011" if USE_SIDECARS else "http://localhost:8010")
AMAZON_URL = os.getenv("AMAZON_URL", "http://localhost:8021" if USE_SIDECARS else "http://localhost:8020")

# ANSI colours
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_GREEN = "\033[92m"
C_RED = "\033[91m"
C_YELLOW = "\033[93m"
C_CYAN = "\033[96m"
C_DIM = "\033[2m"


def banner(text: str) -> None:
    print(f"\n{C_BOLD}{C_CYAN}{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}{C_RESET}\n")


def step(num: int, msg: str) -> None:
    print(f"  {C_BOLD}[Step {num}]{C_RESET} {msg}")


def ok(msg: str) -> None:
    print(f"    {C_GREEN}✔ {msg}{C_RESET}")


def fail(msg: str) -> None:
    print(f"    {C_RED}✗ {msg}{C_RESET}")


def info(msg: str) -> None:
    print(f"    {C_DIM}{msg}{C_RESET}")


def warn(msg: str) -> None:
    print(f"    {C_YELLOW}⚠ {msg}{C_RESET}")


def pp(data: dict) -> None:
    """Pretty-print JSON."""
    print(f"    {C_DIM}{json.dumps(data, indent=4)}{C_RESET}")


async def check_health(name: str, url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{url}/health")
            if r.status_code == 200:
                ok(f"{name} healthy")
                return True
    except Exception:
        pass
    fail(f"{name} NOT reachable at {url}")
    return False


async def handshake(agent_url: str) -> dict:
    """Attempt handshake via well-known manifest; fall back to /health."""
    async with httpx.AsyncClient(timeout=5.0) as c:
        try:
            r = await c.get(f"{agent_url}/.well-known/agent-manifest")
            r.raise_for_status()
            return r.json()
        except Exception:
            r = await c.get(f"{agent_url}/health")
            r.raise_for_status()
            return r.json()


async def show_audit() -> None:
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{COPILOT_URL}/audit")
            data = r.json()
        print(f"\n  {C_BOLD}Audit Log ({len(data.get('entries', []))} entries, "
              f"chain_valid={data.get('chain_valid')}){C_RESET}")
        for e in data.get("entries", [])[-6:]:
            info(f"  {e['timestamp']} | {e['action']:25s} | {e['hash'][:12]}…")
    except Exception as exc:
        warn(f"Could not fetch audit log: {exc}")


async def show_stats() -> None:
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{COPILOT_URL}/stats")
            data = r.json()
        print(f"\n  {C_BOLD}Transaction Stats:{C_RESET}")
        for k, v in data.items():
            info(f"  {k}: {v}")
    except Exception as exc:
        warn(f"Could not fetch stats: {exc}")


# ---------------------------------------------------------------------------
# Scenario 1 — Happy Path
# ---------------------------------------------------------------------------

async def run_happy_path() -> None:
    banner("Scenario 1: Happy Path — Full Purchase Flow")

    step(1, "Handshake with Payment Agent")
    try:
        m = await handshake(PAYMENT_URL)
        ok(f"agent_id={m.get('agent_id')} trust={m.get('trust_level')} "
           f"reversibility={m.get('capabilities', {}).get('reversibility')}")
    except Exception as exc:
        fail(f"Handshake failed: {exc}")
        return

    step(2, "Handshake with Amazon Agent")
    try:
        m = await handshake(AMAZON_URL)
        ok(f"agent_id={m.get('agent_id')} trust={m.get('trust_level')}")
    except Exception as exc:
        fail(f"Handshake failed: {exc}")
        return

    step(3, "Execute purchase via Copilot orchestrator")
    try:
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.post(f"{COPILOT_URL}/purchase", json={
                "item_id": "B07XYZ",
                "quantity": 2,
                "amount": 99.98,
                "shipping_method": "standard",
            })
            result = r.json()
        if result.get("status") == "success":
            ok(f"Purchase succeeded! tx={result.get('tx_id', '?')[:8]}…")
            info(f"escrow_id={result.get('escrow_id', '?')[:8]}…")
            info(f"reservation_id={result.get('reservation_id', '?')[:8]}…")
            info(f"shipping_cost=${result.get('shipping_cost', 0):.2f}")
            info(f"total=${result.get('total', 0):.2f}")
            info(f"steps: {', '.join(result.get('steps', []))}")
        else:
            fail(f"Purchase failed: {result.get('error', result)}")
    except Exception as exc:
        fail(f"Purchase call failed: {exc}")

    await show_audit()


# ---------------------------------------------------------------------------
# Scenario 2 — Payment Failure → Compensation
# ---------------------------------------------------------------------------

async def run_payment_failure() -> None:
    banner("Scenario 2: Payment Failure → SAGA Compensation")

    step(1, "Set payment agent capture fail rate to 100%")
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.post(f"{PAYMENT_URL}/config", json={"fail_rate": 1.0})
            ok(f"Payment fail_rate set to {r.json().get('fail_rate')}")
    except Exception as exc:
        warn(f"Could not set fail rate: {exc}")
        info("Falling back: payment capture may or may not fail")

    step(2, "Execute purchase (capture will fail, triggering SAGA rollback)")
    try:
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.post(f"{COPILOT_URL}/purchase", json={
                "item_id": "B07XYZ",
                "quantity": 1,
                "amount": 49.99,
                "shipping_method": "standard",
            })
            result = r.json()
        if result.get("status") == "failed":
            ok("Purchase correctly failed!")
            info(f"error: {result.get('error', '?')}")
            compensations = result.get("compensations", [])
            if compensations:
                ok(f"SAGA compensations executed ({len(compensations)} steps)")
                for comp in compensations:
                    info(f"  ↩ {comp['step']}: compensated={comp['compensated']}")
            else:
                info("No compensations needed (failed before any steps)")
        else:
            warn(f"Expected failure but got: {result.get('status')}")
            pp(result)
    except Exception as exc:
        fail(f"Purchase call failed: {exc}")

    await show_audit()

    step(3, "Reset payment agent fail rate to 0%")
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            await c.post(f"{PAYMENT_URL}/config", json={"fail_rate": 0.0})
            ok("Payment fail_rate reset to 0")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Scenario 3 — Low Trust Enforcement
# ---------------------------------------------------------------------------

async def run_low_trust() -> None:
    banner("Scenario 3: Low Trust Score → Trust Enforcement")

    step(1, "Check trust scores of all agents")
    for name, url in [("Payment", PAYMENT_URL), ("Amazon", AMAZON_URL)]:
        try:
            m = await handshake(url)
            trust_level = m.get("trust_level", "unknown")
            caps = m.get("capabilities", {})
            privacy = m.get("privacy_contract", {})
            # Compute score locally
            score = 5
            trust_map = {"verified_partner": 3, "trusted": 2, "standard": 0,
                         "unknown": -2, "untrusted": -5}
            score += trust_map.get(trust_level, 0)
            if caps.get("idempotency"):
                score += 1
            if caps.get("reversibility") in ("full", "partial"):
                score += 1
            if privacy.get("retention") == "ephemeral":
                score += 2
            elif privacy.get("retention") in ("permanent", "forever"):
                score -= 2
            if not privacy.get("human_review", False):
                score += 1
            score = max(0, min(10, score))
            ok(f"{name}: trust_level={trust_level} computed_score={score}/10")
        except Exception as exc:
            fail(f"{name} handshake failed: {exc}")

    step(2, "Attempt purchase (orchestrator enforces trust threshold ≥ 3)")
    info("With verified_partner Payment agent, purchase should succeed.")
    info("To see rejection, restart Payment Agent with IATP_TRUST_LEVEL=untrusted")

    try:
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.post(f"{COPILOT_URL}/purchase", json={
                "item_id": "B07XYZ",
                "quantity": 1,
                "amount": 49.99,
                "shipping_method": "express",
            })
            result = r.json()
        if result.get("status") == "success":
            ok(f"Purchase succeeded (trust was sufficient)")
            info(f"steps: {', '.join(result.get('steps', []))}")
        elif result.get("status") == "failed":
            error = result.get("error", "")
            if "trust" in error.lower():
                ok(f"Correctly rejected due to low trust: {error}")
            else:
                info(f"Failed for other reason: {error}")
        else:
            pp(result)
    except Exception as exc:
        fail(f"Purchase call failed: {exc}")

    await show_audit()
    await show_stats()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    banner("IATP Battery Purchase Demo — Orchestrator")
    print(f"  Copilot Agent:   {COPILOT_URL}")
    print(f"  Payment Agent:   {PAYMENT_URL}")
    print(f"  Amazon Agent:    {AMAZON_URL}")

    # Health checks
    print(f"\n{C_BOLD}Health Checks:{C_RESET}")
    healths = await asyncio.gather(
        check_health("Copilot Agent", COPILOT_URL),
        check_health("Payment Agent", PAYMENT_URL),
        check_health("Amazon Agent", AMAZON_URL),
    )
    if not all(healths):
        warn("Some services are not healthy — scenarios may fail")
        print()

    # Run scenarios
    await run_happy_path()
    print()
    await run_payment_failure()
    print()
    await run_low_trust()

    banner("Demo Complete")


if __name__ == "__main__":
    asyncio.run(main())
