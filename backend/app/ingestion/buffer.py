import asyncio
from typing import List, Callable, Any
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class BufferConfig:
    max_size: int = 1000
    flush_interval_seconds: float = 1.0
    max_retries: int = 3


class AsyncBuffer:
    def __init__(
        self,
        config: BufferConfig = None,
        flush_callback: Callable[[List[Any]], Any] = None,
    ):
        self.config = config or BufferConfig()
        self.flush_callback = flush_callback
        self._buffer: List[Any] = []
        self._lock = asyncio.Lock()
        self._flush_task: asyncio.Task = None
        self._running = False
    
    async def start(self):
        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())
    
    async def stop(self):
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self.flush()
    
    async def add(self, item: Any):
        async with self._lock:
            self._buffer.append(item)
            if len(self._buffer) >= self.config.max_size:
                await self._do_flush()
    
    async def add_batch(self, items: List[Any]):
        async with self._lock:
            self._buffer.extend(items)
            if len(self._buffer) >= self.config.max_size:
                await self._do_flush()
    
    async def flush(self):
        async with self._lock:
            await self._do_flush()
    
    async def _do_flush(self):
        if not self._buffer or not self.flush_callback:
            return
        
        items = self._buffer[:]
        self._buffer = []
        
        for attempt in range(self.config.max_retries):
            try:
                await self.flush_callback(items)
                return
            except Exception as e:
                logger.error(f"Flush attempt {attempt + 1} failed: {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
        
        logger.error(f"All flush attempts failed, dropping {len(items)} items")
    
    async def _flush_loop(self):
        while self._running:
            await asyncio.sleep(self.config.flush_interval_seconds)
            await self.flush()
    
    @property
    def size(self) -> int:
        return len(self._buffer)


class BackpressureController:
    def __init__(self, max_pending: int = 10000, sample_rate_min: float = 0.1):
        self.max_pending = max_pending
        self.sample_rate_min = sample_rate_min
        self._pending_count = 0
        self._sample_rate = 1.0
    
    def should_accept(self) -> bool:
        if self._pending_count >= self.max_pending:
            return False
        
        if self._sample_rate < 1.0:
            import random
            return random.random() < self._sample_rate
        
        return True
    
    def record_pending(self, count: int = 1):
        self._pending_count += count
        self._adjust_sample_rate()
    
    def record_processed(self, count: int = 1):
        self._pending_count = max(0, self._pending_count - count)
        self._adjust_sample_rate()
    
    def _adjust_sample_rate(self):
        utilization = self._pending_count / self.max_pending
        
        if utilization > 0.9:
            self._sample_rate = self.sample_rate_min
        elif utilization > 0.7:
            self._sample_rate = 0.5
        elif utilization > 0.5:
            self._sample_rate = 0.75
        else:
            self._sample_rate = 1.0
    
    @property
    def current_sample_rate(self) -> float:
        return self._sample_rate
    
    @property
    def pending_count(self) -> int:
        return self._pending_count
