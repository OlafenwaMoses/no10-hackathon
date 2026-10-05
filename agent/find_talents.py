"""Talent-scouting agent for the Global Talent Taskforce, built on tessaract.

Every tooling/<name>/talent.py that defines find_talents_<name>(country, domain, count) is
registered as a tool, as long as the API keys it lists in REQUIRED_ENV_KEYS are set in .env.
The agent then answers a hardcoded prompt with a reasoning and tool-calling loop, and saves
each run to results/<three_word_summary>_<date>_<time>.json.

Usage, from the repo root:
    python agent/find_talents.py                       # every enabled tool
    python agent/find_talents.py --tools linkup,exa    # only these tools
"""

import argparse
import importlib.util
import inspect
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from tessaract import (
    FunctionTool,
    FunctionToolResult,
    InputSchema,
    OpenAIProvider,
    Property,
    ReasoningOptions,
    SystemPrompt,
    Tessaract,
    UserMessage,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLING_DIR = REPO_ROOT / "tooling"
RESULTS_DIR = REPO_ROOT / "results"
load_dotenv(REPO_ROOT / ".env")

MODEL = "oai/" + os.environ.get("TALENT_AGENT_MODEL", "gpt-6-astra")
REASONING = ReasoningOptions(effort="low", summary="auto")
MAX_STEPS = 8

SYSTEM_PROMPT = """\
You are a talent-scouting analyst for the UK Global Talent Taskforce, which reports to No.10. \
The Taskforce identifies elite international talent (scale-up founders, C-suite executives, \
investors, high-net-worth individuals and world-leading researchers) and helps them relocate to, \
invest in, or expand their business in the UK. Priority sectors: Digital & Tech, Life Sciences \
and Clean Energy.

How to work:
- Source candidates with the find_talents_* tools. Call every available tool exactly once, \
in the same turn, with the requested country, domain and count.
- Use only facts returned by the tools. Never invent people, roles, links or URLs; write \
"unknown" when no tool provided something.
- Merge people found by more than one tool and note which tools found them.

For each person, give:
1. Name, current role and organisation, and location
2. Why they are notable (one sentence)
3. Existing links to the UK or UK Government
4. Likelihood of laying down roots in the UK (High, Medium or Low), with a one-line reason
5. The Taskforce lever most likely to help, such as a Global Talent visa, an Innovator Founder \
visa, a UK HQ or R&D site, or an investment introduction
6. Source URLs

End with one short paragraph on which tools returned results and any gaps.
"""

PROMPT = (
    "Find 5 leading people in Artificial Intelligence who are currently based in Canada and "
    "whom the Global Talent Taskforce should approach about moving to, or expanding into, the UK."
)

# Every find_talents_<name> tool takes the same arguments
TALENT_SEARCH_INPUT = InputSchema(
    properties={
        "country": Property(type="string", description="Country the people are based in, e.g. 'Canada'."),
        "domain": Property(
            type="string",
            description="Sector or field, e.g. 'Artificial Intelligence', 'Life Sciences' or 'Clean Energy'.",
        ),
        "count": Property(type="integer", description="How many people to return, from 1 to 20."),
    },
    required=["country", "domain", "count"],
    additionalProperties=False,
)


def load_tools(only: set[str] | None = None) -> tuple[list[FunctionTool], dict]:
    """Register find_talents_<name> from each tooling/<name>/talent.py whose API keys are set."""
    tools, functions = [], {}
    for talent_file in sorted(TOOLING_DIR.glob("*/talent.py")):
        name = talent_file.parent.name
        if only and name not in only:
            continue

        spec = importlib.util.spec_from_file_location(f"talent_{name}", talent_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        function_name = f"find_talents_{name}"
        missing = [key for key in module.REQUIRED_ENV_KEYS if not os.environ.get(key)]
        if missing:
            print(f"  - {function_name}: disabled, set {', '.join(missing)} in .env")
            continue

        function = getattr(module, function_name)
        tools.append(
            FunctionTool(
                name=function_name,
                description=inspect.getdoc(function),
                input_schema=TALENT_SEARCH_INPUT,
            )
        )
        functions[function_name] = function
        print(f"  + {function_name}: enabled")
    return tools, functions


def execute(call, functions: dict) -> dict:
    """Run one tool call and return a record of it, capturing failures instead of crashing the loop."""
    function = functions.get(call.name)
    started = time.monotonic()
    if function is None:
        result, is_error = f"Unknown tool {call.name!r}", True
    else:
        try:
            result, is_error = function(**call.arguments), False
        except Exception as exc:
            result, is_error = f"{type(exc).__name__}: {exc}", True
    seconds = time.monotonic() - started

    if is_error:
        print(f"  [tool] {call.name} failed after {seconds:.0f}s: {result}")
    else:
        found = len(result.get("talents", [])) if isinstance(result, dict) else "?"
        print(f"  [tool] {call.name} returned {found} people in {seconds:.0f}s")
    return {
        "tool": call.name,
        "arguments": call.arguments,
        "seconds": round(seconds, 1),
        "is_error": is_error,
        "result": result,
    }


def run_agent(client: Tessaract, tools: list[FunctionTool], functions: dict) -> tuple[str, list[dict]]:
    """Run the prompt to completion; return the final answer and a record of every tool call."""
    history = [SystemPrompt(content=SYSTEM_PROMPT), UserMessage(content=PROMPT)]
    tool_calls = []

    for _ in range(MAX_STEPS):
        response = client.send(model=MODEL, input=history, tools=tools, reasoning=REASONING)
        history.extend(response.output)

        for item in response.output:
            if item.type == "reasoning" and item.text:
                print(f"  [thinking] {item.text}")

        calls = [item for item in response.output if item.type == "function_call"]
        if not calls:
            if not response.output_text:
                raise RuntimeError(f"Model returned no answer (status: {response.status})")
            return response.output_text, tool_calls

        for call in calls:
            print(f"  [tool] {call.name}({json.dumps(call.arguments)})")
        # The tools are slow, network-bound research jobs, so run parallel calls concurrently
        with ThreadPoolExecutor(max_workers=len(calls)) as pool:
            records = list(pool.map(lambda call: execute(call, functions), calls))
        for call, record in zip(calls, records):
            history.append(
                FunctionToolResult(call_id=call.call_id, result=record["result"], is_error=record["is_error"])
            )
        tool_calls.extend(records)

    return "Stopped: too many tool-calling steps.", tool_calls


def summarise_prompt(client: Tessaract, prompt: str) -> str:
    """Summarise the prompt in three lowercase words joined by underscores, for the results file name."""
    try:
        response = client.send(
            model=MODEL,
            input=[
                SystemPrompt(
                    content="Summarise the request in exactly three lowercase words, such as "
                    "'canada ai leaders'. Reply with the three words only."
                ),
                UserMessage(content=prompt),
            ],
            reasoning=ReasoningOptions(effort="low"),
        )
        words = re.findall(r"[a-z0-9]+", response.output_text.lower())[:3]
    except Exception as exc:  # failing to name the file must not lose the run
        print(f"Could not summarise the prompt ({exc}); using a default file name")
        words = []
    return "_".join(words) or "talent_search_run"


def save_run(
    client: Tessaract, started_at: datetime, tools: list[FunctionTool], answer: str, tool_calls: list[dict]
) -> Path:
    """Write the run to results/<three_word_summary>_<date>_<time>.json and return its path."""
    finished_at = datetime.now().astimezone()
    summary = summarise_prompt(client, PROMPT)
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"{summary}_{started_at:%Y-%m-%d_%H-%M-%S}.json"
    record = {
        "summary": summary,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "model": MODEL,
        "system_prompt": SYSTEM_PROMPT,
        "prompt": PROMPT,
        "tools": [tool.name for tool in tools],
        "tool_calls": tool_calls,
        "answer": answer,
    }
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tools", help="comma-separated tooling folders to use, e.g. linkup,exa (default: all)")
    args = parser.parse_args()

    only = {name.strip() for name in args.tools.split(",") if name.strip()} if args.tools else None
    available = {path.parent.name for path in TOOLING_DIR.glob("*/talent.py")}
    if only and only - available:
        parser.error(f"unknown tools {sorted(only - available)}; available: {sorted(available)}")

    print(f"Model: {MODEL}\nTools:")
    tools, functions = load_tools(only)
    if not tools:
        sys.exit("No tools enabled: add the API keys listed above to .env")

    print(f"\nPrompt: {PROMPT}\n")
    client = Tessaract(providers={"oai": OpenAIProvider()})
    started_at = datetime.now().astimezone()
    answer, tool_calls = run_agent(client, tools, functions)
    print("\n" + answer)

    path = save_run(client, started_at, tools, answer, tool_calls)
    print(f"\nSaved to {path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
