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

from src.config import get_settings
from src.net import create_client
from src.workflow import create_workflow


def check(case: dict, result) -> list[str]:
    names = [company.name.casefold() for company in result.companies]
    problems = []
    if not any(expected.casefold() in name for expected in case["expect_any"] for name in names):
        problems.append(f"none of {case['expect_any']} found")
    if result.pricing_preference != case["pricing"]:
        problems.append(f"pricing read as {result.pricing_preference}, not {case['pricing']}")
    missing_sources = [c.name for c in result.companies if not c.sources]
    if missing_sources:
        problems.append(f"no sources for {missing_sources}")
    return problems


async def main(limit: int | None) -> int:
    cases = json.loads(Path(__file__).with_name("queries.json").read_text(encoding="utf-8"))
    settings = get_settings()
    failures = 0
    async with create_client(settings) as client:
        workflow = create_workflow(settings, client)
        for case in cases[:limit]:
            started = time.monotonic()
            try:
                result = await workflow.run(case["query"])
            except Exception as exc:  # Type only: provider error text can contain credentials.
                failures += 1
                print(f"ERROR {case['query']}: {type(exc).__name__}")
                continue
            problems = check(case, result)
            failures += bool(problems)
            print(f"{'FAIL' if problems else 'PASS'} {case['query']} [{result.status}] "
                  f"{time.monotonic() - started:.1f}s")
            for company in result.companies:
                print(f"     {company.name} | {company.pricing_model.value} | {company.website}")
            if result.unresearched:
                print(f"     unresearched: {result.unresearched}")
            for problem in problems:
                print(f"     problem: {problem}")
    return 1 if failures else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    sys.exit(asyncio.run(main(parser.parse_args().limit)))
