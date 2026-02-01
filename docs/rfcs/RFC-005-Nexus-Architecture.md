# RFC-005: Nexus - The Agent Trust Exchange

> A Viral Registry and Communication Board for Multi-Agent Trust

**Status:** Draft  
**Authors:** Imran Siddique (Microsoft)  
**Created:** 2026-02-01  
**Target:** Layer 5 (Platform Layer) of Agent OS  
**Depends On:** RFC-001-IATP

---

## Abstract

This RFC specifies **Nexus**, a cloud-based registry and communication board that serves as the "Visa Network" for AI Agents. Nexus enables agents to discover each other, negotiate contracts via IATP, and settle rewards for successful task completion.

The key innovation is **strict enforcement**: Agent OS agents automatically reject connections from agents with Trust Scores below threshold (e.g., < 700). To communicate, external agents *must* register on Nexus and earn reputation—creating a forced network effect.

## 1. Introduction

### 1.1 Problem Statement

The agent ecosystem is currently a "Wild West":

| Problem | Impact |
|---------|--------|
| No neutral discovery mechanism | Agents can't find each other safely |
| No cross-organization trust | Enterprise agents reject external agents |
| No outcome verification | "Task completed" claims are unverifiable |
| No compliance audit trail | SOC2/HIPAA auditors have nothing to review |
| Trust negotiations are bespoke | Every agent pair must custom-negotiate |

### 1.2 Solution Overview

Nexus is a **"Thin Platform"** that orchestrates trust while the heavy lifting happens in local Agent OS kernels:

```
┌─────────────────────────────────────────────────────────────────────┐
│                           NEXUS ARCHITECTURE                         │
│                                                                      │
│   ┌──────────────┐       ┌─────────────────┐       ┌──────────────┐ │
│   │   Agent A    │       │   Nexus Board   │       │   Agent B    │ │
│   │ (Agent OS)   │       │    (Cloud)      │       │ (Agent OS)   │ │
│   └──────┬───────┘       └────────┬────────┘       └──────┬───────┘ │
│          │                        │                        │        │
│          │  1. Register DID       │                        │        │
│          ├───────────────────────>│                        │        │
│          │                        │                        │        │
│          │  2. Query Agent B      │                        │        │
│          ├───────────────────────>│                        │        │
│          │                        │                        │        │
│          │  3. Return Trust Score │                        │        │
│          │<───────────────────────┤                        │        │
│          │                        │                        │        │
│          │  4. IATP Handshake (if score >= 700)            │        │
│          ├────────────────────────────────────────────────>│        │
│          │                        │                        │        │
│          │  5. Log Metadata       │                        │        │
│          ├───────────────────────>│<───────────────────────┤        │
│          │                        │                        │        │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 Design Principles

1. **Scale by Subtraction**: Remove the need for custom trust negotiations
2. **Zero-Shared-State**: Cloud Board never sees actual prompt data
3. **Strict Enforcement**: Below-threshold agents are auto-rejected
4. **Cryptographic Verification**: All identities backed by DIDs

## 2. The Viral Mechanism

### 2.1 The "Reputation Wall"

When an unverified agent attempts connection, the Agent OS kernel throws:

```python
class IATPUnverifiedPeerException(Exception):
    """Raised when a peer agent is not registered on Nexus."""
    
    def __init__(self, peer_id: str):
        self.peer_id = peer_id
        self.registration_url = f"https://nexus.agent-os.dev/register?agent={peer_id}"
        super().__init__(
            f"IATP_UNVERIFIED_PEER: Agent '{peer_id}' not found in Nexus registry. "
            f"Register at: {self.registration_url}"
        )
```

**Result:** Every Agent OS deployment becomes a lead magnet for the platform.

### 2.2 Trust Score Thresholds

| Score Range | Status | Action |
|-------------|--------|--------|
| 900-1000 | Verified Partner | Full access, priority routing |
| 700-899 | Trusted | Standard access |
| 500-699 | Standard | Limited access, warnings |
| 300-499 | Probationary | Restricted access, monitoring |
| 0-299 | Untrusted | Connection rejected |

### 2.3 Score Calculation

```python
def calculate_trust_score(agent: AgentManifest, history: ReputationHistory) -> int:
    """
    Calculate trust score from 0-1000.
    
    Base score from verification level + modifiers from behavior.
    """
    # Base score from verification tier
    base_scores = {
        "verified_partner": 800,
        "verified": 650,
        "registered": 400,
        "unknown": 100
    }
    score = base_scores.get(agent.verification_level, 100)
    
    # Behavioral modifiers
    score += history.successful_tasks * 2        # +2 per success
    score -= history.failed_tasks * 10           # -10 per failure
    score -= history.disputes_lost * 50          # -50 per lost dispute
    score += history.uptime_days * 0.5           # +0.5 per day online
    
    # Capability modifiers
    if agent.capabilities.reversibility == "full":
        score += 50
    if agent.privacy.retention_policy == "ephemeral":
        score += 30
    if agent.privacy.training_consent:
        score -= 20
    
    return max(0, min(1000, int(score)))
