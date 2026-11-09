"""Command-line interface for the research agent."""

import asyncio

from src.config import get_settings
from src.logger import setup_logging
from src.models import ResearchResult
from src.net import create_client
from src.workflow import create_workflow


def print_result(result: ResearchResult) -> None:
    print(f"\nResults for: {result.query} ({result.status})")
    print("=" * 60)
    for index, tool in enumerate(result.companies, 1):
        print(f"\n{index}. {tool.name}")
        print(f"   {tool.description}")
        print(f"   Website: {tool.website or 'unknown'}")
        print(f"   Pricing: {tool.pricing_model.value}")
        open_source = "unknown" if tool.is_open_source is None else tool.is_open_source
        print(f"   Open source: {open_source}")
        if tool.sources:
            print(f"   Sources: {', '.join(tool.sources)}")
    if result.unresearched:
        print(f"\nCould not research: {', '.join(result.unresearched)}")
    if result.analysis:
        print(f"\nRecommendation:\n{result.analysis}")


async def main() -> None:
    settings = get_settings()
    setup_logging()
    async with create_client(settings) as client:
        workflow = create_workflow(settings, client)
        print("Developer Tools Research Agent (type 'quit' to exit)")
        while True:
            query = (await asyncio.to_thread(input, "\nQuery: ")).strip()
            if query.lower() in {"quit", "exit"}:
                return
            if len(query) >= 2:
                print_result(await workflow.run(query))


if __name__ == "__main__":
    asyncio.run(main())
