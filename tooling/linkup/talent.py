"""Talent search backed by Linkup's /search endpoint (https://docs.linkup.so).

Uses depth "deep" (agentic, up to 10 search iterations) with structured output, so one
synchronous call returns JSON matching the schema below.
"""

import os

from linkup import LinkupClient

REQUIRED_ENV_KEYS = ("LINKUP_API_KEY",)

DEPTH = "deep"  # ~5-30s and $0.055 per call with structured output; "standard" is ~1-3s and $0.006
MAX_COUNT = 20


def _output_schema() -> dict:
    person = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "role": {"type": "string", "description": "Current job title"},
            "organisation": {"type": "string", "description": "Current company, fund or institution"},
            "location": {"type": "string", "description": "City and country where they are based"},
            "notable_for": {"type": "string", "description": "One sentence on why they stand out"},
            "uk_links": {"type": "string", "description": "Existing ties to the UK or UK Government, or 'none found'"},
            "source_urls": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["name", "role", "organisation", "location", "notable_for", "uk_links", "source_urls"],
    }
    return {
        "type": "object",
        "properties": {"talents": {"type": "array", "items": person}},
        "required": ["talents"],
    }


def find_talents_linkup(country: str, domain: str, count: int) -> dict:
    """Find high-profile people in a domain who are based in a country, using Linkup deep web search.

    Fast (seconds to about half a minute). Returns profiles with role, organisation, location,
    why they are notable, existing UK links and source URLs.
    """
    count = max(1, min(int(count), MAX_COUNT))
    client = LinkupClient(api_key=os.environ["LINKUP_API_KEY"])
    data = client.search(
        query=(
            f"Find {count} high-profile people in {domain} who currently live or primarily work in {country}: "
            "founders of fast-growing companies, investors, C-suite executives or world-leading researchers. "
            "For each person, find their current role and organisation, why they are notable, "
            "and any existing links to the UK (study, work, investments, UK Government roles)."
        ),
        depth=DEPTH,
        output_type="structured",
        structured_output_schema=_output_schema(),
    )

    talents = data.get("talents", []) if isinstance(data, dict) else []
    return {"source": "linkup", "country": country, "domain": domain, "talents": talents[:count]}
