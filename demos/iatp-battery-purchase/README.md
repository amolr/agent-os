# IATP Battery Purchase Demo

Real-world multi-party agent transaction demonstrating IATP trust infrastructure.

## Scenario

A user purchases a battery from Amazon using Copilot. 4 agents across 3 organizations coordinate with cryptographic identity verification, trust scoring, and tamper-evident audit trails.

| Agent | Port | Sidecar Port | Organization |
|-------|------|-------------|--------------|
| Copilot Orchestrator | 8000 | 8001 | Microsoft |
| Payment Agent | 8010 | 8011 | Bank/Stripe |
| Amazon Marketplace | 8020 | 8021 | Amazon |
| Shipping Agent | 8030 | 8031 | UPS/FedEx |

## Quick Start

### Local Development (No Docker)

```bash
cd demos/iatp-battery-purchase

# Install dependencies
pip install -r requirements.txt

# Start all agents
python run_local.py

# In another terminal, run the demo
python orchestrator.py

# Open dashboard
open dashboard/index.html
```

### Docker Compose

```bash
docker-compose up --build
python orchestrator.py
open dashboard/index.html
```

## Demo Scenarios

The orchestrator runs 3 scenarios:

### 1. Happy Path (Battery Purchase)
All steps succeed: trust handshake → authorize payment → reserve inventory → shipping quote → commit.

### 2. Payment Failure
Payment capture fails after inventory is reserved. Shows SAGA compensation: inventory is automatically restored.

### 3. Low Trust Agent
Payment agent has a trust score below threshold. IATP blocks the interaction, requires human approval.

## Architecture

```
User → [Copilot Agent] ←IATP Sidecar→ [Payment Agent]
                       ←IATP Sidecar→ [Amazon Agent] ←IATP Sidecar→ [Shipping Agent]
```

Each agent has an IATP sidecar that:
- Verifies identity via capability manifest handshake
- Enforces trust policies (minimum trust score)
- Logs all actions in Merkle-chained audit trail
- Manages ephemeral credentials (15-min TTL)

## Dashboard

Open `dashboard/index.html` in a browser. Shows:
- **Transaction Flow**: Live agent status and connections
- **Audit Log**: Merkle-chained entries with integrity verification
- **Trust Scores**: Real-time agent reputation chart

## What IATP Provides (Free)

- ✅ Cryptographic agent identity (DID)
- ✅ Trust handshakes before each interaction
- ✅ Ephemeral credentials (15-min TTL)
- ✅ Delegation chains with scope narrowing
- ✅ Tamper-evident audit trail (Merkle-chained)
- ✅ Trust scoring (behavioral reputation)

## What Agents Must Implement

- ❌ Payment processing logic (authorize, capture, refund)
- ❌ Inventory management (reserve, confirm, cancel)
- ❌ SAGA transaction coordination
- ❌ Compensation logic on failure
- ❌ Domain-specific validation
