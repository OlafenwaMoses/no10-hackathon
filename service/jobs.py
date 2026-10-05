"""Talent-search jobs and their storage (see service.storage).

A job's id comes from its search (see search_spec.search_id), so a repeated search finds the
earlier job, and its cached CSV, instead of running the agent again.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone

from vercel.blob import AsyncBlobClient, BlobError, BlobNotFoundError
from vercel.queue import send

from service import search_spec, storage

TOPIC = "talent-searches"
STALE_AFTER = timedelta(minutes=30)  # a run is at most ~14 minutes; a pending job this old has died
_local_runs: set[asyncio.Task] = set()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path(search_id: str, extension: str) -> str:
    return f"talent-searches/{search_id}.{extension}"


async def read_record(blob: AsyncBlobClient, search_id: str) -> dict | None:
    try:
        result = await blob.get(_path(search_id, "json"), access="private", use_cache=False)
    except BlobNotFoundError:
        return None
    return json.loads(result.content)


async def write_record(blob: AsyncBlobClient, record: dict, overwrite: bool = True) -> None:
    await blob.put(
        _path(record["id"], "json"),
        json.dumps(record).encode(),
        access="private",
        content_type="application/json",
        overwrite=overwrite,
    )


async def read_csv(blob: AsyncBlobClient, search_id: str) -> bytes:
    result = await blob.get(_path(search_id, "csv"), access="private", use_cache=False)
    return result.content


async def write_csv(blob: AsyncBlobClient, search_id: str, data: bytes) -> None:
    await blob.put(
        _path(search_id, "csv"), data, access="private", content_type="text/csv; charset=utf-8", overwrite=True
    )


def is_stale(record: dict) -> bool:
    return datetime.now(timezone.utc) - datetime.fromisoformat(record["requested_at"]) > STALE_AFTER


async def dispatch(search_id: str, idempotency_key: str) -> None:
    """Queue the agent run on Vercel. Locally there is no queue, so run it in this process."""
    if storage.LOCAL_DATA_DIR:
        from service import worker  # imported here because it loads the agent, which the Vercel API doesn't need

        task = asyncio.create_task(worker.process(search_id))
        _local_runs.add(task)  # keep a reference so the run isn't garbage-collected before it finishes
        task.add_done_callback(_local_runs.discard)
    else:
        await send(TOPIC, {"id": search_id}, idempotency_key=idempotency_key)


async def start(blob: AsyncBlobClient, search: dict) -> dict:
    """Return the existing job for this search, or create one and queue the agent run."""
    search_id = search_spec.search_id(search)
    key = search_spec.cache_key(search)
    record = {"id": search_id, "search": search, "cache_key": key, "status": "pending", "requested_at": now()}
    previous = None
    try:
        await write_record(blob, record, overwrite=False)  # fails if the job exists, so one request creates it
    except BlobError:
        previous = await read_record(blob, search_id)
        if previous is None:
            raise
        # The id only hashes a custom query, so confirm the stored text really is the same search
        same_search = previous.get("cache_key") == key
        in_progress = previous["status"] == "pending" and not is_stale(previous)
        if same_search and (previous["status"] == "ready" or in_progress):
            return previous  # the cached result, or a run already in progress
        await write_record(blob, record)  # a different search, or the last run failed or died: run it

    # Requests racing to re-run the same failed job share this key, so the queue drops the duplicates
    generation = previous["requested_at"] if previous else "first"
    try:
        await dispatch(search_id, f"{search_id}:{generation}")
    except Exception as exc:
        await write_record(blob, {**record, "status": "failed", "error": f"Could not queue the search: {exc}"})
        raise
    return record
