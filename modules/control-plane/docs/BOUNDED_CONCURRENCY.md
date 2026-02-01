# Bounded Concurrency and Backpressure

This document explains the bounded concurrency and backpressure features added to prevent resource exhaustion.

## Problem Statement

**Issue #46** identified two critical performance problems:

1. **Unbounded `asyncio.gather()`**: Using `asyncio.gather()` without limits can spawn unlimited coroutines, leading to resource exhaustion
2. **Race condition in concurrency limits**: The `max_concurrent_executions` check had a race condition (check-then-decrement pattern) that could allow more concurrent executions than intended

## Solution

### 1. Semaphore-Based Concurrency Control

The `ResourceQuota` class now uses `asyncio.Semaphore` for atomic concurrency control:

```python
from agent_control_plane import PolicyEngine, ResourceQuota

# Create quota with concurrency limit
quota = ResourceQuota(
    agent_id="my-agent",
    max_concurrent_executions=5  # Max 5 concurrent executions
)

# PolicyEngine manages the semaphore automatically
policy = PolicyEngine()
policy.set_quota("my-agent", quota)

# Acquire execution slot (async)
acquired = await policy.try_acquire_execution_slot("my-agent")
if acquired:
    try:
        # Do work...
        pass
    finally:
        # Always release the slot
        policy.release_execution_slot("my-agent")
```

### 2. Bounded `asyncio.gather()`

New utility functions prevent unbounded concurrent task execution:

```python
from agent_control_plane.async_utils import gather_with_concurrency

# Old way - unbounded concurrency (bad!)
# results = await asyncio.gather(task1(), task2(), task3(), ...)

# New way - bounded concurrency (good!)
results = await gather_with_concurrency(
    5,  # Max 5 concurrent tasks
    task1(),
    task2(),
    task3(),
    # ... any number of tasks
)
```

### 3. Bounded Work Queue

For processing large collections with backpressure:

```python
from agent_control_plane.async_utils import process_with_bounded_queue

async def process_item(item):
    # Process individual item
    return await do_work(item)

# Process with bounded concurrency and queue size
results = await process_with_bounded_queue(
    items=large_list,
    processor=process_item,
    max_workers=10,      # Max 10 concurrent workers
    max_queue_size=50    # Backpressure: max 50 items queued
)
```

## API Reference

### `ResourceQuota`

Now includes automatic semaphore initialization for thread-safe concurrency control.

**New attribute:**
- `_execution_semaphore`: `asyncio.Semaphore` - Automatically initialized with `max_concurrent_executions` value

### `PolicyEngine`

**New methods:**

#### `async try_acquire_execution_slot(agent_id: str) -> bool`

Try to acquire an execution slot for the agent using semaphore-based backpressure.

**Returns:** `True` if slot acquired, `False` if at capacity

#### `release_execution_slot(agent_id: str)`

Release an execution slot for the agent.

### Async Utilities

#### `gather_with_concurrency(max_concurrency, *tasks, return_exceptions=False)`

Execute async tasks with bounded concurrency.

**Parameters:**
- `max_concurrency`: Maximum number of tasks to run concurrently
- `*tasks`: Awaitable tasks to execute
- `return_exceptions`: If True, exceptions are returned as results

**Returns:** List of results in same order as input tasks

#### `gather_with_semaphore(semaphore, *tasks, return_exceptions=False)`

Execute async tasks with an existing semaphore for concurrency control.

**Parameters:**
- `semaphore`: Existing `asyncio.Semaphore` to use
- `*tasks`: Awaitable tasks to execute
- `return_exceptions`: If True, exceptions are returned as results

**Returns:** List of results in same order as input tasks

#### `process_with_bounded_queue(items, processor, max_workers, max_queue_size=100)`

Process items using a bounded work queue with fixed number of workers.

**Parameters:**
- `items`: Iterable of items to process
- `processor`: Async function that processes each item
- `max_workers`: Maximum number of concurrent workers
- `max_queue_size`: Maximum queue size (controls backpressure)

**Returns:** List of processed results

## Migration Guide

### For Users of `asyncio.gather()`

**Before:**
```python
results = await asyncio.gather(
    agent.execute(task1),
    agent.execute(task2),
    agent.execute(task3),
)
```

**After:**
```python
from agent_control_plane.async_utils import gather_with_concurrency

results = await gather_with_concurrency(
    10,  # Reasonable concurrency limit
    agent.execute(task1),
    agent.execute(task2),
    agent.execute(task3),
)
```

### For Users of `check_rate_limit()`

The `check_rate_limit()` method no longer checks concurrent executions (this is now handled by the semaphore). If you were relying on this check, update your code to use `try_acquire_execution_slot()` and `release_execution_slot()` instead.

**Before:**
```python
# Old pattern - race condition!
if policy.check_rate_limit(request):
    quota.current_executions += 1
    try:
        result = execute(request)
    finally:
        quota.current_executions -= 1
```

**After:**
```python
# New pattern - atomic with semaphore
if await policy.try_acquire_execution_slot(agent_id):
    try:
        result = execute(request)
    finally:
        policy.release_execution_slot(agent_id)
```

## Performance Characteristics

- **Semaphore overhead**: Minimal - O(1) acquire/release operations
- **Memory usage**: Bounded - queue size limits prevent unbounded memory growth
- **Throughput**: Configurable via `max_concurrency` and `max_workers` parameters
- **Latency**: Tasks may wait in queue if at capacity (intentional backpressure)

## Testing

Comprehensive test suite in `tests/test_bounded_concurrency.py` validates:

- Semaphore initialization
- Acquire/release operations
- Bounded gather execution
- Concurrency limits enforcement
- Exception handling
- Multi-agent independence

Run tests:
```bash
python -m unittest tests.test_bounded_concurrency -v
```

## Research Foundation

These patterns are based on established distributed systems research:

- **Backpressure**: Reactive Streams specification (reactive programming)
- **Semaphore-based rate limiting**: "Fault-Tolerant Multi-Agent Systems" (IEEE Trans. SMC, 2024)
- **Bounded work queues**: Distributed systems and concurrent programming patterns
- **Circuit breaker integration**: Release It! (Michael Nygard) - preventing cascading failures
