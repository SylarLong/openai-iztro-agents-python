"""Live end-to-end test against a deployed backend (opt-in).

Skipped unless ZIWEI_API_KEY is set. Drives the stock Agents SDK Runner with a local
tool against the real hosted Ziwei agent.

    ZIWEI_API_KEY=sk_ziwei_... pytest tests/test_live.py -v -s
    # prod: ZIWEI_BASE_URL=https://chat-api.iztro.com
"""

import asyncio
import os

import pytest
from agents import Runner

from iztro_agents import function_tool, iztro_ziwei_agent

API_KEY = os.environ.get("ZIWEI_API_KEY")
BASE_URL = os.environ.get("ZIWEI_BASE_URL", "https://api-dev.ziwei.guru")

pytestmark = pytest.mark.skipif(not API_KEY, reason="set ZIWEI_API_KEY to run the live test")


def test_live_dev_tool_loop():
    executed: list[tuple[str, str]] = []

    @function_tool
    def add_to_calendar(date: str, title: str) -> str:
        """Add an event to the user's calendar."""
        executed.append((date, title))
        return f"Added '{title}' on {date}"

    async def run():
        agent = iztro_ziwei_agent(
            tools=[add_to_calendar], api_key=API_KEY, base_url=BASE_URL,
            instructions="You are a helpful Ziwei assistant.",
        )
        return await Runner.run(
            agent,
            "Today is 2026-06-26. I was born on 1990-06-15 at 10:00, male. Pick ONE concrete "
            "auspicious date next week based on my chart, then you MUST call the add_to_calendar "
            "tool (do not ask me anything). Confirm in one short sentence.",
        )

    result = asyncio.run(run())
    assert executed, "agent never called the local tool — passthrough loop did not fire"
    assert result.final_output
    print(f"\ntool executed: {executed}\nfinal: {result.final_output[:120]}")


if __name__ == "__main__":
    if not API_KEY:
        raise SystemExit("Set ZIWEI_API_KEY to run this live test.")
    test_live_dev_tool_loop()
    print("PASS")
