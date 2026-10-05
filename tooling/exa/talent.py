"""Talent search backed by the Exa Agent API (https://exa.ai/docs/agent/quickstart).

Exa recommends its Agent API, not /search, for sourcing candidates: it runs multi-step
web research asynchronously and returns JSON matching the output schema below.
"""

import os

from exa_py import Exa

REQUIRED_ENV_KEYS = ("EXA_API_KEY",)

EFFORT = "medium"  # fixed $0.10 per run; "low" is cheaper and lighter, "high" more thorough
MAX_COUNT = 20
TIMEOUT_MS = 6 * 60 * 1000  # keeps a whole agent run inside the API worker's 800-second limit


def _output_schema(count: int) -> dict:
    person = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "role": {"type": "string", "description": "Current job title"},
            "organisation": {"type": "string", "description": "Current company, fund or institution"},
            "location": {"type": "string", "description": "City and country where they are based"},
            "notable_for": {"type": "string", "description": "One sentence on why they stand out"},
            "uk_links": {"type": "string", "description": "Existing ties to the UK or UK Government, or 'none found'"},
            # Optional, so they are left out when not found. Exa bills $0.02 per email and $0.07 per phone found.
            "email": {"type": "string", "format": "email", "description": "Public professional email"},
            "phone": {"type": "string", "format": "phone", "description": "Phone number with country code"},
            "social_link": {"type": "string", "format": "uri", "description": "LinkedIn, X or other public profile"},
            "image_url": {
                "type": "string",
                "format": "uri",
                "description": "Their LinkedIn or X profile photo URL, only if it certainly shows them",
            },
            "nationality": {"type": "string"},
            "source_urls": {"type": "array", "items": {"type": "string", "format": "uri"}},
        },
        "required": ["name", "role", "organisation", "location", "notable_for", "uk_links", "source_urls"],
    }
    return {
        "type": "object",
        "properties": {"talents": {"type": "array", "maxItems": count, "items": person}},
        "required": ["talents"],
    }


def find_talents_exa(country: str, domain: str, count: int, query: str | None = None) -> dict:
    """Find high-profile people in a domain who are based in a country, using Exa's research agent.

    Runs multi-step web research and returns cited profiles: role, organisation, location,
    why they are notable, existing UK links and sources. Thorough but slow (minutes, not seconds).
    """
    count = max(1, min(int(count), MAX_COUNT))
    if query:  # a brief replaces the one built from domain and country
        task, location_rule = f"Find {count} people who match this brief: {query}", ""
    else:
        task = (
            f"Find {count} high-profile people in {domain} who are based in {country}: "
            "founders, investors, C-suite executives or world-leading researchers."
        )
        location_rule = f"Only include people who currently live or primarily work in {country}. "

    exa = Exa(api_key=os.environ["EXA_API_KEY"])
    run = exa.agent.runs.create(
        query=task,
        system_prompt=(
            location_rule + "Record any existing links to the UK (study, work, investments, UK Government roles). "
            "Never guess: leave out email, phone, social_link, image_url and nationality when you cannot verify them, "
            "and use 'unknown' for any other field you cannot verify."
        ),
        output_schema=_output_schema(count),
        effort=EFFORT,
    )
    run = exa.agent.runs.poll_until_finished(run.id, poll_interval=4000, timeout_ms=TIMEOUT_MS)
    if run.status != "completed":
        raise RuntimeError(f"Exa agent run {run.id} ended {run.status}: {run.error}")

    talents = (run.output.structured or {}).get("talents", [])
    return {
        "source": "exa",
        "country": country,
        "domain": domain,
        "talents": talents[:count],
        "cost_usd": run.cost_dollars.total if run.cost_dollars else None,  # varies with contacts found
    }
