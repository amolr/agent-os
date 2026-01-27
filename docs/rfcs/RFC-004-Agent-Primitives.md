# RFC-004: Agent Primitives Specification

**Status:** Draft  
**Author:** Imran Siddique  
**Created:** 2026-01-27  
**Target:** AAIF (Agentic AI Foundation) Standards Process

---

## Abstract

This RFC specifies a minimal set of primitives for autonomous AI agents, enabling interoperability across frameworks. The primitives are: Signals (process control), VFS (memory abstraction), IPC Pipes (communication), and Syscalls (kernel interface).

## Motivation

Agent frameworks today are incompatible at the infrastructure level. An agent built with LangChain cannot be governed by a CrewAI control plane. This RFC proposes common primitives that allow:

- Portable agents (write once, run anywhere)
- Interoperable governance (one control plane for all agents)
- Standard tooling (debuggers, profilers, audit tools)

## Primitives Overview

| Primitive | Purpose | Inspired By |
|-----------|---------|-------------|
| **Signals** | Process control | POSIX signals |
| **VFS** | Memory abstraction | Unix filesystem |
| **IPC Pipes** | Agent communication | Unix pipes |
| **Syscalls** | Kernel interface | System calls |

## Primitive 1: Signals

See [RFC-003: Standard Agent Signals](RFC-003-Agent-Signals.md) for full specification.

Summary:
- SIGKILL, SIGSTOP, SIGCONT for non-catchable control
- SIGINT, SIGTERM for graceful shutdown
- SIGUSR1, SIGUSR2 for user-defined behavior

## Primitive 2: Virtual File System (VFS)

### Purpose

Provide agents with a standard memory abstraction. Instead of framework-specific memory APIs, agents read/write to a virtual filesystem.

### Mount Points

| Path | Purpose | Permissions | Persistence |
|------|---------|-------------|-------------|
| `/mem/working` | Scratchpad | Read/Write | Ephemeral |
| `/mem/episodic` | Experience log | Append-only | Persistent |
| `/mem/semantic` | Long-term knowledge | Read/Write | Persistent |
| `/state/checkpoints` | State snapshots | Read/Write | Persistent |
| `/policy` | Governance rules | Read-only | Persistent |
| `/audit` | Action log | Append-only | Immutable |

### Interface

```python
from typing import Any, Optional
from datetime import datetime

class AgentVFS:
    """Virtual File System for agent memory."""
    
    def read(self, path: str) -> Any:
        """
        Read from a virtual path.
        
        Args:
            path: Virtual path (e.g., "/mem/working/task.json")
            
        Returns:
            Contents at path (deserialized)
            
        Raises:
            PermissionError: If agent lacks read permission
            FileNotFoundError: If path doesn't exist
        """
        raise NotImplementedError
    
    def write(self, path: str, data: Any) -> None:
        """
        Write to a virtual path.
        
        Args:
            path: Virtual path
            data: Data to write (will be serialized)
            
        Raises:
            PermissionError: If path is read-only
        """
        raise NotImplementedError
    
    def append(self, path: str, data: Any) -> None:
        """
        Append to a virtual path (for logs).
        
        Args:
            path: Virtual path
            data: Data to append
        """
        raise NotImplementedError
    
    def list(self, path: str) -> list[str]:
        """List contents of a directory."""
        raise NotImplementedError
    
    def exists(self, path: str) -> bool:
        """Check if path exists."""
        raise NotImplementedError
```

### Permission Model

Agents run in "user space" and cannot access kernel paths:

```
Allowed for agents:
  /mem/*           - Agent's memory space
  /state/*         - Agent's state
  
Read-only for agents:
  /policy/*        - Governance rules
  
Forbidden for agents:
  /kernel/*        - Kernel internals
  /audit/*         - Audit log (write via syscall only)
```

### Backend Abstraction

VFS is an abstraction over physical storage:

```python
class VFSBackend:
    """Backend storage for VFS."""
    
    def get(self, key: str) -> Optional[bytes]:
        raise NotImplementedError
    
    def put(self, key: str, value: bytes) -> None:
        raise NotImplementedError
    
    def delete(self, key: str) -> None:
        raise NotImplementedError

# Implementations
class InMemoryBackend(VFSBackend): ...
class RedisBackend(VFSBackend): ...
class S3Backend(VFSBackend): ...
class VectorStoreBackend(VFSBackend): ...  # For /mem/semantic
```

## Primitive 3: IPC Pipes

### Purpose

Enable type-safe communication between agents without framework coupling.

### Interface

```python
from typing import TypeVar, Generic
from dataclasses import dataclass

T = TypeVar('T')

@dataclass
class Message(Generic[T]):
    """Typed message for IPC."""
    payload: T
    sender: str
    timestamp: datetime
    correlation_id: Optional[str] = None

class Pipe(Generic[T]):
    """Typed pipe between agents."""
    
    async def send(self, message: Message[T]) -> None:
        """Send a message through the pipe."""
        raise NotImplementedError
    
    async def receive(self) -> Message[T]:
        """Receive a message from the pipe."""
        raise NotImplementedError
    
    async def receive_timeout(self, timeout: float) -> Optional[Message[T]]:
        """Receive with timeout."""
        raise NotImplementedError
```

