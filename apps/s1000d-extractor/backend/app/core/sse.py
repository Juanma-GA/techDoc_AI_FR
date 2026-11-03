"""Cooperative cancellation and event transport for threaded local jobs."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from threading import Event

import structlog
from fastapi import Request
from sse_starlette.sse import EventSourceResponse

from app.core.errors import AppError

log = structlog.get_logger(__name__)


class JobCancelled(Exception):
    pass


class Progress:
    def __init__(self, loop: asyncio.AbstractEventLoop, queue: asyncio.Queue, cancelled: Event) -> None:
        self.loop = loop
        self.queue = queue
        self.cancelled = cancelled

    def check_cancelled(self) -> None:
        if self.cancelled.is_set():
            raise JobCancelled()

    def emit(self, event: str, data: dict) -> None:
        self.check_cancelled()
        self.loop.call_soon_threadsafe(self.queue.put_nowait, (event, data))

    def __call__(self, step: str, pct: int) -> None:
        self.emit("progress", {"step": step, "pct": pct})


def stream_threaded_job(
    request: Request,
    work: Callable[[Progress], dict],
    *,
    session_data: dict,
    error_code: str,
) -> EventSourceResponse:
    async def events():
        queue: asyncio.Queue = asyncio.Queue()
        cancelled = Event()
        progress = Progress(asyncio.get_running_loop(), queue, cancelled)

        def run() -> dict:
            progress.check_cancelled()
            result = work(progress)
            progress.check_cancelled()
            return result

        task = asyncio.create_task(asyncio.to_thread(run))
        getter = None
        try:
            yield {"event": "session", "data": json.dumps(session_data)}
            while True:
                if await request.is_disconnected():
                    return
                getter = asyncio.create_task(queue.get())
                done, _ = await asyncio.wait(
                    {getter, task},
                    timeout=0.25,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if getter in done:
                    event, data = getter.result()
                    yield {"event": event, "data": json.dumps(data)}
                else:
                    getter.cancel()
                    await asyncio.gather(getter, return_exceptions=True)
                if task.done() and queue.empty():
                    break
            try:
                result = task.result()
            except JobCancelled:
                return
            except Exception as exc:
                log.exception("stream_job_failed", error_code=error_code, error_type=type(exc).__name__)
                code = exc.code if isinstance(exc, AppError) else error_code
                yield {"event": "error", "data": json.dumps({"code": code, "message": str(exc)})}
                return
            yield {"event": "done", "data": json.dumps(result)}
        finally:
            cancelled.set()
            if getter is not None and not getter.done():
                getter.cancel()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, *([getter] if getter is not None else []), return_exceptions=True)

    return EventSourceResponse(events())
