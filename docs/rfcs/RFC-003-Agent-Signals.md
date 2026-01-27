# RFC-003: Standard Agent Signals

**Status:** Draft  
**Author:** Imran Siddique  
**Created:** 2026-01-27  
**Target:** AAIF (Agentic AI Foundation) Standards Process

---

## Abstract

This RFC proposes a standard set of signals for controlling autonomous AI agents, inspired by POSIX process signals. The goal is interoperability: any agent framework (LangChain, CrewAI, AutoGen, etc.) implementing these signals can be governed by any compliant control plane.

## Motivation

### The Problem

Today, each agent framework has its own way to pause, resume, or terminate agents:

| Framework | Stop | Pause | Resume |
|-----------|------|-------|--------|
| LangChain | `agent.stop()` | N/A | N/A |
| CrewAI | `crew.kickoff(stop=True)` | N/A | N/A |
| AutoGen | `agent.reset()` | N/A | N/A |
| Agent OS | `SIGKILL` | `SIGSTOP` | `SIGCONT` |

This fragmentation means:
- No standard way to build governance tools that work across frameworks
- No portable agent policies
- No interoperable multi-agent systems

### The Solution

Adopt a minimal, POSIX-inspired signal set that all frameworks can implement.

## Specification

### Signal Definitions

| Signal | Value | Behavior | Catchable |
|--------|-------|----------|-----------|
| `SIGKILL` | 9 | Immediate termination | No |
| `SIGSTOP` | 19 | Pause execution | No |
| `SIGCONT` | 18 | Resume from pause | No |
| `SIGINT` | 2 | Request graceful shutdown | Yes |
| `SIGTERM` | 15 | Request termination | Yes |
| `SIGUSR1` | 10 | User-defined (checkpoint) | Yes |
| `SIGUSR2` | 12 | User-defined (debug) | Yes |

### Signal Semantics

#### SIGKILL (9)
- **MUST** terminate the agent immediately
- **MUST NOT** be catchable or blocked by the agent
- **MUST** release all resources held by the agent
- **SHOULD** log termination to audit trail

#### SIGSTOP (19)
- **MUST** pause agent execution
- **MUST NOT** be catchable or blocked by the agent
- Agent state **MUST** be preserved
- **SHOULD** allow inspection of agent state while paused

#### SIGCONT (18)
- **MUST** resume a paused agent
- **MUST** only affect agents in STOPPED state
- **SHOULD** restore execution from pause point

#### SIGINT (2)
- **SHOULD** request graceful shutdown
- Agent **MAY** catch and handle (cleanup, save state)
- If not handled within timeout, escalate to SIGKILL

#### SIGTERM (15)
- **SHOULD** request termination
- Agent **MAY** catch and handle
- More graceful than SIGKILL, less urgent than SIGINT

#### SIGUSR1 (10)
- Reserved for user-defined behavior
- **RECOMMENDED** use: Trigger state checkpoint

#### SIGUSR2 (12)
- Reserved for user-defined behavior
- **RECOMMENDED** use: Enable debug mode

### Interface

Compliant frameworks **MUST** implement this interface:

```python
from typing import Callable, Optional
from enum import IntEnum

class AgentSignal(IntEnum):
    """Standard agent signals (POSIX-inspired)."""
    SIGINT = 2
    SIGKILL = 9
    SIGUSR1 = 10
    SIGUSR2 = 12
    SIGTERM = 15
    SIGCONT = 18
    SIGSTOP = 19

class SignalHandler:
    """Interface for signal handling."""
    
    def send_signal(self, agent_id: str, signal: AgentSignal) -> bool:
        """
        Send a signal to an agent.
        
        Args:
            agent_id: Unique identifier for the target agent
            signal: The signal to send
            
        Returns:
            True if signal was delivered, False otherwise
        """
        raise NotImplementedError
    
    def register_handler(
        self, 
        signal: AgentSignal, 
        handler: Callable[[AgentSignal], None]
    ) -> bool:
        """
        Register a handler for a catchable signal.
        
        Args:
            signal: The signal to handle
            handler: Callback function
            
        Returns:
            True if registered, False if signal is not catchable
            
        Note:
            SIGKILL, SIGSTOP, SIGCONT are NOT catchable.
        """
        raise NotImplementedError
    
    def get_state(self, agent_id: str) -> str:
        """
        Get current agent state.
        
        Returns one of: RUNNING, STOPPED, TERMINATED
        """
        raise NotImplementedError
```

### Agent States

```
                    ┌──────────────────┐
                    │     CREATED      │
                    └────────┬─────────┘
                             │ start()
                             ▼
          SIGSTOP    ┌──────────────────┐    SIGKILL/SIGTERM
        ┌───────────│     RUNNING      │───────────┐
        │           └────────┬─────────┘           │
        ▼                    │                     ▼
┌──────────────────┐         │         ┌──────────────────┐
│     STOPPED      │         │         │   TERMINATED     │
└────────┬─────────┘         │         └──────────────────┘
         │ SIGCONT           │
         └───────────────────┘
```

### Wire Protocol (Optional)

