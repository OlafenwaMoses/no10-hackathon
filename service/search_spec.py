"""A talent search: the request fields, the brief the agent searches for, and the cache key.

The fields match the GTT talent dashboard's CreateSearchBody, and the brief templates are
ported from its query builder, so both systems look for the same people:
https://github.com/magerags/no10-hackathon (src/api/types.ts, src/api/pipeline/queries.ts)
"""

import hashlib
import re
import unicodedata

ALL = "all"
CATEGORIES = ("founder", "investor", "highly_talented", "hnwi", "c_suite", "researcher")
SECTORS = ("digital_tech", "ai", "life_sciences", "clean_energy", "pan_economy")
REGIONS = ("usa", "india", "singapore", "brazil", "americas_other", "europe", "asia_other", "other")
MAX_PER_TOOL = 20  # each tooling/<name>/talent.py caps count at 20

REGION_PHRASES = {
    "usa": "the United States",
    "india": "India",
    "singapore": "Singapore",
    "brazil": "Brazil",
    "americas_other": "Canada, Mexico or Latin America (outside the United States and Brazil)",
    "europe": "continental Europe",
    "asia_other": "Asia, the Middle East or Australia (outside India and Singapore)",
}

SECTOR_TERMS = {
    "digital_tech": {
        "field": "software, fintech, cybersecurity, quantum and deep tech",
        "companies": "software, fintech, cybersecurity, quantum computing, semiconductor and deep tech companies",
        "research": "computer science, quantum computing, semiconductors, cybersecurity or robotics",
        "talent": "senior engineers and technical leaders at leading software, fintech, quantum and semiconductor companies",
    },
    "ai": {
        "field": "artificial intelligence",
        "companies": "AI companies building foundation models, AI infrastructure and applied AI products",
        "research": "artificial intelligence, machine learning, deep learning, reinforcement learning or AI safety",
        "talent": "research scientists and engineers at frontier AI labs such as OpenAI, Google DeepMind, Anthropic and Meta AI",
    },
    "life_sciences": {
        "field": "biotech, pharmaceuticals, medtech and life sciences",
        "companies": "biotech, pharmaceutical, medtech, diagnostics and healthtech companies",
        "research": "biomedical science, genomics, drug discovery, synthetic biology, immunology or neuroscience",
        "talent": "senior scientists and R&D leaders at leading biotech and pharmaceutical companies",
    },
    "clean_energy": {
        "field": "climate tech and clean energy",
        "companies": "climate tech and clean energy companies in renewables, batteries, hydrogen, fusion, grid and carbon removal",
        "research": "renewable energy, energy storage, batteries, fusion, hydrogen, carbon capture or climate science",
        "talent": "senior engineers and scientists at leading clean energy, battery, fusion and climate tech companies",
    },
    "pan_economy": {
        "field": "high-growth companies across sectors",
        "companies": "high-growth, venture-backed companies across technology, life sciences, energy and consumer sectors",
        "research": "science, engineering or economics",
        "talent": "exceptional operators and technical leaders at the world's fastest-growing companies",
    },
    ALL: {
        "field": "AI, digital technology, life sciences and clean energy",
        "companies": "AI, deep tech, biotech, medtech, climate tech and clean energy companies",
        "research": "artificial intelligence, computer science, biomedical science or clean energy",
        "talent": "senior scientists, engineers and technical leaders at leading AI, deep tech, biotech and clean energy companies",
    },
}

CATEGORY_TEMPLATES = {
    "founder": "founders and CEOs of venture-backed {companies} that have raised Series A or later funding",
    "investor": "partners and principals at venture capital and growth equity firms that invest in {field} companies",
    "hnwi": "angel investors, family office principals and exited founders who back {field} startups",
    "c_suite": "CEOs, CTOs, chief scientific officers and other C-suite executives of large, established {companies}",
    "researcher": "professors, principal investigators and lab heads with highly cited research in {research}",
    "highly_talented": "exceptional {talent}, including major award winners and 30 Under 30 honourees in {field}",
}


def normalise(text: str | None) -> str:
    """Lowercase with single spaces, so case and spacing don't make two searches different."""
    return " ".join((text or "").split()).lower()


def _slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    if len(slug) > 30:  # keep ids short; the hash keeps long names distinct
        slug = f"{slug[:23]}-{hashlib.sha256(slug.encode()).hexdigest()[:6]}"
    return slug


def region_phrase(search: dict) -> str | None:
    """Where the people should be based, or None for all regions."""
    if search["region"] == "other":
        return search["customRegion"]
    return REGION_PHRASES.get(search["region"])


def generated_brief(search: dict) -> str:
    """The brief built from category, sector and region, used when there is no custom query."""
    terms = SECTOR_TERMS[search["sector"]]
    phrase = region_phrase(search)
    location = f"based in {phrase}, outside the United Kingdom" if phrase else "based outside the United Kingdom"
    categories = CATEGORIES if search["category"] == ALL else (search["category"],)
    people = [CATEGORY_TEMPLATES[category].format(**terms) for category in categories]
    if len(people) == 1:
        return f"{people[0]}, {location}"
    return f"a mix of {'; '.join(people)}; all {location}"


def cache_key(search: dict) -> str:
    """The text that decides whether two searches are the same search.

    With a custom query, only the query text and the number of people count, since the query
    replaces the generated brief. Otherwise every field counts.
    """
    if search["query"]:
        return f"query:{normalise(search['query'])}|{search['numResults']}"
    return (
        f"fields:{search['category']}|{search['sector']}|{search['region'] or 'global'}"
        f"|{normalise(search['customRegion'])}|{search['numResults']}"
    )


def search_id(search: dict) -> str:
    """A readable id, e.g. "investor-clean-energy-europe-10", or "query-<hash>-10" for a custom query."""
    if search["query"]:
        return f"query-{hashlib.sha256(cache_key(search).encode()).hexdigest()[:16]}-{search['numResults']}"
    region = search["region"] or "global"
    if region == "other":
        region = f"other-{_slug(search['customRegion'])}"
    return f"{search['category']}-{search['sector']}-{region}-{search['numResults']}".replace("_", "-")


def agent_prompt(search: dict) -> str:
    """The prompt the agent runs for this search."""
    brief = search["query"] or generated_brief(search)
    country = region_phrase(search) or "anywhere outside the United Kingdom"
    domain = SECTOR_TERMS[search["sector"]]["field"]
    per_tool = min(search["numResults"], MAX_PER_TOOL)
    return (
        f"Find {search['numResults']} people who match this search brief: {brief}\n\n"
        "They are candidates for the Global Talent Taskforce to approach about moving to, or expanding into, "
        f"the UK. Call every available tool once with country {country!r}, domain {domain!r}, "
        f"count {per_tool}, and query set to the search brief above, word for word."
    )
