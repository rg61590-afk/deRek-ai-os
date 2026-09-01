"""
Task queue for deRek AI OS.

A thin, purpose-built wrapper around `asyncio.Queue` holding task IDs
ready for processing. In-memory only, for this sprint — no external
broker or persistence. Wrapping it (rather than passing a bare
`asyncio.Queue` around) keeps the Task Engine's queuing contract
independent of the underlying implementation, so it can be swapped
out later without changing `TaskManager` or `TaskWorker`.
"""

from __future__ import annotations

import asyncio
from typing import Optional


class TaskQueue:
    """FIFO queue of task IDs awaiting processing."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()

    async def enqueue(self, task_id: str) -> None:
        """Add a task ID to the back of the queue."""
        await self._queue.put(task_id)

    async def dequeue(self) -> str:
        """Remove and return the next task ID, waiting if the queue is
        currently empty.

        Used by `TaskWorker.run()`'s continuous loop. Not started
        automatically in this sprint (continuous background execution,
        separate from the request/response cycle, is Event Bus &
        Workers scope — see docs/PROJECT_BIBLE.md, Long-Term Roadmap).
        """
        return await self._queue.get()

    def dequeue_nowait(self) -> Optional[str]:
        """Remove and return the next task ID if one is immediately
        available, else return `None` without waiting.

        Used by `TaskWorker.process_one()`, which is called
        synchronously from the task-creation request and must never
        block indefinitely.
        """
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    def qsize(self) -> int:
        """Number of task IDs currently waiting to be processed."""
        return self._queue.qsize()