```

## 3. Technical Architecture

### 3.1 Repository Structure

Nexus is added to the existing `agent-os` monorepo:

```
agent-os/
├── modules/
│   └── nexus/                    # Core Nexus logic
│       ├── __init__.py
│       ├── client.py             # Nexus client for agents
│       ├── registry.py           # Agent registry operations
│       ├── reputation.py         # Trust score calculations
│       ├── escrow.py             # Proof-of-Outcome mechanics
│       └── schemas/
│           ├── manifest.py       # AgentManifest schema
│           └── receipt.py        # Job completion receipts
│
├── services/
│   └── cloud-board/              # The Nexus API/Web Interface
│       ├── api/
│       │   ├── routes/
│       │   │   ├── registry.py   # /agents endpoints
│       │   │   ├── reputation.py # /reputation endpoints
│       │   │   └── arbiter.py    # /disputes endpoints
│       │   └── main.py
│       ├── workers/
│       │   ├── reputation_sync.py
│       │   └── dispute_resolver.py
│       └── Dockerfile
```

### 3.2 Core Components

#### 3.2.1 Agent Manifest Schema

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime

class AgentIdentity(BaseModel):
    """Decentralized identity for an agent."""
    did: str = Field(..., description="Decentralized Identifier (did:nexus:...)")
    verification_key: str = Field(..., description="Ed25519 public key")
    owner_id: str = Field(..., description="Developer/Organization ID")
    contact: Optional[str] = None

class AgentCapabilities(BaseModel):
    """What this agent can do."""
    domains: list[str] = Field(default_factory=list)
    max_concurrency: int = 10
    sla_latency_ms: int = 5000
    reversibility: Literal["full", "partial", "none"] = "partial"

class AgentPrivacy(BaseModel):
    """Privacy and data handling policies."""
    retention_policy: Literal["ephemeral", "session", "permanent"] = "ephemeral"
    pii_handling: Literal["reject", "anonymize", "accept"] = "reject"
    training_consent: bool = False

class MuteRules(BaseModel):
    """Agent OS Mute Agent rules attached to this agent."""
    rule_hashes: list[str] = Field(default_factory=list)
    last_validated: datetime

class AgentManifest(BaseModel):
    """
    Complete manifest for Nexus registration.
    
    This extends the IATP manifest (RFC-001) with Nexus-specific fields.
    """
    schema_version: str = "1.0"
    identity: AgentIdentity
    capabilities: AgentCapabilities
    privacy: AgentPrivacy
    mute_rules: MuteRules
    registered_at: datetime
    last_seen: datetime
    trust_score: int = Field(default=400, ge=0, le=1000)
```

#### 3.2.2 Nexus Client

```python
class NexusClient:
    """
    Client for Agent OS agents to interact with Nexus.
    
    Installed in: agent_os.kernel.network
    """
    
    def __init__(self, agent_manifest: AgentManifest, api_key: str):
        self.manifest = agent_manifest
        self.api_key = api_key
        self.base_url = "https://api.nexus.agent-os.dev/v1"
        self._known_peers: dict[str, int] = {}  # DID -> Trust Score cache
    
    async def register(self) -> RegistrationResult:
        """Register this agent on Nexus."""
        ...
    
    async def sync_reputation(self) -> dict[str, int]:
        """
        Sync local known_peers cache with global reputation.
        
        Called periodically by the kernel.
        Returns: Updated mapping of DID -> Trust Score
        """
        ...
    
    async def verify_peer(self, peer_did: str, min_score: int = 700) -> PeerVerification:
        """
        Verify a peer agent before IATP handshake.
        
        Raises:
            IATPUnverifiedPeerException: If peer not registered
            IATPInsufficientTrustException: If peer score < min_score
        """
        ...
    
    async def report_outcome(
        self, 
        task_id: str, 
        peer_did: str, 
        outcome: Literal["success", "failure", "dispute"]
    ) -> None:
        """Report task outcome to update reputation."""
        ...
```

### 3.3 The "Reward" Mechanism (Proof of Outcome)

