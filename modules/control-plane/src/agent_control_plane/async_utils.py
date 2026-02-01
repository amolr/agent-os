"""
Async Utilities - Bounded concurrency helpers

Provides utilities for controlling async task execution with backpressure
to prevent unbounded resource usage.

Research Foundations:
    - Backpressure patterns from reactive programming (Reactive Streams specification)
    - Semaphore-based rate limiting from "Fault-Tolerant Multi-Agent Systems"
      (IEEE Trans. SMC, 2024)
    - Bounded work queue patterns from distributed systems literature
"""

import asyncio
from typing import Any, Awaitable, Iterable, List, TypeVar


T = TypeVar('T')


async def gather_with_concurrency(
    max_concurrency: int,
    *tasks: Awaitable[T],
    return_exceptions: bool = False
) -> List[T]:
    """
    Execute async tasks with bounded concurrency using semaphore-based backpressure.
    
    This is a drop-in replacement for asyncio.gather() that limits the number of
    concurrent tasks to prevent resource exhaustion.
    
    Args:
        max_concurrency: Maximum number of tasks to run concurrently
        *tasks: Awaitable tasks to execute
        return_exceptions: If True, exceptions are returned as results instead of raising
        
    Returns:
        List of results in the same order as input tasks
        
    Example:
        results = await gather_with_concurrency(
            5,  # max 5 concurrent tasks
            task1(),
            task2(),
            task3(),
            ...
        )
    """
    semaphore = asyncio.Semaphore(max_concurrency)
    
    async def bounded_task(task: Awaitable[T]) -> T:
        """Wrapper that acquires semaphore before executing task"""
        async with semaphore:
            return await task
    
    # Wrap all tasks with semaphore
    bounded_tasks = [bounded_task(task) for task in tasks]
    
    # Execute with original asyncio.gather behavior
    return await asyncio.gather(*bounded_tasks, return_exceptions=return_exceptions)


async def gather_with_semaphore(
    semaphore: asyncio.Semaphore,
    *tasks: Awaitable[T],
    return_exceptions: bool = False
) -> List[T]:
    """
    Execute async tasks with an existing semaphore for concurrency control.
    
    Useful when you want to share a semaphore across multiple gather calls
    or when coordinating with other rate-limited operations.
    
    Args:
        semaphore: Existing asyncio.Semaphore to use for concurrency control
        *tasks: Awaitable tasks to execute
        return_exceptions: If True, exceptions are returned as results instead of raising
        
    Returns:
        List of results in the same order as input tasks
    """
    async def bounded_task(task: Awaitable[T]) -> T:
        """Wrapper that acquires semaphore before executing task"""
        async with semaphore:
            return await task
    
    # Wrap all tasks with semaphore
    bounded_tasks = [bounded_task(task) for task in tasks]
    
    # Execute with original asyncio.gather behavior
    return await asyncio.gather(*bounded_tasks, return_exceptions=return_exceptions)


async def process_with_bounded_queue(
    items: Iterable[Any],
    processor: Awaitable,
    max_workers: int,
    max_queue_size: int = 100
) -> List[Any]:
    """
    Process items using a bounded work queue with a fixed number of workers.
    
    This pattern provides both concurrency control (via max_workers) and
    backpressure (via max_queue_size) to prevent memory issues with large inputs.
    
    Args:
        items: Iterable of items to process
        processor: Async function that processes each item
        max_workers: Maximum number of concurrent workers
        max_queue_size: Maximum queue size (controls backpressure)
        
    Returns:
        List of processed results
        
    Example:
        async def process_item(item):
            # ... do work
            return result
            
        results = await process_with_bounded_queue(
            large_list_of_items,
            process_item,
            max_workers=10,
            max_queue_size=50
        )
    """
    queue = asyncio.Queue(maxsize=max_queue_size)
    results = []
    
    async def worker():
        """Worker that processes items from the queue"""
        while True:
            item = await queue.get()
            if item is None:  # Sentinel value to stop worker
                queue.task_done()
                break
            
            try:
                result = await processor(item)
                results.append((item, result))
            finally:
                queue.task_done()
    
    # Start workers
    workers = [asyncio.create_task(worker()) for _ in range(max_workers)]
    
    # Add items to queue
    for item in items:
        await queue.put(item)
    
    # Add sentinel values to stop workers
    for _ in range(max_workers):
        await queue.put(None)
    
    # Wait for all items to be processed
    await queue.join()
    
    # Wait for workers to finish
    await asyncio.gather(*workers)
    
    # Return just the results, not the tuples
    return [result for _, result in results]
