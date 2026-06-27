"""Example 06 — Your own tools: let the agent run YOUR code.

A "tool" is just one of your Python functions that the agent is allowed to call. You add
the @function_tool decorator, list it when you build the agent, and the agent decides
when to call it. Here the agent calls TWO of your functions in the same turn.

The functions run locally, on your machine, in this process — so they can do anything
your code can do (look something up, save a file, hit your own database, …).

The agent reads the birth chart AUTOMATICALLY (that happens on the server — you never
write a tool for it). It then figures out the chart's dominant element on its own and
calls YOUR lookup functions with that element. Your tools are just your own data.

────────────────────────────────────────────────────────────────────────────
RUN IT      python examples/06_two_tools_at_once.py
WHAT YOU'LL SEE   Two "[your function ran]" lines, then a sentence combining their results.
────────────────────────────────────────────────────────────────────────────
"""

import asyncio
import os

from agents import Runner

from iztro_agents import function_tool, iztro_ziwei_agent

API_KEY = os.environ.get("ZIWEI_API_KEY") or "sk_ziwei_REPLACE_WITH_YOUR_KEY"


# ── Tool #1 ──────────────────────────────────────────────────────────────────
@function_tool
def get_lucky_color(element: str) -> str:
    """Return a lucky color for a five-element type (wood, fire, earth, metal, water).

    The docstring matters: the agent reads it to understand WHEN and HOW to call this.

    Args:
        element: One of wood / fire / earth / metal / water.
    """
    print(f"  [your function ran] get_lucky_color(element={element!r})")
    table = {"wood": "green", "fire": "red", "earth": "yellow", "metal": "white", "water": "black"}
    return table.get(element.lower(), "gold")


# ── Tool #2 ──────────────────────────────────────────────────────────────────
@function_tool
def get_lucky_number(element: str) -> int:
    """Return a lucky number for a five-element type.

    Args:
        element: One of wood / fire / earth / metal / water.
    """
    print(f"  [your function ran] get_lucky_number(element={element!r})")
    return {"wood": 3, "fire": 9, "earth": 5, "metal": 7, "water": 1}.get(element.lower(), 8)


async def main() -> None:
    # List BOTH tools when building the agent. The agent picks which to call (here, both).
    agent = iztro_ziwei_agent(
        tools=[get_lucky_color, get_lucky_number],
        instructions="You are a Ziwei guide. Use the tools to give concrete lucky details.",
        api_key=API_KEY,
    )

    result = await Runner.run(
        agent,
        "Born 1995-09-09 at noon, female. Based on my chart's dominant element, "
        "tell me my lucky color and lucky number in one sentence.",
    )

    print("\n=== Final reply ===")
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
