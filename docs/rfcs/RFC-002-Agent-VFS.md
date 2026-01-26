# RFC-002: Agent VFS - Virtual File System for AI Agents

> A Standard Memory Interface for Autonomous Agents

**Status:** Draft  
**Authors:** Imran Siddique (Microsoft)  
**Created:** 2026-01-26  
**Target:** AAIF Infrastructure Standards

---

## Abstract

This RFC specifies the Agent Virtual File System (VFS), a standardized memory interface for AI agents. Agent VFS provides POSIX-inspired mount points that abstract underlying storage backends (vector stores, key-value stores, file systems) into a unified hierarchical namespace.

By standardizing how agents access memory, VFS enables:
1. **Portability**: Agents work across any storage backend
2. **Isolation**: Agents can't access each other's memory without permission
3. **Auditability**: All memory operations logged to Flight Recorder
4. **Composability**: Mount different backends for different memory types

## 1. Introduction

### 1.1 Problem Statement

Current agent memory implementations are ad-hoc:

| Framework | Memory Approach | Problem |
|-----------|-----------------|---------|
| LangChain | Custom memory classes | No standard interface |
| AutoGen | Conversation history | No semantic memory |
| CrewAI | Shared context | No isolation |

This creates:
- **Vendor lock-in**: Memory tied to specific vector store
- **No portability**: Can't swap ChromaDB for Pinecone without refactoring
- **No isolation**: Agents can read each other's memory
- **No audit**: No log of what agent read/wrote

### 1.2 Solution Overview

Agent VFS provides a filesystem-like interface:

```python
# Write to working memory
vfs.write("/mem/working/current_task.json", task_data)

# Read from episodic memory
history = vfs.read("/mem/episodic/session_001.log")

# Policy is read-only from user space
policies = vfs.read("/policy/rules.yaml")  # ✓
vfs.write("/policy/rules.yaml", {})  # ✗ Permission denied
```

Backend is transparent:
```python
# Same VFS interface, different backends
vfs = AgentVFS(
    agent_id="agent-001",
    mounts={
        "/mem/working": MemoryBackend(),      # In-memory
        "/mem/episodic": RedisBackend(),      # Redis
        "/mem/semantic": PineconeBackend(),   # Vector store
    }
)
```

## 2. Filesystem Hierarchy

### 2.1 Standard Mount Points

Every agent has the following namespace:

```
/agent/{agent_id}/
├── mem/
│   ├── working/      # Ephemeral scratchpad (cleared on restart)
│   ├── episodic/     # Experience logs (append-only)
│   └── semantic/     # Long-term knowledge (vector store)
├── state/
│   └── checkpoints/  # SIGUSR1 snapshots
├── policy/           # Read-only from user space
│   ├── active.json   # Current policies
│   └── history.json  # Policy change log
├── ipc/              # Inter-process communication
│   ├── inbox/        # Incoming messages
│   └── outbox/       # Outgoing messages
└── audit/            # Flight Recorder
    └── events.jsonl  # Immutable event log
```

### 2.2 Memory Types

| Mount Point | Persistence | Access Pattern | Typical Backend |
|-------------|-------------|----------------|-----------------|
| `/mem/working` | Ephemeral | Read/Write | Memory, Redis |
| `/mem/episodic` | Durable | Append | SQLite, DynamoDB |
| `/mem/semantic` | Durable | Similarity search | Pinecone, Weaviate |
| `/state/checkpoints` | Durable | Snapshot | S3, GCS |
| `/policy` | Durable | Read-only | Config file |
| `/ipc` | Ephemeral | FIFO queue | Memory, Redis |
| `/audit` | Immutable | Append-only | File, S3 |

### 2.3 Path Resolution

Paths are resolved relative to agent namespace:

```python
# Absolute path
vfs.read("/agent/agent-001/mem/working/task.json")

# Relative path (within agent context)
vfs.read("/mem/working/task.json")  # Resolves to above

# Cross-agent access (requires IATP trust)
vfs.read("/agent/agent-002/mem/working/task.json")  # Checked by policy
```

## 3. Operations

### 3.1 Core Operations

