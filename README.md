# Global Talent Taskforce: talent-finding agent

An agent that finds high-profile international talent (founders, investors, C-suite executives and leading researchers) for the UK Global Talent Taskforce. It runs on [tessaract](https://github.com/jenniferumoke/tessaract) and [OpenAI](https://openai.com), and uses three web-research services as tools: [Exa](https://exa.ai), [Linkup](https://www.linkup.so) and [Parallel FindAll](https://parallel.ai).

## Quick start

From this folder, fetch the pinned dashboard (first time only), then start the talent API and the dashboard together:

```bash
git submodule update --init
docker compose up --build
```

A new clone can run `git clone --recurse-submodules` instead of the first line. The dashboard is the `main` branch of our fork, [OlafenwaMoses/no10-hackathon-frontend](https://github.com/OlafenwaMoses/no10-hackathon-frontend), of the source repo [magerags/no10-hackathon](https://github.com/magerags/no10-hackathon), which is no longer publicly available.

This needs `.env` and `no10-hackathon-frontend/.dev.vars` in place first; see [Run the API and dashboard locally](#run-the-api-and-dashboard-locally).

| What | Link |
| --- | --- |
| Dashboard | [http://localhost:5173](http://localhost:5173) |
| Talent API (local) | [http://localhost:8000](http://localhost:8000) |
| Talent API docs (local) | [http://localhost:8000/docs](http://localhost:8000/docs) |

Stop both with `docker compose down`. Setup and details are in [Run the API and dashboard locally](#run-the-api-and-dashboard-locally).

Both also run on Vercel, with no local setup:

| What | Link |
| --- | --- |
| Dashboard (Vercel) | [https://no10-talent-dashboard.vercel.app](https://no10-talent-dashboard.vercel.app). It asks for a password; see [Dashboard on Vercel](#dashboard-on-vercel). |
| Talent API (Vercel) | [https://no10-talent-api.vercel.app](https://no10-talent-api.vercel.app), with docs at [/docs](https://no10-talent-api.vercel.app/docs). See [API](#api). |

## How it works

1. `agent/find_talents.py` loads `.env` and looks for `tooling/<name>/talent.py` files.
2. Each `talent.py` lists the API keys it needs. If they are set, its `find_talents_<name>(country, domain, count)` function is registered as a tool. If not, the tool is skipped and the agent says which key is missing.
3. The agent sends its hardcoded system prompt and prompt to the model. The model calls the tools, the agent runs them (at the same time when there are several) and returns the results, and the model writes a shortlist. For each person the shortlist gives their role, why they are notable, links to the UK, how likely they are to move, the Taskforce lever most likely to help, and sources.
4. The model merges everyone the tools found into one row per person. The run is saved to `results/` as a JSON record, plus a CSV of those rows. See [Results](#results).

## Tooling

The repo combines an agent framework, a model API and three web-research APIs, and is served as an API on Vercel. Every package is listed in [requirements.txt](requirements.txt).

| Tool or library | Python package | Used in | What it's for |
| --- | --- | --- | --- |
| [tessaract](https://github.com/jenniferumoke/tessaract) | [`tessaract[openai]`](https://github.com/jenniferumoke/tessaract) | `agent/find_talents.py` | The agent framework. It defines tools, messages and reasoning settings in a provider-neutral way and turns them into OpenAI API calls. |
| [OpenAI Responses API](https://openai.com) | [`openai`](https://github.com/openai/openai-python) | `agent/find_talents.py`, through tessaract | The model (`gpt-6-astra` by default). It decides which tools to call, merges their results, writes the shortlist and turns it into CSV rows. It also writes the three-word summary that names each results file. |
| [Exa Agent API](https://exa.ai) | [`exa-py`](https://github.com/exa-labs/exa-py) | `tooling/exa/talent.py` | Powers `find_talents_exa`: a multi-step research agent that returns cited profiles as JSON matching a schema. |
| [Linkup Search API](https://www.linkup.so) | [`linkup-sdk`](https://github.com/LinkupPlatform/linkup-python-sdk) | `tooling/linkup/talent.py` | Powers `find_talents_linkup`: deep web search that returns profiles as structured JSON in a single call. The cheapest of the three. |
| [Parallel FindAll API](https://parallel.ai) | [`parallel-web`](https://github.com/parallel-web/parallel-sdk-python) | `tooling/parallels/talent.py` | Powers `find_talents_parallels`: finds candidate people, checks each one against the search criteria with citations, and keeps only those that pass. The most thorough checks, but the slowest. |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | [`python-dotenv`](https://github.com/theskumar/python-dotenv) | `agent/find_talents.py` | Loads the API keys from `.env`. Which keys are set decides which talent-search tools are enabled. |
| [FastAPI](https://fastapi.tiangolo.com) | [`fastapi`](https://github.com/fastapi/fastapi) | `service/app.py` | The HTTP API: validates requests, checks the API key and serves the two endpoints. See [API](#api). |
| [Vercel](https://vercel.com) | [`vercel`](https://github.com/vercel/vercel-py) | `service/` | Hosts the API. Vercel Queues runs each search in a background worker, and a private Vercel Blob store holds job status and cached CSVs. |

Each name links to the service's website, or to its GitHub repo for libraries. Each package links to its GitHub repo. The API docs each tool follows are linked at the top of its `talent.py`.

The agent also uses three standard-library modules: `importlib` to find the `tooling/*/talent.py` files, `concurrent.futures` to run several tool calls at the same time, and `argparse` for the `--tools` option. Speed and cost for each talent-search tool are under [Tools](#tools).

## Setup

You need Python 3.11 or later.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Put your API keys in a `.env` file in the repo root:

```
OPENAI_API_KEY=...
EXA_API_KEY=...
LINKUP_API_KEY=...
PARALLES_FIND_ALL_API_KEY=...
```

| Key                           | Used by                      | Get one at                                                 |
| ----------------------------- | ---------------------------- | ---------------------------------------------------------- |
| `OPENAI_API_KEY`            | The agent's model (required) | [platform.openai.com](https://platform.openai.com/api-keys) |
| `EXA_API_KEY`               | `find_talents_exa`         | [dashboard.exa.ai](https://dashboard.exa.ai/api-keys)       |
| `LINKUP_API_KEY`            | `find_talents_linkup`      | [app.linkup.so](https://app.linkup.so)                      |
| `PARALLES_FIND_ALL_API_KEY` | `find_talents_parallels`   | [platform.parallel.ai](https://platform.parallel.ai)        |

Only `OPENAI_API_KEY` is required. Leave a tool's key out and the agent runs without that tool. The Parallel key name is spelled `PARALLES_…`, as in this repo's `.env`. For the local API (see [Run the API and dashboard locally](#run-the-api-and-dashboard-locally)), also add `API_KEY`, the key its clients must send.

## Run

From the repo root, with the virtual environment active:

```bash
python agent/find_talents.py                     # every tool whose key is set
python agent/find_talents.py --tools linkup      # one tool
python agent/find_talents.py --tools exa,linkup  # a subset
```

The agent uses `gpt-6-astra` by default. To use another OpenAI model, set `TALENT_AGENT_MODEL`, either in `.env` or on the command line:

```bash
TALENT_AGENT_MODEL=gpt-5.6-sol python agent/find_talents.py
```

To change what the agent looks for, edit `SYSTEM_PROMPT` and `PROMPT` at the top of [agent/find_talents.py](agent/find_talents.py). The default prompt asks for 10 leading people in Artificial Intelligence based in Germany.

A run prints which tools are enabled, each tool call, and then the shortlist:

```
Model: oai/gpt-6-astra
Tools:
  + find_talents_exa: enabled
  + find_talents_linkup: enabled
  + find_talents_parallels: enabled

Prompt: Find 10 leading people in Artificial Intelligence who are currently based in Germany ...

  [tool] find_talents_exa({"country": "Germany", "domain": "Artificial Intelligence", "count": 10})
  [tool] find_talents_linkup({"country": "Germany", "domain": "Artificial Intelligence", "count": 10})
  [tool] find_talents_parallels({"country": "Germany", "domain": "Artificial Intelligence", "count": 10})
  [tool] find_talents_exa returned 10 people in 78s
  [tool] find_talents_linkup returned 10 people in 121s
  [tool] find_talents_parallels returned 10 people in 152s

## Recommended shortlist: 10 Germany-based AI leaders
...

Saved to results/germany_ai_recruitment_2026-10-05_13-03-41.json
Saved 26 professionals to results/germany_ai_recruitment_2026-10-05_13-03-41.csv
```

The shortlist notes which tools found each person. People found by more than one tool are merged.

## Results

Each run is saved as two files with the same name, `results/<summary>_<date>_<time>.json` and `.csv`. For example: `results/germany_ai_recruitment_2026-10-05_13-03-41.json` and `results/germany_ai_recruitment_2026-10-05_13-03-41.csv`.

- `<summary>` is a three-word summary of the prompt, written by the model at the end of the run. If that call fails, the name falls back to `talent_search_run`.
- `<date>_<time>` is when the run started, in local time and to the second. The time uses dashes because colons aren't allowed in file names on every system.

The JSON file holds everything the run produced:

| Field                           | Contents                                                                                                                                                                                             |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `summary`                     | The three-word summary used in the file name                                                                                                                                                         |
| `started_at`, `finished_at` | ISO 8601 timestamps with UTC offset                                                                                                                                                                  |
| `model`                       | The model that ran the agent                                                                                                                                                                         |
| `system_prompt`, `prompt`   | The prompts used for the run                                                                                                                                                                         |
| `tools`                       | The tools that were enabled                                                                                                                                                                          |
| `tool_calls`                  | One entry per tool call:`tool`, `arguments`, `seconds`, `is_error` and `result`. `result` is the tool's output, including its `talents` list, or the error message if the call failed. |
| `answer`                      | The model's final shortlist, in Markdown                                                                                                                                                             |

A run is saved only when it finishes. If it stops with an error, nothing is written. The JSON is written before the CSV step, so if that step fails the JSON is still saved.

### CSV

The `.csv` file has one row per professional. After the research loop, the agent sends `CSV_PROMPT` from [agent/find_talents.py](agent/find_talents.py) and forces the model to call a `save_talents_csv` tool. The model merges people that more than one tool found into a single row. The tool's schema fixes the columns, and the agent code writes the file.

| Column | Contents |
| --- | --- |
| `first_name`, `last_name` | The person's name |
| `email` | Public professional email, if a tool found one |
| `phone` | Phone number with country code, if a tool found one |
| `social_link` | The person's own LinkedIn profile, or else their X or personal page, if a tool found one |
| `image_url` | A photo that certainly shows the person, for use as an avatar. See [Avatars](#avatars). |
| `organisation` | Current company, fund or institution |
| `role` | Current job title |
| `type_of_individual` | One of Founder, Investor, Highly Talented, HNWI, C-Suite or Researcher |
| `priority_sector` | The sector the person works in, such as AI, Web or Clean Energy |
| `nationality` | Nationality, if a tool found it |

An empty cell means no tool found that detail; the model is told never to guess. Only Exa and Linkup look for email, phone, social link, photo and nationality. The file is UTF-8 with a byte-order mark, so Excel shows accented names correctly.

#### Avatars

`image_url` holds a photo only when it certainly shows the person. After the CSV step, `add_avatars` in [agent/find_talents.py](agent/find_talents.py) checks each row:

1. If `social_link` is the person's own LinkedIn or X profile, it fetches that profile's photo with Exa. A photo on their own account is them.
2. Otherwise it uses a photo a tool supplied, but only a LinkedIn or X profile photo.
3. The photo must load as an image. LinkedIn's no-photo placeholder doesn't count.

Anything else, such as a team page, a logo or a group photo, is dropped, so some people have no avatar. A wrong face would be worse than none. The Exa lookups cost a fraction of a cent each.

To change the columns, edit `PROFESSIONAL_FIELDS` in [agent/find_talents.py](agent/find_talents.py). The CSV columns follow its order.

## Run the API and dashboard locally

[docker-compose.yml](docker-compose.yml) runs two services:
- **The talent API** from this repo.
- **The GTT talent dashboard,** in `no10-hackathon-frontend/` (see [Dashboard version](#dashboard-version)).

A search started in the dashboard goes to the local API, and the people the agent finds are added to the dashboard's database.

You need:
- Docker.
- **The dashboard:** run `git submodule update --init` once.
- **`.env`:** the agent's keys (see [Setup](#setup)), plus `API_KEY`, the key clients must send as `x-api-key`.
- **`no10-hackathon-frontend/.dev.vars`:** the dashboard's settings. It's a copy of `.env_frontend` plus two lines: `TALENT_API_URL=http://api:8000` and `TALENT_API_KEY` set to the same value as `API_KEY`.

```bash
docker compose up --build    # build and start both
docker compose logs -f api   # watch the agent's tool calls
docker compose down          # stop both
```

| Service | URL |
| --- | --- |
| Dashboard | [http://localhost:5173](http://localhost:5173) |
| Talent API | [http://localhost:8000](http://localhost:8000), with docs at [http://localhost:8000/docs](http://localhost:8000/docs) |

Locally, the API runs each search inside its own process instead of on a Vercel Queue, and caches results in `api-cache/` instead of Vercel Blob. The `LOCAL_DATA_DIR` setting in `docker-compose.yml` turns this on. The endpoints and payloads are the same as on Vercel (see [API](#api)), at `http://localhost:8000` instead.

To search from the dashboard, and for what was changed in it, see [TALENT_API.md in the dashboard fork](https://github.com/OlafenwaMoses/no10-hackathon-frontend/blob/main/TALENT_API.md).

### Dashboard version

| | Repo | Version |
| --- | --- | --- |
| Used here and on Vercel | [OlafenwaMoses/no10-hackathon-frontend](https://github.com/OlafenwaMoses/no10-hackathon-frontend), our fork of the source repo | Branch [`main`](https://github.com/OlafenwaMoses/no10-hackathon-frontend/tree/main): the talent API integration, ported from Cloudflare Workers to Vercel. Pinned at commit `02205a7`. |
| Cloudflare version | The same fork | Branch [`talent-api-integration`](https://github.com/OlafenwaMoses/no10-hackathon-frontend/tree/talent-api-integration): the same integration on Cloudflare Workers, as proposed to the source repo |
| Source repo | [magerags/no10-hackathon](https://github.com/magerags/no10-hackathon) | No longer publicly available, as of 7 October 2026 |

`no10-hackathon-frontend/` is a git submodule that follows the fork's `main` branch. This repo records the exact commit it works with. To move to newer commits on `main`, run `git submodule update --remote no10-hackathon-frontend`, then commit the new pin.

### Dashboard on Vercel

The dashboard is deployed at **https://no10-talent-dashboard.vercel.app** (Vercel project `no10-talent-dashboard`). Its searches go to the deployed talent API, and the people found are scored and added to its Postgres database.

- **Password:** the dashboard asks for one. It's `APP_PASSWORD` in `.env_vercel_dashboard` in this folder, which git ignores. To remove the password, delete `APP_PASSWORD` from the project's environment variables and redeploy.
- **Code:** the `main` branch of our fork, the same code as the submodule. The source repo, [magerags/no10-hackathon](https://github.com/magerags/no10-hackathon), runs on Cloudflare Workers, so the fork ports it to Vercel: [Nitro](https://nitro.build) serves the React app and the Hono API, and [Vercel Workflows](https://vercel.com/docs/workflows) replaces Cloudflare Workflows for the search and scoring pipeline. Its [VERCEL.md](https://github.com/OlafenwaMoses/no10-hackathon-frontend/blob/main/VERCEL.md) lists the changes.
- **Link to the API:** the project's `TALENT_API_URL` is `https://no10-talent-api.vercel.app`, and its `TALENT_API_KEY` matches the API's `API_KEY`. The other variables are copied from `.env_frontend`.
- **Database:** [Neon](https://neon.tech) Postgres on the free plan in London, named `no10-talent-dashboard-db`. It was created through the Vercel Marketplace and is connected to the project, which sets `DATABASE_URL` and the other `PG*`/`POSTGRES_*` variables. `.env_frontend` and `no10-hackathon-frontend/.dev.vars` use the same database, so the local and deployed dashboards share data. It replaced the team's PlanetScale database, which was deleted on 7 October 2026. A new, empty database needs the dashboard's tables first: in `no10-hackathon-frontend/`, run `npx --yes bun@1 install`, then `DATABASE_URL='<url>' npx --yes bun@1 x drizzle-kit migrate`.
- **Region:** functions run in London (`lhr1`).
- **Progress:** each search and candidate is a workflow run. To see their steps, open the project in Vercel and go to **Observability**, then **Workflows**.

To redeploy the dashboard, deploy the submodule folder. After changing an environment variable, redeploy for it to take effect.

```bash
cd no10-hackathon-frontend
npx vercel link --project no10-talent-dashboard --scope moses-olafenwas-projects   # first time only
npx vercel deploy --prod --scope moses-olafenwas-projects --token <your Vercel token>
```

## API

The agent also runs as an API on Vercel at **https://no10-talent-api.vercel.app**, with interactive docs at [/docs](https://no10-talent-api.vercel.app/docs). To run it locally instead, see [Run the API and dashboard locally](#run-the-api-and-dashboard-locally).

Every request to `/api/...` needs an `x-api-key` header. The key is the `API_KEY` environment variable of the `no10-talent-api` project on Vercel.

A search takes 3 to 5 minutes, so the API works in two steps.

### 1. Start a search

`POST /api/talent-searches` takes the same body as the talent dashboard's search form: `CreateSearchBody` in the dashboard's [src/api/types.ts](https://github.com/OlafenwaMoses/no10-hackathon-frontend/blob/main/src/api/types.ts). Every field is optional.

| Field | Values | Default |
| --- | --- | --- |
| `category` | Type of individual: `founder`, `investor`, `highly_talented`, `hnwi`, `c_suite`, `researcher` or `all` | `all` |
| `sector` | `digital_tech`, `ai`, `life_sciences`, `clean_energy`, `pan_economy` or `all` | `all` |
| `region` | `usa`, `india`, `singapore`, `brazil`, `americas_other`, `europe`, `asia_other` or `other`. Leave it out for all regions (global). | global |
| `customRegion` | The region when `region` is `other`, such as `Nordics`, up to 60 characters. It's ignored for other regions, and `other` without it means global. | none |
| `query` | A custom query of up to 1,000 characters. It replaces the brief built from `category`, `sector` and `region`. | none |
| `numResults` | People in total, from 1 to 50 | `10` |

Without a `query`, the API builds a search brief from `category`, `sector` and `region`, using the same templates as the dashboard. For `all` categories, the brief asks for a mix of all six types.

```bash
curl -X POST https://no10-talent-api.vercel.app/api/talent-searches \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"category": "investor", "sector": "clean_energy", "region": "europe", "numResults": 5}'
```

The response is `202 Accepted`:

```json
{
  "id": "investor-clean-energy-europe-5",
  "status": "pending",
  "message": "The search is running. Check again in a minute.",
  "status_url": "/api/talent-searches/investor-clean-energy-europe-5"
}
```

With a custom query, send it in `query`:

```bash
curl -X POST https://no10-talent-api.vercel.app/api/talent-searches \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "Series B climate-tech founders in California who studied in the UK", "numResults": 5}'
```

That search's id is `query-12f2f3747328310b-5`.

### 2. Check the search and download the CSV

```bash
curl https://no10-talent-api.vercel.app/api/talent-searches/investor-clean-energy-europe-5 -H "x-api-key: $API_KEY"
```

The response is `200 OK`. While the agent is working, `status` is `pending`:

```json
{
  "id": "investor-clean-energy-europe-5",
  "status": "pending",
  "message": "The search is running. Check again in a minute.",
  "search": {"category": "investor", "sector": "clean_energy", "region": "europe", "customRegion": null, "query": null, "numResults": 5},
  "requested_at": "2026-10-05T13:13:00+00:00"
}
```

When it's done, `status` is `ready` and `csv_base64` holds the CSV file:

```json
{
  "id": "investor-clean-energy-europe-5",
  "status": "ready",
  "message": "The search is done. Decode csv_base64 to get the CSV file.",
  "search": {"category": "investor", "sector": "clean_energy", "region": "europe", "customRegion": null, "query": null, "numResults": 5},
  "requested_at": "2026-10-05T13:13:00+00:00",
  "finished_at": "2026-10-05T13:15:43+00:00",
  "rows": 5,
  "filename": "investor-clean-energy-europe-5.csv",
  "csv_base64": "77u/Zmlyc3RfbmFtZSxsYXN0X25hbWUsZW1haWws..."
}
```

To save the CSV to a file:

```bash
curl -s https://no10-talent-api.vercel.app/api/talent-searches/investor-clean-energy-europe-5 -H "x-api-key: $API_KEY" \
  | python3 -c "import base64, json, sys; d = json.load(sys.stdin); open(d['filename'], 'wb').write(base64.b64decode(d['csv_base64']))"
```

The CSV has the columns described in [CSV](#csv), and at most `numResults` people. Each tool is asked for up to `numResults` people (20 at most per tool). The model then keeps the best matches, preferring people that more than one tool found and a balanced mix of types when `category` is `all`.

### Caching and errors

- **Without a `query`**, a search is identified by `category`, `sector`, `region` (with `customRegion`) and `numResults`. The id spells them out, for example `investor-clean-energy-europe-5` or `all-all-other-nordics-10`.
- **With a `query`**, a search is identified by the query text and `numResults` only, because the query replaces the other fields. Case and extra spaces don't matter. The id is `query-<hash>-<numResults>`, and before reusing a stored result the API checks that its query text matches.
- **A repeated search** returns `202` with `status` `ready` straight away once it's done. The agent doesn't run again, so a repeat costs nothing, and the GET returns the stored CSV. A different query text, or any other changed field, runs the agent.
- **Cost:** a new search costs about $0.55 in provider charges for 5 people.
- **A search that's still running** is returned as it is instead of being started again.
- **Failed runs:** if a run fails, the GET returns `status` `failed` with an `error`, and sending the same search again re-runs it. A search still pending after 30 minutes counts as failed.
- **Other responses:** `401` for a missing or wrong `x-api-key`, `404` for an unknown `id`, and `422` for an invalid body or `id`.

### How it's built

| Part | What it does |
| --- | --- |
| `service/app.py` | The FastAPI app. A POST records the job and puts a message on a Vercel Queue. |
| `service/worker.py` | A queue-triggered function that runs the agent for each message and stores the result. |
| `service/search_spec.py` | The request fields, the cache key and id, and the search brief. The brief templates are ported from the dashboard's query builder, so both systems look for the same people. |
| `service/jobs.py` | Job storage: each search is `talent-searches/<id>.json` (its status) and `<id>.csv`. |
| `service/storage.py` | Where jobs are stored: the private Blob store on Vercel, or a folder when `LOCAL_DATA_DIR` is set. Locally, `jobs.dispatch` also runs the worker inside the API process instead of queueing it. |
| Blob store `no10-talent-cache` | Private Vercel Blob storage in London (`lhr1`). Files are readable only with the store's token, never by a public URL. |

The Vercel project has these environment variables: `API_KEY` (plain), `OPENAI_API_KEY`, `EXA_API_KEY`, `LINKUP_API_KEY` and `PARALLES_FIND_ALL_API_KEY` (sensitive), and `BLOB_READ_WRITE_TOKEN` (added when the store was connected). Its default function time limit is 800 seconds, and each tool stops waiting after 6 minutes, so a run always finishes in time.

To deploy changes, run this from the repo root with a Vercel token for the `moses-olafenwas-projects` team. On a fresh clone, run `npx vercel link --project no10-talent-api --scope moses-olafenwas-projects` first.

```bash
npx vercel deploy --prod --scope moses-olafenwas-projects --token <your Vercel token>
```

`.vercelignore` uploads only `agent/`, `service/`, `tooling/` and `pyproject.toml`, so `.env` and `results/` stay local. Vercel installs dependencies from `pyproject.toml`, not `requirements.txt`, so keep the two lists in sync. To clear a cached result, delete its two files from the `no10-talent-cache` store in the Vercel dashboard.

## Tools

| Tool                       | Service           | How it searches                                                                                   | Typical time            | Cost per call              |
| -------------------------- | ----------------- | ------------------------------------------------------------------------------------------------- | ----------------------- | -------------------------- |
| `find_talents_exa`       | [Exa Agent API](https://exa.ai) | Multi-step research agent (`effort="medium"`)                                                   | 50–75 seconds          | $0.10                      |
| `find_talents_linkup`    | [Linkup](https://www.linkup.so) `/search` | Deep agentic search with structured output                                                        | 40 seconds to 3 minutes | $0.055                     |
| `find_talents_parallels` | [Parallel FindAll](https://parallel.ai) | Generates candidates, then checks each against the criteria with citations (`generator="base"`) | about 3 minutes         | $0.25 plus $0.03 per match |

Times are from test runs asking for 5 to 10 people. Costs are the services' list prices at the time of writing. With every tool, a run asking for 10 people costs about $0.75, including OpenAI usage. Tool calls in the same turn run at the same time, so a run takes about as long as the slowest tool plus the final CSV step: about 4 minutes for 10 people.

Every tool takes the same arguments: `country`, `domain`, `count` and an optional `query`. A `query` is a search brief that replaces the one the tool would build from country and domain. Every tool returns the same shape:

```json
{
  "source": "linkup",
  "country": "Canada",
  "domain": "Artificial Intelligence",
  "talents": [
    {
      "name": "...",
      "role": "...",
      "organisation": "...",
      "location": "...",
      "notable_for": "...",
      "uk_links": "...",
      "email": "...",
      "phone": "...",
      "social_link": "...",
      "image_url": "...",
      "nationality": "...",
      "source_urls": ["..."]
    }
  ]
}
```

`email`, `phone`, `social_link`, `image_url` and `nationality` are left out when a tool can't find them.

Notes on each tool:

- **All tools** cap `count` at 20 per call.
- **Exa** also returns `cost_usd`, the run's actual cost. Exa lists contact enrichment at $0.02 per email and $0.07 per phone number found, so a run can cost more than $0.10 when Exa finds contact details.
- **Parallel FindAll** doesn't return a separate organisation field, contact details or nationality, and doesn't check links to the UK. Its smallest run is 5 matches, so smaller counts still run with 5 and are trimmed. It also returns a `run_status` field, such as `completed (match_limit_met)`.
- **Tuning:** each `talent.py` sets its speed and cost at the top of the file (`EFFORT`, `DEPTH` or `GENERATOR`).

## Add a tool

1. Create `tooling/<name>/talent.py`.
2. Declare the keys it needs: `REQUIRED_ENV_KEYS = ("MY_SERVICE_API_KEY",)`.
3. Define `find_talents_<name>(country: str, domain: str, count: int, query: str | None = None) -> dict`. Its docstring becomes the tool description the model reads, so say what the source is good at. When `query` is set, search for that brief instead of building one from `country` and `domain`. The API always passes a brief, and the CLI passes `None`.
4. Return a dict with a `talents` list, like the shape above. Don't return a bare list: tessaract sends a list of dicts that have a `"type"` key to OpenAI unchanged instead of encoding it as JSON.
5. Add the service's SDK to `requirements.txt` and its key to `.env`.

The agent picks the new tool up on its next run. Exceptions raised by a tool are sent back to the model as tool errors, so one failing service doesn't stop the run.

## Project layout

```
.
├── .env                     # API keys: keep out of version control
├── .env_vercel_dashboard    # the deployed dashboard's password (not tracked)
├── requirements.txt
├── pyproject.toml           # dependencies and entrypoints for the Vercel deployment
├── .vercelignore            # what gets uploaded to Vercel
├── Dockerfile               # the API image used by docker-compose.yml
├── docker-compose.yml       # runs the API and the dashboard locally
├── service/
│   ├── app.py               # the API: POST and GET /api/talent-searches
│   ├── search_spec.py       # request fields, search brief and cache key
│   ├── jobs.py              # search jobs: create, cache, dispatch
│   ├── storage.py           # Vercel Blob, or a local folder
│   └── worker.py            # runs the agent for a search
├── no10-hackathon-frontend/ # the dashboard: a submodule of our fork of magerags/no10-hackathon
├── api-cache/               # searches cached by the local API (not tracked)
├── agent/
│   └── find_talents.py      # the agent: prompts, tool discovery, reasoning + tool-calling loop, saving runs
├── results/                 # one JSON file and one CSV file per run
└── tooling/
    ├── exa/talent.py        # find_talents_exa: Exa Agent API
    ├── linkup/talent.py     # find_talents_linkup: Linkup deep search
    └── parallels/talent.py  # find_talents_parallels: Parallel FindAll
```

`openai` is pinned below version 3 in `requirements.txt` because tessaract 0.1.2 was built and tested against the 2.x SDK.
