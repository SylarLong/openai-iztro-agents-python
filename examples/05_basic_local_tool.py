"""Example 05 — Your first tool: a local function the hosted Ziwei agent can call.

Run:  python examples/05_basic_local_tool.py
"""

import asyncio
import os

from agents import Runner

from iztro_agents import ChatSession, function_tool, iztro_ziwei_agent

# ── Paste your API key here (from the developer console), or set ZIWEI_API_KEY. ──
API_KEY = os.environ.get("ZIWEI_API_KEY") or "sk_ziwei_REPLACE_WITH_YOUR_KEY"


@function_tool
def add_to_calendar(date: str, title: str) -> str:
    """Add an event to the user's calendar. Runs locally in this process.

    Args:
        date: ISO date, e.g. "2026-07-03".
        title: Short event title.
    """
    return f"Added '{title}' on {date}."


async def main() -> None:
    agent = iztro_ziwei_agent(
        tools=[add_to_calendar],
        instructions="You are a helpful Ziwei assistant.",
        api_key=API_KEY,
    )
    session = ChatSession(external_user_id="user_42", api_key=API_KEY)
    result = await Runner.run(
        agent,
        "Today is 2026-06-26. I was born on 1990-06-15 at 10:00, male. Pick one "
        "auspicious day next week based on my chart and add it to my calendar.",
        session=session,
    )
    print(result.final_output)
    await session.close()


if __name__ == "__main__":
    asyncio.run(main())