```python
class AgentVFS:
    def read(self, path: str) -> Any:
        """Read data from path."""
        
    def write(self, path: str, data: Any) -> bool:
        """Write data to path. Returns success."""
        
    def exists(self, path: str) -> bool:
        """Check if path exists."""
        
    def list(self, path: str) -> List[str]:
        """List contents of directory."""
        
    def delete(self, path: str) -> bool:
        """Delete path. Returns success."""
        
    def checkpoint(self, name: str) -> str:
        """Create checkpoint of current state."""
        
    def restore(self, checkpoint_id: str) -> bool:
        """Restore from checkpoint."""
```

### 3.2 Serialization

VFS handles serialization transparently:

```python
# Automatic JSON serialization
vfs.write("/mem/working/config.json", {"key": "value"})
data = vfs.read("/mem/working/config.json")  # Returns dict

# Binary data
vfs.write("/mem/working/model.bin", model_bytes)

# Text
vfs.write("/mem/working/notes.txt", "Plain text")
```

### 3.3 Permissions

Permissions follow UNIX-style model:

| Path | User Space | Kernel Space |
|------|------------|--------------|
| `/mem/*` | Read/Write | Read/Write |
| `/state/*` | Read/Write | Read/Write |
| `/policy/*` | **Read-only** | Read/Write |
| `/audit/*` | **Read-only** | Append-only |
| `/ipc/inbox/*` | Read/Delete | Write |
| `/ipc/outbox/*` | Write | Read/Delete |

### 3.4 Events

All operations emit events to Flight Recorder:

```json
{
  "timestamp": "2026-01-26T10:00:00Z",
  "agent_id": "agent-001",
  "operation": "write",
  "path": "/mem/working/task.json",
  "size_bytes": 1024,
  "success": true,
  "trace_id": "abc123"
}
```

## 4. Backend Protocol

### 4.1 Backend Interface

Storage backends implement:

```python
class StorageBackend(Protocol):
    async def get(self, key: str) -> Optional[bytes]:
        """Get value by key."""
        
    async def set(self, key: str, value: bytes, ttl: int = None) -> bool:
        """Set value with optional TTL."""
        
    async def delete(self, key: str) -> bool:
        """Delete key."""
        
    async def list(self, prefix: str) -> List[str]:
        """List keys with prefix."""
        
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
```

### 4.2 Built-in Backends

| Backend | Import | Use Case |
|---------|--------|----------|
| `MemoryBackend` | `agent_os.vfs` | Development, testing |
| `RedisBackend` | `agent_os.vfs.redis` | Production, shared state |
| `S3Backend` | `agent_os.vfs.s3` | Checkpoints, large files |
| `PineconeBackend` | `agent_os.vfs.pinecone` | Semantic memory |
| `WeaviateBackend` | `agent_os.vfs.weaviate` | Semantic memory |
| `ChromaDBBackend` | `agent_os.vfs.chroma` | Local vector store |

### 4.3 Custom Backends

```python
class MyCustomBackend:
    async def get(self, key: str) -> Optional[bytes]:
        return await my_storage.fetch(key)
    
    async def set(self, key: str, value: bytes, ttl: int = None) -> bool:
        return await my_storage.store(key, value, expires=ttl)
    
    # ... implement other methods

# Mount custom backend
vfs = AgentVFS(
    agent_id="agent-001",
    mounts={"/mem/custom": MyCustomBackend()}
)
```

## 5. MCP Integration

### 5.1 VFS as MCP Resource

VFS paths are exposed as MCP resources:

```
Resource URI: vfs://{agent_id}/mem/working/*
Resource URI: vfs://{agent_id}/mem/episodic/*
Resource URI: vfs://{agent_id}/state/checkpoints/*
```

### 5.2 MCP Resource Template

```json
{
  "uriTemplate": "vfs://{agent_id}/{path}",
  "name": "Agent VFS",
  "mimeType": "application/octet-stream",
  "description": "Read/write agent memory through VFS"
}
```

### 5.3 MCP Tool

```json
{
  "name": "vfs_operation",
  "description": "Perform VFS operation (read, write, list, delete)",
  "inputSchema": {
    "type": "object",
    "properties": {
      "operation": {
        "type": "string",
        "enum": ["read", "write", "list", "delete", "checkpoint"]
      },
      "path": {"type": "string"},
      "data": {"type": "object"}
    },
    "required": ["operation", "path"]
  }
}
```

