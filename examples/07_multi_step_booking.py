"""Example 07 — A multi-step task with YOUR tools, used in sequence.

IMPORTANT — what the agent does for free:
  The Ziwei agent reads and summarizes the birth chart AUTOMATICALLY on the server.
  You do NOT write a tool for that. Your tools are only for things in YOUR world —
  here, your own calendar.

This example shows two of your tools used in order, where the second depends on the
first:
  Step 1 — `check_availability`: is that day free in my calendar?
  Step 2 — `add_to_calendar`: if it's free, book it.

The agent picks WHICH day is auspicious (from the chart it read automatically), then uses
your tools to check and book it. You don't script the order — the agent figures it out.

────────────────────────────────────────────────────────────────────────────
RUN IT      python examples/07_multi_step_booking.py
WHAT YOU'LL SEE   A "[checking]" line, then a "[booking]" line, then a confirmation.
────────────────────────────────────────────────────────────────────────────
"""

import asyncio
import os

from agents import Runner

from iztro_agents import function_tool, iztro_ziwei_agent

API_KEY = os.environ.get("ZIWEI_API_KEY") or "sk_ziwei_REPLACE_WITH_YOUR_KEY"

# A pretend calendar. In a real app this is Google Calendar, Outlook, your database, etc.
# Pretend July 2nd is already taken, so the agent has to work around it.
my_calendar: list[dict] = [{"date": "2026-07-02", "title": "Dentist"}]


@function_tool
def check_availability(date: str) -> str:
    """Check whether the user's calendar is FREE on a given day.

    Args:
        date: ISO date like "2026-07-03".
    """
    taken = any(event["date"] == date for event in my_calendar)
    print(f"  [checking] {date} -> {'BUSY' if taken else 'free'}")
    return "busy" if taken else "free"


@function_tool
def add_to_calendar(date: str, title: str) -> str:
    """Add ONE event to the user's calendar. Only call this for a free day.

    Args:
        date: ISO date like "2026-07-03".
        title: A short event title.
    """
    print(f"  [booking] add_to_calendar(date={date!r}, title={title!r})")
    my_calendar.append({"date": date, "title": title})
    return f"Added '{title}' on {date}."


async def main() -> None:
    agent = iztro_ziwei_agent(
        tools=[check_availability, add_to_calendar],
        instructions=(
            "You are a Ziwei guide. The user's chart is available to you automatically. "
            "Pick ONE auspicious weekday next week, FIRST check it with check_availability, "
            "and only if it is free, book it with add_to_calendar. If it is busy, try the "
            "next auspicious day. Do not ask the user any questions."
        ),
        api_key=API_KEY,
    )

    result = await Runner.run(
        agent,
        "Today is 2026-06-26. I was born on 1990-06-15 at 10:00, male. "
        "Find a good day next week for an important meeting and put it on my calendar.",
    )

    # Multi-step run: gather the server-side iztro tools from every model call.
    used = [t for r in result.raw_responses for t in r.iztro_tools]
    print("\n🔮 iztro computed:", ", ".join(dict.fromkeys(used)))
    print("\n=== Final reply ===")
    print(result.final_output)
    print("\nYour calendar now holds:", my_calendar)


if __name__ == "__main__":
    asyncio.run(main())