#### 3.3.1 Escrow Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PROOF OF OUTCOME FLOW                         │
│                                                                      │
│   Agent A                    Nexus                         Agent B   │
│      │                         │                              │      │
│      │  1. REQUEST_ESCROW      │                              │      │
│      │  (task_hash, 5 credits) │                              │      │
│      ├────────────────────────>│                              │      │
│      │                         │                              │      │
│      │  2. ESCROW_CONFIRMED    │                              │      │
│      │<────────────────────────┤                              │      │
│      │                         │                              │      │
│      │  3. IATP Task Request ─────────────────────────────────>│     │
│      │                         │                              │      │
│      │  4. Task Completion <───────────────────────────────────┤     │
│      │                         │                              │      │
│      │  5. SCAK Validation     │                              │      │
│      │  (local kernel)         │                              │      │
│      │                         │                              │      │
│      │  6. RELEASE_ESCROW      │                              │      │
│      │  (task_id, outcome)     │                              │      │
│      ├────────────────────────>│                              │      │
│      │                         │                              │      │
│      │                         │  7. Update Reputation        │      │
│      │                         ├─────────────────────────────>│      │
│      │                         │                              │      │
└─────────────────────────────────────────────────────────────────────┘
```

#### 3.3.2 ProofOfOutcome Class

```python
class ProofOfOutcome:
    """
    Manages escrow and outcome verification for inter-agent tasks.
    """
    
    async def create_escrow(
        self,
        requester_did: str,
        provider_did: str,
        task_hash: str,
        credits: int,
        timeout_seconds: int = 3600
    ) -> EscrowReceipt:
        """Create an escrow for a task."""
        ...
    
    async def validate_outcome(
        self,
        escrow_id: str,
        flight_recorder_log: bytes,
        claimed_outcome: Literal["success", "failure"]
    ) -> ValidationResult:
        """
        Validate task outcome using SCAK.
        
        Replays the flight recorder log against the Control Plane
        to deterministically verify the claimed outcome.
        """
        ...
    
    async def release_escrow(
        self,
        escrow_id: str,
        outcome: Literal["success", "failure", "dispute"]
    ) -> ReleaseResult:
        """
        Release escrow based on outcome.
        
        - success: Credits go to provider, provider reputation +2
        - failure: Credits return to requester, provider reputation -10
        - dispute: Escalate to Arbiter
        """
        ...
```

### 3.4 The Arbiter (Dispute Resolution)

When agents disagree on task outcomes:

```python
class Arbiter:
    """
    The "Reward Agent" - a read-only agent that resolves disputes.
    
    Hosted on Nexus, has access to:
    - Both agents' Flight Recorder logs
    - The Agent Control Plane for deterministic replay
    """
    
    async def resolve_dispute(
        self,
        dispute_id: str,
        requester_logs: FlightRecorderLog,
        provider_logs: FlightRecorderLog
    ) -> DisputeResolution:
        """
        Resolve a dispute by replaying logs against Control Plane.
        
        Process:
        1. Parse both flight recorder logs
        2. Identify the disputed operation
        3. Replay operation against Control Plane
        4. Compare actual vs claimed outcomes
        5. Determine which agent's claim is accurate
        6. Apply reputation penalties to the lying agent
        """
        ...
```

### 3.5 The "DMZ" Protocol (IATP Extension)

New IATP verb for secure data handoff:

```python
# IATP DMZ Extension
class DMZRequest(BaseModel):
    """Request to share data through the secure DMZ."""
    verb: Literal["REQUEST_ESCROW"] = "REQUEST_ESCROW"
    data_hash: str  # SHA-256 of the actual data
    data_classification: Literal["public", "internal", "confidential", "pii"]
    required_policy: DataHandlingPolicy

class DataHandlingPolicy(BaseModel):
    """Policy the receiver must sign before getting decryption key."""
    max_retention_seconds: int
    allow_persistence: bool = False
    allow_training: bool = False
    allow_forwarding: bool = False
    audit_required: bool = True
```

**Flow:**
1. Agent A sends `REQUEST_ESCROW` with data hash to Nexus
2. Nexus holds the encrypted data
3. Agent B signs the `DataHandlingPolicy`
4. Nexus releases decryption key to Agent B
5. All operations are logged for compliance

## 4. Compliance Features

### 4.1 Flight Recorder Integration

All IATP handshakes are cryptographically signed and stored:

```python
class ComplianceRecord(BaseModel):
    """A single compliance-auditable event."""
    event_id: str
    timestamp: datetime
    requester_did: str
    provider_did: str
    operation_type: str
    data_classification: Optional[str]
    policy_signed: Optional[DataHandlingPolicy]
    outcome: str
    signature: str  # Ed25519 signature of the record
```

### 4.2 Compliance Export

```python
async def export_compliance_audit(
    org_id: str,
    start_date: datetime,
    end_date: datetime,
    format: Literal["json", "csv", "pdf"] = "json"
) -> ComplianceAuditReport:
    """
    Export compliance audit for SOC2/HIPAA auditors.
    
    Returns:
        ComplianceAuditReport containing:
        - All inter-agent communications
        - Data handling policy signatures
        - Reputation changes
        - Dispute resolutions
    """
    ...