## 6. Security

### 6.1 Isolation

Each agent has its own namespace. Cross-agent access requires:

1. **IATP Trust**: Requesting agent must have sufficient trust score
2. **Scope**: Target agent's manifest must allow the scope
3. **Policy**: Kernel policy must permit the access

```python
# Agent A trying to read Agent B's memory
result = vfs.read("/agent/agent-b/mem/working/data.json")

# Kernel checks:
# 1. Does Agent A have IATP trust >= 7 with Agent B?
# 2. Does Agent B's manifest include scope "data:read"?
# 3. Does policy allow cross-agent memory access?
```

### 6.2 Encryption

Sensitive paths can be encrypted at rest:

```python
vfs = AgentVFS(
    agent_id="agent-001",
    encryption={
        "/mem/working/*": "aes-256-gcm",
        "/state/checkpoints/*": "aes-256-gcm"
    },
    encryption_key=os.environ["VFS_KEY"]
)
```

### 6.3 Audit

All operations logged to `/audit/events.jsonl`:

```json
{"ts": "2026-01-26T10:00:00Z", "op": "read", "path": "/mem/working/x", "ok": true}
{"ts": "2026-01-26T10:00:01Z", "op": "write", "path": "/policy/y", "ok": false, "err": "permission_denied"}
```

## 7. Examples

### 7.1 Basic Usage

```python
from agent_os import AgentVFS

# Create VFS for agent
vfs = AgentVFS(agent_id="research-agent")

# Working memory (ephemeral)
vfs.write("/mem/working/current_query.txt", "What is quantum computing?")
query = vfs.read("/mem/working/current_query.txt")

# Episodic memory (durable)
vfs.write("/mem/episodic/session_001.jsonl", {
    "query": query,
    "response": "Quantum computing uses...",
    "timestamp": "2026-01-26T10:00:00Z"
})

# Checkpoint before risky operation
checkpoint_id = vfs.checkpoint("before_api_call")

# Restore if needed
if operation_failed:
    vfs.restore(checkpoint_id)
```

### 7.2 With Vector Store

```python
from agent_os import AgentVFS
from agent_os.vfs.pinecone import PineconeBackend

vfs = AgentVFS(
    agent_id="rag-agent",
    mounts={
        "/mem/semantic": PineconeBackend(
            api_key=os.environ["PINECONE_KEY"],
            index="agent-knowledge"
        )
    }
)

# Store embeddings
vfs.write("/mem/semantic/doc_001", {
    "text": "Agent OS provides...",
    "embedding": [0.1, 0.2, ...],
    "metadata": {"source": "readme"}
})

# Similarity search (backend-specific)
results = vfs.query("/mem/semantic", 
    embedding=[0.1, 0.2, ...], 
    top_k=5
)
```

### 7.3 Cross-Agent Access

```python
from agent_os import AgentVFS
from agent_os.iatp import verify_trust

# Agent A wants to read Agent B's output
async def get_collaborator_output(vfs: AgentVFS, collaborator_id: str):
    # Verify trust first
    trust = await verify_trust(collaborator_id, required_level="trusted")
    if not trust.verified:
        raise PermissionError(f"Insufficient trust with {collaborator_id}")
    
    # Now we can read
    return vfs.read(f"/agent/{collaborator_id}/ipc/outbox/result.json")
```

## 8. Implementation

### 8.1 Reference Implementation

Available at:
- Package: `agent-os-kernel` (PyPI)
- Source: `github.com/imran-siddique/agent-os/packages/control-plane`

### 8.2 Compliance Levels

| Level | Requirements |
|-------|-------------|
| **Minimal** | `/mem/working` read/write, `/policy` read-only |
| **Standard** | + `/mem/episodic`, `/audit`, permissions |
| **Full** | + `/mem/semantic`, checkpoints, encryption |

## 9. References

- [Agent OS Kernel Internals](../kernel-internals.md)
- [IATP Trust Protocol](RFC-001-IATP.md)
- [POSIX Filesystem Specification](https://pubs.opengroup.org/onlinepubs/9699919799/)
- [MCP Protocol](https://modelcontextprotocol.io/)

---

**Document Status:** Draft - Ready for AAIF review