### Pipeline Composition

Agents can be composed into pipelines:

```python
# Unix-style: agent1 | policy_check | agent2
pipeline = Pipeline([
    research_agent,
    PolicyCheck(allowed_types=["ResearchResult"]),
    summary_agent
])

result = await pipeline.execute(input_data)
```

### Policy Enforcement

Pipes can enforce policies on messages:

```python
class PolicyPipe(Pipe[T]):
    """Pipe that enforces policy on messages."""
    
    def __init__(self, inner: Pipe[T], policy: Policy):
        self.inner = inner
        self.policy = policy
    
    async def send(self, message: Message[T]) -> None:
        if not self.policy.allows(message):
            raise PolicyViolation(f"Message blocked by policy")
        await self.inner.send(message)
```

## Primitive 4: Syscalls

### Purpose

Provide a standard interface for agents to request privileged operations from the kernel.

### Core Syscalls

| Syscall | Purpose | Example |
|---------|---------|---------|
| `execute` | Run action with policy check | `kernel.execute("db_query", {...})` |
| `audit` | Log to immutable audit trail | `kernel.audit("action_taken", {...})` |
| `checkpoint` | Save agent state | `kernel.checkpoint()` |
| `restore` | Restore from checkpoint | `kernel.restore(checkpoint_id)` |
| `getpolicy` | Read current policies | `kernel.getpolicy()` |

### Interface

```python
from typing import Any, Dict
from dataclasses import dataclass

@dataclass
class SyscallResult:
    """Result of a syscall."""
    success: bool
    data: Any
    error: Optional[str] = None
    signal: Optional[str] = None  # e.g., "SIGKILL" on violation

class KernelInterface:
    """Syscall interface for agents."""
    
    async def execute(
        self,
        action: str,
        params: Dict[str, Any],
        policies: list[str] = None
    ) -> SyscallResult:
        """
        Execute an action with policy enforcement.
        
        Args:
            action: Action name (e.g., "file_read", "api_call")
            params: Action parameters
            policies: Optional policy overrides
            
        Returns:
            SyscallResult with success/failure and any data
        """
        raise NotImplementedError
    
    async def audit(self, event: str, data: Dict[str, Any]) -> None:
        """Log an event to the immutable audit trail."""
        raise NotImplementedError
    
    async def checkpoint(self) -> str:
        """
        Create a state checkpoint.
        
        Returns:
            Checkpoint ID for later restoration
        """
        raise NotImplementedError
    
    async def restore(self, checkpoint_id: str) -> bool:
        """Restore agent state from checkpoint."""
        raise NotImplementedError
    
    def getpolicy(self) -> Dict[str, Any]:
        """Get current active policies."""
        raise NotImplementedError
```

### Execution Context

Syscalls operate within an execution context:

```python
@dataclass
class ExecutionContext:
    """Context for syscall execution."""
    agent_id: str
    policies: list[str]
    history: list[dict]  # Previous actions
    metadata: dict
    
    def to_dict(self) -> dict:
        """Serialize for stateless execution."""
        return {
            "agent_id": self.agent_id,
            "policies": self.policies,
            "history": self.history,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ExecutionContext":
        """Deserialize from dict."""
        return cls(**data)
```

## Combining Primitives

### Example: Governed Agent

```python
from agent_os import KernelInterface, AgentVFS, SignalHandler, AgentSignal

class GovernedAgent:
    def __init__(self, kernel: KernelInterface, vfs: AgentVFS):
        self.kernel = kernel
        self.vfs = vfs
        self._running = True
    
    async def run(self, task: str):
        # Read policy
        policy = self.kernel.getpolicy()
        
        # Write task to working memory
        self.vfs.write("/mem/working/current_task.txt", task)
        
        # Execute with policy enforcement
        result = await self.kernel.execute(
            action="llm_generate",
            params={"prompt": task}
        )
        
        if result.signal == "SIGKILL":
            # Policy violation - agent terminated
            return None
        
        # Log to audit trail
        await self.kernel.audit("task_completed", {
            "task": task,
            "result": result.data
        })
        
        return result.data
```

## Conformance Levels

### Level 1: Minimal (Signals Only)
- Implement SIGKILL, SIGSTOP, SIGCONT
- Enables basic governance

### Level 2: Standard (Signals + Syscalls)
- Add execute() syscall with policy enforcement
- Add audit() syscall
- Enables full governance

### Level 3: Full (All Primitives)
- Add VFS
- Add IPC Pipes
- Enables portable agents and interoperability

## Security Considerations

1. **Syscall validation**: All syscalls must validate parameters
2. **Path traversal**: VFS must prevent `../` attacks
3. **Signal authentication**: Signals must be authenticated in multi-tenant
4. **Pipe isolation**: Agents should not access other agents' pipes

## References

- RFC-003: Standard Agent Signals
- RFC-001: Inter-Agent Trust Protocol
- RFC-002: Agent VFS
- POSIX.1-2017

---

## Feedback

Submit comments via GitHub Issues:
https://github.com/imran-siddique/agent-os/issues
