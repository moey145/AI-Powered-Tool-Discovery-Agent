"""Quality benchmark against live search and LLM APIs. This spends real API credits.

Usage, from advanced-agent/:  python -m evals.run [--limit N]
Exits non-zero if any query fails its checks.
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from pydantic import BaseModel, Field

from src.config import get_settings
from src.models import ResearchResult
from src.net import create_client
from src.workflow import LLM, create_workflow

MIN_TOOLS = 3
MAX_UNKNOWN_PRICING = 0.5
JUDGE_SYSTEM = """You grade a developer-tool search engine.
Given a search and the tools it returned, list only the tools that clearly do not answer the
search. A tool from an adjacent category that a developer could reasonably use is acceptable."""


class Judgement(BaseModel):
    irrelevant: list[str] = Field(description="Tool names that do not answer the search")


async def check(case: dict, result: ResearchResult, llm: LLM) -> list[str]:
    names = [company.name.casefold() for company in result.companies]
    problems = []
    if not any(expected.casefold() in name for expected in case["expect_any"] for name in names):
        problems.append(f"none of {case['expect_any']} found")
    if result.pricing_preference != case["pricing"]:
        problems.append(f"pricing read as {result.pricing_preference}, not {case['pricing']}")
    if len(names) < case.get("min_tools", MIN_TOOLS):
        problems.append(f"only {len(names)} tools")
    no_sources = [c.name for c in result.companies if not c.sources]
    if no_sources:
        problems.append(f"no sources for {no_sources}")
    no_site = [c.name for c in result.companies if not c.website]
    if no_site:
        problems.append(f"no website for {no_site}")
    unknown = [c.name for c in result.companies if c.pricing_model.value == "Unknown"]
    if names and len(unknown) / len(names) > MAX_UNKNOWN_PRICING:
        problems.append(f"pricing unknown for {unknown}")
    if names:
        listing = ", ".join(company.name for company in result.companies)
        verdict = await llm.structured(
            Judgement, JUDGE_SYSTEM, f"Search: {case['query']}\nTools: {listing}"
        )
        if verdict.irrelevant:
            problems.append(f"judged irrelevant: {verdict.irrelevant}")
    return problems


async def main(limit: int | None, delay: float) -> int:
    cases = json.loads(Path(__file__).with_name("queries.json").read_text(encoding="utf-8"))
    settings = get_settings()
    failures = 0
    async with create_client(settings) as client:
        workflow = create_workflow(settings, client)
        for index, case in enumerate(cases[:limit]):
            if index:
                await asyncio.sleep(delay)
            started = time.monotonic()
            try:
                result = await workflow.run(case["query"])
                problems = await check(case, result, workflow.llm)
            except Exception as exc:  # Type only: provider error text can contain credentials.
                failures += 1
                print(f"ERROR {case['query']}: {type(exc).__name__}")
                continue
            failures += bool(problems)
            print(
                f"{'FAIL' if problems else 'PASS'} {case['query']} [{result.status}] "
                f"{time.monotonic() - started:.1f}s"
            )
            for tool in result.companies:
                stars = f"{tool.github_stars} stars" if tool.github_stars else "no repo"
                print(
                    f"     {tool.name} | {tool.pricing_model.value} | {tool.website} | "
                    f"{stars} | {tool.maintenance or '-'}"
                )
            if result.unresearched:
                print(f"     unresearched: {result.unresearched}")
            for problem in problems:
                print(f"     problem: {problem}")
    return 1 if failures else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--delay", type=float, default=0, help="seconds between queries, for GitHub's API limit"
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.limit, args.delay)))
