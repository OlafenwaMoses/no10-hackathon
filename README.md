# Global Talent Taskforce: talent-finding agent

An agent that finds high-profile international talent (founders, investors, C-suite executives and leading researchers) for the UK Global Talent Taskforce. It runs on [tessaract](https://github.com/jenniferumoke/tessaract) and [OpenAI](https://openai.com), and uses three web-research services as tools: [Exa](https://exa.ai), [Linkup](https://www.linkup.so) and [Parallel FindAll](https://parallel.ai).

## How it works

1. `agent/find_talents.py` loads `.env` and looks for `tooling/<name>/talent.py` files.
2. Each `talent.py` lists the API keys it needs. If they are set, its `find_talents_<name>(country, domain, count)` function is registered as a tool. If not, the tool is skipped and the agent says which key is missing.
3. The agent sends its hardcoded system prompt and prompt to the model. The model calls the tools, the agent runs them (at the same time when there are several) and returns the results, and the model writes a shortlist. For each person the shortlist gives their role, why they are notable, links to the UK, how likely they are to move, the Taskforce lever most likely to help, and sources.
4. The model merges everyone the tools found into one row per person. The run is saved to `results/` as a JSON record, plus a CSV of those rows. See [Results](#results).

## Tooling

The repo combines an agent framework, a model API and three web-research APIs. Every package is listed in [requirements.txt](requirements.txt).

| Tool or library | Python package | Used in | What it's for |
| --- | --- | --- | --- |
| [tessaract](https://github.com/jenniferumoke/tessaract) | [`tessaract[openai]`](https://github.com/jenniferumoke/tessaract) | `agent/find_talents.py` | The agent framework. It defines tools, messages and reasoning settings in a provider-neutral way and turns them into OpenAI API calls. |
| [OpenAI Responses API](https://openai.com) | [`openai`](https://github.com/openai/openai-python) | `agent/find_talents.py`, through tessaract | The model (`gpt-6-astra` by default). It decides which tools to call, merges their results, writes the shortlist and turns it into CSV rows. It also writes the three-word summary that names each results file. |
| [Exa Agent API](https://exa.ai) | [`exa-py`](https://github.com/exa-labs/exa-py) | `tooling/exa/talent.py` | Powers `find_talents_exa`: a multi-step research agent that returns cited profiles as JSON matching a schema. |
| [Linkup Search API](https://www.linkup.so) | [`linkup-sdk`](https://github.com/LinkupPlatform/linkup-python-sdk) | `tooling/linkup/talent.py` | Powers `find_talents_linkup`: deep web search that returns profiles as structured JSON in a single call. The cheapest of the three. |
| [Parallel FindAll API](https://parallel.ai) | [`parallel-web`](https://github.com/parallel-web/parallel-sdk-python) | `tooling/parallels/talent.py` | Powers `find_talents_parallels`: finds candidate people, checks each one against the search criteria with citations, and keeps only those that pass. The most thorough checks, but the slowest. |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | [`python-dotenv`](https://github.com/theskumar/python-dotenv) | `agent/find_talents.py` | Loads the API keys from `.env`. Which keys are set decides which talent-search tools are enabled. |

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

Only `OPENAI_API_KEY` is required. Leave a tool's key out and the agent runs without that tool. The Parallel key name is spelled `PARALLES_…`, as in this repo's `.env`.

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
| `social_link` | LinkedIn, X or other public profile URL, if a tool found one |
| `organisation` | Current company, fund or institution |
| `role` | Current job title |
| `type_of_individual` | One of Founder, Investor, Highly Talented, HNWI, C-Suite or Researcher |
| `priority_sector` | The sector the person works in, such as AI, Web or Clean Energy |
| `nationality` | Nationality, if a tool found it |

An empty cell means no tool found that detail; the model is told never to guess. Only Exa and Linkup look for email, phone, social link and nationality. The file is UTF-8 with a byte-order mark, so Excel shows accented names correctly.

To change the columns, edit `PROFESSIONAL_FIELDS` in [agent/find_talents.py](agent/find_talents.py). The CSV columns follow its order.

## Tools

| Tool                       | Service           | How it searches                                                                                   | Typical time            | Cost per call              |
| -------------------------- | ----------------- | ------------------------------------------------------------------------------------------------- | ----------------------- | -------------------------- |
| `find_talents_exa`       | [Exa Agent API](https://exa.ai) | Multi-step research agent (`effort="medium"`)                                                   | 50–75 seconds          | $0.10                      |
| `find_talents_linkup`    | [Linkup](https://www.linkup.so) `/search` | Deep agentic search with structured output                                                        | 40 seconds to 3 minutes | $0.055                     |
| `find_talents_parallels` | [Parallel FindAll](https://parallel.ai) | Generates candidates, then checks each against the criteria with citations (`generator="base"`) | about 3 minutes         | $0.25 plus $0.03 per match |

Times are from test runs asking for 5 to 10 people. Costs are the services' list prices at the time of writing. With every tool, a run asking for 10 people costs about $0.75, including OpenAI usage. Tool calls in the same turn run at the same time, so a run takes about as long as the slowest tool plus the final CSV step: about 4 minutes for 10 people.

Every tool takes the same arguments and returns the same shape:

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
      "nationality": "...",
      "source_urls": ["..."]
    }
  ]
}
```

`email`, `phone`, `social_link` and `nationality` are left out when a tool can't find them.

Notes on each tool:

- **All tools** cap `count` at 20 per call.
- **Exa** also returns `cost_usd`, the run's actual cost. Exa lists contact enrichment at $0.02 per email and $0.07 per phone number found, so a run can cost more than $0.10 when Exa finds contact details.
- **Parallel FindAll** doesn't return a separate organisation field, contact details or nationality, and doesn't check links to the UK. Its smallest run is 5 matches, so smaller counts still run with 5 and are trimmed. It also returns a `run_status` field, such as `completed (match_limit_met)`.
- **Tuning:** each `talent.py` sets its speed and cost at the top of the file (`EFFORT`, `DEPTH` or `GENERATOR`).

## Add a tool

1. Create `tooling/<name>/talent.py`.
2. Declare the keys it needs: `REQUIRED_ENV_KEYS = ("MY_SERVICE_API_KEY",)`.
3. Define `find_talents_<name>(country: str, domain: str, count: int) -> dict`. Its docstring becomes the tool description the model reads, so say what the source is good at.
4. Return a dict with a `talents` list, like the shape above. Don't return a bare list: tessaract sends a list of dicts that have a `"type"` key to OpenAI unchanged instead of encoding it as JSON.
5. Add the service's SDK to `requirements.txt` and its key to `.env`.

The agent picks the new tool up on its next run. Exceptions raised by a tool are sent back to the model as tool errors, so one failing service doesn't stop the run.

## Project layout

```
.
├── .env                     # API keys: keep out of version control
├── requirements.txt
├── agent/
│   └── find_talents.py      # the agent: prompts, tool discovery, reasoning + tool-calling loop, saving runs
├── results/                 # one JSON file and one CSV file per run
└── tooling/
    ├── exa/talent.py        # find_talents_exa: Exa Agent API
    ├── linkup/talent.py     # find_talents_linkup: Linkup deep search
    └── parallels/talent.py  # find_talents_parallels: Parallel FindAll
```

`openai` is pinned below version 3 in `requirements.txt` because tessaract 0.1.2 was built and tested against the 2.x SDK.