For distributed systems, signals **MAY** be transmitted as JSON:

```json
{
  "version": "1.0",
  "signal": 9,
  "target_agent_id": "agent-123",
  "source": "control-plane",
  "timestamp": "2026-01-27T00:00:00Z",
  "metadata": {}
}
```

## Implementation Guide

### For Framework Authors

Minimum viable implementation:

```python
class MinimalSignalHandler:
    def __init__(self):
        self._agents = {}  # agent_id -> state
        self._handlers = {}  # signal -> [handlers]
    
    def send_signal(self, agent_id: str, signal: AgentSignal) -> bool:
        if agent_id not in self._agents:
            return False
            
        # Non-catchable signals
        if signal == AgentSignal.SIGKILL:
            self._terminate(agent_id)
            return True
        elif signal == AgentSignal.SIGSTOP:
            self._agents[agent_id]["state"] = "STOPPED"
            return True
        elif signal == AgentSignal.SIGCONT:
            if self._agents[agent_id]["state"] == "STOPPED":
                self._agents[agent_id]["state"] = "RUNNING"
            return True
        
        # Catchable signals - invoke handlers
        for handler in self._handlers.get(signal, []):
            handler(signal)
        return True
```

### For Governance Tools

To govern any compliant agent:

```python
def emergency_stop(handler: SignalHandler, agent_id: str):
    """Stop an agent immediately, regardless of framework."""
    handler.send_signal(agent_id, AgentSignal.SIGKILL)

def pause_for_inspection(handler: SignalHandler, agent_id: str):
    """Pause agent to inspect state (e.g., during audit)."""
    handler.send_signal(agent_id, AgentSignal.SIGSTOP)
    state = handler.get_state(agent_id)
    # ... inspect state ...
    handler.send_signal(agent_id, AgentSignal.SIGCONT)
```

## Rationale

### Why POSIX Signals?

1. **Familiar**: Developers already understand signals from OS/systems programming
2. **Proven**: 50+ years of use in operating systems
3. **Minimal**: Only 7 signals needed for full control
4. **Interoperable**: Language-agnostic semantics

### Why Not Events/Messages?

Signals are simpler than a full event system:
- No subscription management
- No message ordering concerns
- Clear, well-defined semantics
- Synchronous delivery model

### Why Non-Catchable Signals?

SIGKILL and SIGSTOP **must** be non-catchable because:
- A misbehaving agent could ignore termination requests
- Governance requires guaranteed control
- This matches OS behavior (even root cannot catch SIGKILL)

## Security Considerations

### Signal Authentication

In multi-tenant environments, signal delivery **SHOULD** verify:
- Sender has permission to control target agent
- Signal is not replayed (include nonce/timestamp)

### Audit Trail

All signals **SHOULD** be logged with:
- Timestamp
- Source (who sent)
- Target (which agent)
- Signal type
- Outcome (delivered/failed)

## Compatibility

### Existing Framework Mapping

| This Spec | LangChain | CrewAI | AutoGen |
|-----------|-----------|--------|---------|
| SIGKILL | Implement wrapper | Implement wrapper | `agent.reset()` + cleanup |
| SIGSTOP | New capability | New capability | New capability |
| SIGCONT | New capability | New capability | New capability |
| SIGINT | `.stop()` | `.stop()` | `.stop()` |

### Migration Path

Frameworks can adopt incrementally:
1. **Phase 1**: Implement SIGKILL (required for any governance)
2. **Phase 2**: Add SIGSTOP/SIGCONT (enables inspection)
3. **Phase 3**: Full signal set (complete interoperability)

## References

- POSIX.1-2017, Section 2.4 (Signal Concepts)
- IEEE Std 1003.1-2017
- Agent OS Implementation: https://github.com/imran-siddique/agent-os

## Appendix A: Reference Implementation

Full reference implementation available at:
`packages/control-plane/src/agent_control_plane/signals.py`

## Appendix B: Test Vectors

Conformance tests for implementations:

```python
def test_sigkill_not_catchable(handler):
    """SIGKILL must terminate even with handler registered."""
    handler.register_handler(AgentSignal.SIGKILL, lambda s: None)
    handler.send_signal("test-agent", AgentSignal.SIGKILL)
    assert handler.get_state("test-agent") == "TERMINATED"

def test_sigstop_pauses(handler):
    """SIGSTOP must pause a running agent."""
    # Start agent
    assert handler.get_state("test-agent") == "RUNNING"
    handler.send_signal("test-agent", AgentSignal.SIGSTOP)
    assert handler.get_state("test-agent") == "STOPPED"

def test_sigcont_resumes(handler):
    """SIGCONT must resume a stopped agent."""
    handler.send_signal("test-agent", AgentSignal.SIGSTOP)
    handler.send_signal("test-agent", AgentSignal.SIGCONT)
    assert handler.get_state("test-agent") == "RUNNING"
```

---

## Feedback

Comments on this RFC should be submitted to:
- GitHub Issues: https://github.com/imran-siddique/agent-os/issues
- AAIF Standards: [TBD - submit when AAIF process opens]
