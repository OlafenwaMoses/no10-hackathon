"""HTTP API for the talent-scouting agent: start a search, then poll until its CSV is ready."""

import base64
import hmac
import os
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Path, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from service import jobs, storage
from service.search_spec import ALL, CATEGORIES, REGIONS, SECTORS

app = FastAPI(
    title="Global Talent Taskforce talent search",
    description="Find people to approach about moving to, or expanding into, the UK, as a CSV.",
)
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)

MESSAGES = {
    "pending": "The search is running. Check again in a minute.",
    "ready": "The search is done. Decode csv_base64 to get the CSV file.",
    "failed": "The search failed. Send the same search to POST /api/talent-searches to run it again.",
}


def check_api_key(key: str | None = Security(api_key_header)) -> None:
    expected = os.environ.get("API_KEY")
    if not expected or not key or not hmac.compare_digest(key, expected):
        raise HTTPException(status_code=401, detail="Missing or invalid x-api-key header")


class SearchRequest(BaseModel):
    """The talent dashboard's CreateSearchBody (github.com/magerags/no10-hackathon, src/api/types.ts)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    category: Literal[(ALL, *CATEGORIES)] = Field(default=ALL, description="Type of individual")
    sector: Literal[(ALL, *SECTORS)] = Field(default=ALL, description="Priority sector")
    region: Literal[REGIONS] | None = Field(default=None, description="Leave out for all regions (global)")
    customRegion: str | None = Field(
        default=None, max_length=60, pattern=r"^\p{L}[\p{L} .,'()&-]*$", description="The region when region is 'other'"
    )
    query: str | None = Field(
        default=None, max_length=1000, description="Custom query. Replaces the brief built from the other fields."
    )
    numResults: int = Field(default=10, ge=1, le=50, description="People in total")

    @field_validator("customRegion", "query")
    @classmethod
    def blank_is_none(cls, value: str | None) -> str | None:
        collapsed = " ".join((value or "").split())
        return collapsed or None

    @model_validator(mode="after")
    def resolve_region(self) -> "SearchRequest":
        # As in the dashboard: "other" with no custom region means global, and only "other" keeps one
        if self.region == "other" and not self.customRegion:
            self.region = None
        if self.region != "other":
            self.customRegion = None
        return self


@app.get("/")
def index() -> dict:
    return {
        "service": app.title,
        "start_search": "POST /api/talent-searches",
        "check_search": "GET /api/talent-searches/{id}",
        "docs": "/docs",
    }


@app.post("/api/talent-searches", status_code=202, dependencies=[Depends(check_api_key)])
async def start_search(request: SearchRequest) -> dict:
    """Accept a search. A search that was run before returns its cached CSV instead of running again."""
    async with storage.open_store() as blob:
        record = await jobs.start(blob, request.model_dump())
    return {
        "id": record["id"],
        "status": record["status"],
        "message": MESSAGES[record["status"]],
        "status_url": f"/api/talent-searches/{record['id']}",
    }


@app.get("/api/talent-searches/{search_id}", dependencies=[Depends(check_api_key)])
async def get_search(search_id: str = Path(pattern=r"^[a-z0-9-]{1,100}$")) -> dict:
    """Report a search's status and, once it is ready, its CSV as base64."""
    async with storage.open_store() as blob:
        record = await jobs.read_record(blob, search_id)
        if record is None:
            raise HTTPException(status_code=404, detail="No search with this id. Start one with POST /api/talent-searches")

        response = {
            "id": search_id,
            "status": record["status"],
            "message": MESSAGES[record["status"]],
            "search": record.get("search"),
            "requested_at": record["requested_at"],
        }
        if record["status"] == "ready":
            csv_bytes = await jobs.read_csv(blob, search_id)
            response |= {
                "finished_at": record["finished_at"],
                "rows": record["rows"],
                "filename": f"{search_id}.csv",
                "csv_base64": base64.b64encode(csv_bytes).decode(),
            }
        elif record["status"] == "failed":
            response["error"] = record.get("error")
    return response
