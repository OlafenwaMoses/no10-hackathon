"""Runs the talent-scouting agent for a search and stores its CSV.

On Vercel the @subscribe handler becomes a private, queue-triggered function
(see [[tool.vercel.subscribers]] in pyproject.toml). Locally, service.jobs calls
process() directly in the API process.
"""

import asyncio

from tessaract import OpenAIProvider, Tessaract
from vercel.queue import Message, subscribe

from agent import find_talents
from service import jobs, search_spec, storage


def run_search(search: dict) -> tuple[bytes, int]:
    """Run the agent and return its CSV (UTF-8 with a byte-order mark, for Excel) and row count."""
    client = Tessaract(providers={"oai": OpenAIProvider()})
    tools, functions = find_talents.load_tools()
    _, _, history = find_talents.run_agent(client, tools, functions, prompt=search_spec.agent_prompt(search))
    professionals = find_talents.add_avatars(
        find_talents.extract_professionals(client, tools, history, limit=search["numResults"])
    )
    return find_talents.to_csv(professionals).encode("utf-8-sig"), len(professionals)


async def process(search_id: str) -> None:
    """Run one search and store its CSV, or record why it failed."""
    async with storage.open_store() as blob:
        record = await jobs.read_record(blob, search_id)
        if record is None or record["status"] == "ready":
            return  # deleted, or already done by an earlier delivery

        try:
            # The agent is synchronous; a thread keeps the event loop free (to renew the queue lease on Vercel)
            csv_bytes, rows = await asyncio.to_thread(run_search, record["search"])
        except Exception as exc:
            record.update(status="failed", error=f"{type(exc).__name__}: {exc}", finished_at=jobs.now())
        else:
            await jobs.write_csv(blob, search_id, csv_bytes)
            record.update(status="ready", rows=rows, finished_at=jobs.now())
        await jobs.write_record(blob, record)


# A run that dies (for example at the time limit) is redelivered once, then left for STALE_AFTER to expire
@subscribe(topic=jobs.TOPIC, max_attempts=2)
async def handle_search(message: Message[dict[str, object]]) -> None:
    await process(message.payload["id"])