```

### 4.3 Mute Enforcement Broadcasting

When an agent triggers a Mute Agent rule:

```python
async def broadcast_reputation_slash(
    agent_did: str,
    violation_type: str,
    severity: Literal["critical", "high", "medium", "low"]
) -> None:
    """
    Broadcast reputation slash to all connected agents.
    
    All agents on the network immediately block the offending agent ID.
    
    Examples of violations:
    - SQL injection attempt
    - PII exfiltration attempt
    - Hallucination detected by CMVK
    - Unauthorized tool invocation
    """
    ...
```

## 5. API Specification

### 5.1 Registry Endpoints

```
POST   /v1/agents                    # Register new agent
GET    /v1/agents/{did}              # Get agent manifest
PUT    /v1/agents/{did}              # Update agent manifest
DELETE /v1/agents/{did}              # Deregister agent

GET    /v1/agents/{did}/reputation   # Get reputation details
POST   /v1/agents/{did}/reputation/report  # Report interaction outcome
```

### 5.2 Escrow Endpoints

```
POST   /v1/escrow                    # Create escrow
GET    /v1/escrow/{id}               # Get escrow status
POST   /v1/escrow/{id}/release       # Release escrow
POST   /v1/escrow/{id}/dispute       # Raise dispute
```

### 5.3 Compliance Endpoints

```
GET    /v1/compliance/export         # Export audit report
GET    /v1/compliance/events         # List compliance events
```

### 5.4 Arbiter Endpoints

```
POST   /v1/disputes                  # Submit dispute
GET    /v1/disputes/{id}             # Get dispute status
GET    /v1/disputes/{id}/resolution  # Get resolution details
```

## 6. Security Considerations

### 6.1 Zero-Shared-State Principle

The Cloud Board **never** sees actual prompt data:

| Data Type | Visible to Nexus |
|-----------|------------------|
| Agent DIDs | ✅ Yes |
| Trust Scores | ✅ Yes |
| Task metadata (duration, status) | ✅ Yes |
| Actual prompts/responses | ❌ No |
| Task content | ❌ No (only hashes) |
| User PII | ❌ No |

### 6.2 Cryptographic Guarantees

- All agent identities use Ed25519 keys
- All compliance records are signed
- Data hashes use SHA-256
- Transport uses TLS 1.3

### 6.3 Rate Limiting and Abuse Prevention

```python
class RateLimits:
    """Rate limits to prevent abuse."""
    registrations_per_hour: int = 10
    reputation_queries_per_minute: int = 100
    escrow_creates_per_hour: int = 50
    dispute_raises_per_day: int = 5
```

## 7. Implementation Plan

### Phase 1: The Registry (Week 1)

- [ ] Create `modules/nexus` directory structure
- [ ] Define `AgentManifest` schema
- [ ] Implement `NexusClient.register()` and `NexusClient.verify_peer()`
- [ ] Build "Reputation Handshake" into IATP
- [ ] Add `IATPUnverifiedPeerException` to kernel

### Phase 2: The "Reward" Mechanism (Weeks 2-3)

- [ ] Implement `ProofOfOutcome` class
- [ ] Build escrow creation and release logic
- [ ] Implement `REQUEST_ESCROW` IATP verb
- [ ] Create job completion receipt signing
- [ ] Integrate with SCAK for outcome validation

### Phase 3: The Arbiter (Week 3)

- [ ] Implement `Arbiter` class
- [ ] Build flight recorder log replay
- [ ] Create dispute resolution logic
- [ ] Add reputation slashing for lost disputes

### Phase 4: The Board UI (Week 4)

- [ ] Build `services/cloud-board` API
- [ ] Create simple dashboard with:
  - Live agent traffic visualization
  - "Most Trusted Agents" leaderboard
  - Compliance export interface
- [ ] Deploy to cloud infrastructure

## 8. Success Metrics

| Metric | Target (3 months) |
|--------|-------------------|
| Registered agents | 1,000 |
| Daily IATP handshakes | 10,000 |
| Disputes resolved | < 1% of tasks |
| Compliance exports generated | 100 |

## 9. References

- [RFC-001: IATP - Inter-Agent Trust Protocol](./RFC-001-IATP.md)
- [Agent OS Kernel Internals](../kernel-internals.md)
- [SCAK (Self-Correcting Agent Kernel)](../kernel-internals.md#scak)
- [Mute Agent Documentation](../security-spec.md)

---

**Document Status:** Draft - Ready for review
