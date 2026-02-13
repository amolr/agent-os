#!/usr/bin/env python3
"""
Local development launcher — starts all 4 agents on their respective ports.

Usage:
    python run_local.py

Requires: fastapi, uvicorn, httpx, pydantic  (pip install -r requirements.txt)
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AGENTS_DIR = os.path.join(BASE_DIR, "agents")

AGENTS = [
    {
        "name": "copilot",
        "port": 8000,
        "dir": os.path.join(AGENTS_DIR, "copilot"),
        "env": {
            "PAYMENT_SIDECAR_URL": "http://localhost:8011",
            "AMAZON_SIDECAR_URL": "http://localhost:8021",
            "SHIPPING_SIDECAR_URL": "http://localhost:8031",
        },
    },
    {
        "name": "payment",
        "port": 8010,
        "dir": os.path.join(AGENTS_DIR, "payment"),
        "env": {"PAYMENT_FAIL_RATE": "0.0"},
    },
    {
        "name": "amazon",
        "port": 8020,
        "dir": os.path.join(AGENTS_DIR, "amazon"),
        "env": {
            "SHIPPING_SIDECAR_URL": "http://localhost:8031",
            "INVENTORY_FAIL": "false",
        },
    },
    {
        "name": "shipping",
        "port": 8030,
        "dir": os.path.join(AGENTS_DIR, "shipping"),
        "env": {},
    },
]

SIDECAR_MODULE_DIR = os.path.normpath(
    os.path.join(BASE_DIR, "..", "..", "modules", "iatp")
)


def start_agent(agent: dict) -> subprocess.Popen:
    env = {**os.environ, **agent["env"]}
    cmd = [
        sys.executable, "-m", "uvicorn",
        "agent:app",
        "--host", "0.0.0.0",
        "--port", str(agent["port"]),
        "--reload",
    ]
    print(f"  Starting {agent['name']:10s} on port {agent['port']}  (dir={agent['dir']})")
    proc = subprocess.Popen(
        cmd,
        cwd=agent["dir"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return proc


def start_sidecar(name: str, port: int, agent_port: int,
                  agent_id: str, trust_level: str = "verified_partner",
                  reversibility: str = "full",
                  retention: str = "ephemeral") -> subprocess.Popen | None:
    """Start an IATP sidecar from the modules directory."""
    if not os.path.isdir(SIDECAR_MODULE_DIR):
        print(f"  ⚠ IATP module not found at {SIDECAR_MODULE_DIR} — skipping sidecar {name}")
        return None
    env = {
        **os.environ,
        "IATP_AGENT_URL": f"http://localhost:{agent_port}",
        "IATP_PORT": str(port),
        "IATP_AGENT_ID": agent_id,
        "IATP_TRUST_LEVEL": trust_level,
        "IATP_REVERSIBILITY": reversibility,
        "IATP_RETENTION": retention,
    }
    cmd = [
        sys.executable, "-m", "uvicorn",
        "iatp.main:app",
        "--host", "0.0.0.0",
        "--port", str(port),
    ]
    print(f"  Starting {name:20s} on port {port}")
    proc = subprocess.Popen(
        cmd,
        cwd=SIDECAR_MODULE_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return proc


def main() -> None:
    print("=" * 60)
    print("  IATP Battery Purchase Demo — Local Launcher")
    print("=" * 60)
    print()

    procs: list[subprocess.Popen] = []

    # Start agents
    print("Starting agents:")
    for agent in AGENTS:
        p = start_agent(agent)
        procs.append(p)

    print()
    print("Starting IATP sidecars:")
    sidecars = [
        ("copilot-sidecar", 8001, 8000, "copilot-orchestrator", "verified_partner", "full", "ephemeral"),
        ("payment-sidecar", 8011, 8010, "payment-processor", "verified_partner", "full", "temporary"),
        ("amazon-sidecar", 8021, 8020, "amazon-marketplace", "trusted", "full", "temporary"),
        ("shipping-sidecar", 8031, 8030, "shipping-carrier", "trusted", "none", "ephemeral"),
    ]
    for name, port, agent_port, agent_id, trust, rev, ret in sidecars:
        p = start_sidecar(name, port, agent_port, agent_id, trust, rev, ret)
        if p:
            procs.append(p)

    print()
    print("=" * 60)
    print("  All services starting...")
    print()
    print("  Agent URLs:")
    for agent in AGENTS:
        print(f"    {agent['name']:10s} → http://localhost:{agent['port']}")
    print()
    print("  Sidecar URLs:")
    for name, port, *_ in sidecars:
        print(f"    {name:20s} → http://localhost:{port}")
    print()
    print("  Run the demo:  python orchestrator.py")
    print("  Press Ctrl+C to stop all services")
    print("=" * 60)

    # Wait for Ctrl+C
    try:
        while True:
            # Check if any process died
            for p in procs:
                if p.poll() is not None:
                    # Read remaining output
                    out, _ = p.communicate()
                    if out:
                        print(out.decode(errors="replace")[-500:])
            time.sleep(2)
    except KeyboardInterrupt:
        print("\n\nShutting down all services...")
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass
        for p in procs:
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()
        print("Done.")


if __name__ == "__main__":
    main()
