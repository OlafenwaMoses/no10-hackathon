"""Talent search backed by Parallel's FindAll API (https://docs.parallel.ai/findall-api/findall-quickstart).

FindAll generates candidate people from the web, checks each one against the match
conditions below, and keeps those that pass, with citations. Runs are asynchronous,
so this polls until the run finishes.
"""

import os
import time

from parallel import Parallel

REQUIRED_ENV_KEYS = ("PARALLES_FIND_ALL_API_KEY",)

GENERATOR = "base"  # $0.25 per run + $0.03 per match; "core" and "pro" search harder and cost more
MAX_COUNT = 20
MIN_MATCH_LIMIT = 5  # FindAll accepts match_limit from 5 to 1000
POLL_SECONDS = 5
TIMEOUT_SECONDS = 15 * 60


def _condition_value(candidate, condition: str) -> str | None:
    entry = (candidate.output or {}).get(condition)
    return entry.get("value") if isinstance(entry, dict) else None


def _source_urls(candidate, limit: int = 3) -> list[str]:
    urls = [candidate.url] + [c.url for basis in candidate.basis or [] for c in basis.citations or []]
    return list(dict.fromkeys(url for url in urls if url))[:limit]


def find_talents_parallels(country: str, domain: str, count: int) -> dict:
    """Find people in a domain who are based in a country, using Parallel FindAll.

    Every match is checked against the criteria with cited evidence, so precision is high,
    but runs are slow (often several minutes). Does not check links to the UK.
    """
    count = max(1, min(int(count), MAX_COUNT))
    client = Parallel(api_key=os.environ["PARALLES_FIND_ALL_API_KEY"])
    run = client.beta.findall.create(
        objective=(
            f"FindAll high-profile {domain} founders, investors, C-suite executives "
            f"or leading researchers based in {country}"
        ),
        entity_type="people",
        match_conditions=[
            {
                "name": "based_in_country",
                "description": f"The person currently lives or primarily works in {country}.",
            },
            {
                "name": "leader_in_domain",
                "description": (
                    f"The person is a founder, investor, C-suite executive or leading researcher "
                    f"in {domain} with a notable, verifiable track record."
                ),
            },
        ],
        generator=GENERATOR,
        match_limit=max(count, MIN_MATCH_LIMIT),
    )

    deadline = time.monotonic() + TIMEOUT_SECONDS
    while run.status.is_active and time.monotonic() < deadline:
        time.sleep(POLL_SECONDS)
        run = client.beta.findall.retrieve(run.findall_id)
    if run.status.is_active:  # timed out: stop the run so it stops billing, keep the matches so far
        client.beta.findall.cancel(run.findall_id)

    result = client.beta.findall.result(run.findall_id)
    status = result.run.status
    matched = [c for c in result.candidates if c.match_status == "matched"][:count]
    if not matched and status.status == "failed":
        raise RuntimeError(f"FindAll run {run.findall_id} failed ({status.termination_reason})")

    talents = [
        {
            "name": c.name,
            "role": _condition_value(c, "leader_in_domain"),
            "location": _condition_value(c, "based_in_country"),
            "notable_for": c.description,
            "uk_links": "not checked by this source",
            "source_urls": _source_urls(c),
        }
        for c in matched
    ]
    return {
        "source": "parallels",
        "country": country,
        "domain": domain,
        "talents": talents,
        "run_status": f"{status.status} ({status.termination_reason})",
    }
