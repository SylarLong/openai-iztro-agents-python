"""Example 11 — Use the Ziwei agent as a TOOL inside your own agent.

Package the Ziwei agent as a single tool and give it to a bigger "orchestrator" agent
that runs on YOUR model (e.g. GPT). The orchestrator decides when to consult the
astrologer, then does other things (book a calendar event) with the result.

    your orchestrator agent (your model + your key)
      ├─ tool: ziwei_reading   ← the Ziwei agent, wrapped with .as_tool(...)
      └─ tool: add_to_calendar ← your own local function

RUN IT   python examples/11_agent_as_tool.py
"""

import asyncio
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from openai import AsyncOpenAI

from agents import Agent, OpenAIChatCompletionsModel, Runner

from iztro_agents import function_tool, iztro_ziwei_agent

# ── Fill in your keys and model (or set them as environment variables). ──────
ZIWEI_API_KEY = os.environ.get("ZIWEI_API_KEY") or "sk_ziwei_REPLACE_WITH_YOUR_KEY"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or "sk-REPLACE_WITH_YOUR_OPENAI_KEY"
ORCHESTRATOR_MODEL = "gpt-4o-mini"   # any model your OpenAI key can use

my_calendar: list[dict] = []


@function_tool
def add_to_calendar(date: str, title: str) -> str:
    """Add ONE event to the user's calendar.

    Args:
        date: ISO date like "2026-07-03".
        title: A short event title.
    """
    print(f"  [calendar] add_to_calendar(date={date!r}, title={title!r})")
    my_calendar.append({"date": date, "title": title})
    return f"Added '{title}' on {date}."


async def main() -> None:
    # The Ziwei agent, wrapped as a tool the orchestrator can call. Keep a reference to the
    # agent: its responses run INSIDE the sub-agent, so they aren't in the orchestrator's
    # result.raw_responses — read the iztro tools from the agent's model afterwards instead.
    ziwei_agent = iztro_ziwei_agent(
        instructions="你是一位资深紫微斗数命理师，请基于真实命盘给出专业、具体的解读。",
        api_key=ZIWEI_API_KEY,
    )
    ziwei_reading = ziwei_agent.as_tool(
        tool_name="ziwei_reading",
        tool_description="Get a professional Ziwei reading. Pass birth date, time, gender, and the question.",
    )

    # Your orchestrator, running on your model. A stock Agent has no `api_key=` argument —
    # you pass the key by giving it a model object that carries its own OpenAI client.
    orchestrator = Agent(
        name="Concierge",
        model=OpenAIChatCompletionsModel(
            model=ORCHESTRATOR_MODEL,
            openai_client=AsyncOpenAI(api_key=OPENAI_API_KEY),
        ),
        instructions=(
            "You are a personal concierge. For destiny, personality, or auspicious timing, "
            "call ziwei_reading. To schedule, call add_to_calendar. Don't ask follow-ups."
        ),
        tools=[ziwei_reading, add_to_calendar],
    )

    result = await Runner.run(
        orchestrator,
        "Today is 2026-06-26. I was born 1990-06-15 at 10:00, male. "
        "Ask the astrologer for one auspicious day next week, then put it on my calendar.",
    )
    # The sub-agent's tools aren't in the orchestrator's result; read the latest tool event.
    tool_event = ziwei_agent.model.last_tool_event
    print("\n🔮 iztro computed:", ", ".join(tool_event.tools if tool_event else []))
    print("\n=== Final reply ===")
    print(result.final_output)
    print("\nYour calendar now holds:", my_calendar)


if __name__ == "__main__":
    asyncio.run(main())
