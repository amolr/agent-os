"""
Tests for bounded concurrency and semaphore-based rate limiting
"""

import unittest
import asyncio
from datetime import datetime
from agent_control_plane import (
    PolicyEngine,
    ResourceQuota,
    AgentKernel,
    ExecutionRequest,
    ActionType,
    ExecutionStatus,
)
from agent_control_plane.agent_kernel import AgentContext as KernelAgentContext
from agent_control_plane.async_utils import (
    gather_with_concurrency,
    gather_with_semaphore,
    process_with_bounded_queue,
)


class TestBoundedConcurrency(unittest.TestCase):
    """Test suite for bounded concurrency features"""
    
    def test_resource_quota_semaphore_initialization(self):
        """Test that ResourceQuota initializes semaphore correctly"""
        quota = ResourceQuota(
            agent_id="test-agent",
            max_concurrent_executions=5
        )
        
        # Verify semaphore is initialized
        self.assertIsNotNone(quota._execution_semaphore)
        # Test semaphore behavior instead of accessing private _value
        # Should be able to acquire up to max_concurrent_executions times
        async def test_semaphore():
            # Acquire 5 times should succeed
            for i in range(5):
                await quota._execution_semaphore.acquire()
            
            # 6th acquire should timeout (semaphore at capacity)
            with self.assertRaises(asyncio.TimeoutError):
                await asyncio.wait_for(
                    quota._execution_semaphore.acquire(), 
                    timeout=0.01
                )
            
            # Release all
            for i in range(5):
                quota._execution_semaphore.release()
        
        asyncio.run(test_semaphore())
    
    def test_gather_with_concurrency_basic(self):
        """Test gather_with_concurrency executes all tasks"""
        async def test_task(value):
            await asyncio.sleep(0.01)
            return value * 2
        
        async def run_test():
            results = await gather_with_concurrency(
                2,  # max 2 concurrent
                test_task(1),
                test_task(2),
                test_task(3),
                test_task(4),
            )
            return results
        
        results = asyncio.run(run_test())
        self.assertEqual(results, [2, 4, 6, 8])
    
    def test_gather_with_concurrency_limits(self):
        """Test that gather_with_concurrency actually limits concurrency"""
        concurrent_count = 0
        max_concurrent_seen = 0
        
        async def test_task(value):
            nonlocal concurrent_count, max_concurrent_seen
            concurrent_count += 1
            max_concurrent_seen = max(max_concurrent_seen, concurrent_count)
            await asyncio.sleep(0.05)
            concurrent_count -= 1
            return value
        
        async def run_test():
            # Run 10 tasks with max 3 concurrent
            tasks = [test_task(i) for i in range(10)]
            results = await gather_with_concurrency(3, *tasks)
            return results
        
        results = asyncio.run(run_test())
        
        # All tasks completed
        self.assertEqual(len(results), 10)
        # Max concurrent was respected
        self.assertLessEqual(max_concurrent_seen, 3)
        self.assertGreater(max_concurrent_seen, 0)
    
    def test_gather_with_semaphore(self):
        """Test gather_with_semaphore works with external semaphore"""
        async def test_task(value):
            await asyncio.sleep(0.01)
            return value * 3
        
        async def run_test():
            semaphore = asyncio.Semaphore(2)
            results = await gather_with_semaphore(
                semaphore,
                test_task(1),
                test_task(2),
                test_task(3),
            )
            return results
        
        results = asyncio.run(run_test())
        self.assertEqual(results, [3, 6, 9])
    
    def test_gather_with_exceptions(self):
        """Test gather_with_concurrency handles exceptions correctly"""
        async def failing_task():
            await asyncio.sleep(0.01)
            raise ValueError("Test error")
        
        async def successful_task(value):
            await asyncio.sleep(0.01)
            return value
        
        async def run_test():
            results = await gather_with_concurrency(
                2,
                successful_task(1),
                failing_task(),
                successful_task(3),
                return_exceptions=True
            )
            return results
        
        results = asyncio.run(run_test())
        
        # First and third tasks should succeed
        self.assertEqual(results[0], 1)
        self.assertEqual(results[2], 3)
        # Second task should be an exception
        self.assertIsInstance(results[1], ValueError)
    
    def test_policy_engine_acquire_release_execution_slot(self):
        """Test semaphore-based execution slot management"""
        async def run_test():
            policy = PolicyEngine()
            quota = ResourceQuota(
                agent_id="test-agent",
                max_concurrent_executions=2
            )
            policy.set_quota("test-agent", quota)
            
            # Should be able to acquire first slot
            acquired1 = await policy.try_acquire_execution_slot("test-agent")
            self.assertTrue(acquired1)
            self.assertEqual(quota.current_executions, 1)
            
            # Should be able to acquire second slot
            acquired2 = await policy.try_acquire_execution_slot("test-agent")
            self.assertTrue(acquired2)
            self.assertEqual(quota.current_executions, 2)
            
            # Should NOT be able to acquire third slot (at limit)
            acquired3 = await policy.try_acquire_execution_slot("test-agent")
            self.assertFalse(acquired3)
            self.assertEqual(quota.current_executions, 2)  # Still at 2
            
            # Release first slot
            policy.release_execution_slot("test-agent")
            self.assertEqual(quota.current_executions, 1)
            
            # Should now be able to acquire again
            acquired4 = await policy.try_acquire_execution_slot("test-agent")
            self.assertTrue(acquired4)
            self.assertEqual(quota.current_executions, 2)
            
            # Clean up - release both slots
            policy.release_execution_slot("test-agent")
            policy.release_execution_slot("test-agent")
            self.assertEqual(quota.current_executions, 0)
        
        asyncio.run(run_test())
    
    def test_concurrent_execution_with_multiple_agents(self):
        """Test that different agents have independent execution slots"""
        async def run_test():
            policy = PolicyEngine()
            
            quota1 = ResourceQuota(agent_id="agent-1", max_concurrent_executions=2)
            quota2 = ResourceQuota(agent_id="agent-2", max_concurrent_executions=3)
            
            policy.set_quota("agent-1", quota1)
            policy.set_quota("agent-2", quota2)
            
            # Acquire slots for agent-1
            acquired1 = await policy.try_acquire_execution_slot("agent-1")
            acquired2 = await policy.try_acquire_execution_slot("agent-1")
            
            self.assertTrue(acquired1)
            self.assertTrue(acquired2)
            self.assertEqual(quota1.current_executions, 2)
            
            # Agent-2 should still have all its slots available
            acquired3 = await policy.try_acquire_execution_slot("agent-2")
            self.assertTrue(acquired3)
            self.assertEqual(quota2.current_executions, 1)
            
            # Clean up
            policy.release_execution_slot("agent-1")
            policy.release_execution_slot("agent-1")
            policy.release_execution_slot("agent-2")
        
        asyncio.run(run_test())
    
    def test_check_rate_limit_no_concurrent_check(self):
        """Test that check_rate_limit no longer checks concurrent executions"""
        policy = PolicyEngine()
        quota = ResourceQuota(
            agent_id="test-agent",
            max_concurrent_executions=1,
            max_requests_per_minute=10,
        )
        policy.set_quota("test-agent", quota)
        
        # Create a mock request
        context = KernelAgentContext(
            agent_id="test-agent",
            session_id="test-session",
            created_at=datetime.now()
        )
        request = ExecutionRequest(
            request_id="test-request",
            agent_context=context,
            action_type=ActionType.FILE_READ,
            parameters={},
            timestamp=datetime.now(),
        )
        
        # check_rate_limit should pass even when concurrent executions is at max
        # (because concurrent execution check is now handled by semaphore)
        quota.current_executions = 1
        self.assertTrue(policy.check_rate_limit(request))


class TestProcessWithBoundedQueue(unittest.TestCase):
    """Test suite for process_with_bounded_queue"""
    
    def test_process_items_basic(self):
        """Test basic item processing with bounded queue"""
        async def processor(item):
            await asyncio.sleep(0.01)
            return item * 2
        
        async def run_test():
            items = [1, 2, 3, 4, 5]
            results = await process_with_bounded_queue(
                items,
                processor,
                max_workers=2,
                max_queue_size=10
            )
            return results
        
        results = asyncio.run(run_test())
        
        # All items should be processed
        self.assertEqual(len(results), 5)
        # Results should contain processed values (though order may vary)
        self.assertEqual(sorted(results), [2, 4, 6, 8, 10])


if __name__ == '__main__':
    unittest.main()
