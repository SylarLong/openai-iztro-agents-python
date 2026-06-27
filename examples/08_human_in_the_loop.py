"""Example 08 — Human-in-the-loop: approve a sensitive action before it runs.

A tool marked ``needs_approval=True`` pauses the run; ``Runner.run`` returns a result
with ``interruptions``. You approve/reject, then resume by running the saved state.

Run:  python examples/08_human_in_the_loop.py
"""

import asyncio
import os

from agents import Runner

from iztro_agents import function_tool, iztro_ziwei_agent

# ── Paste your API key here (from the developer console), or set ZIWEI_API_KEY. ──
API_KEY = os.environ.get("ZIWEI_API_KEY") or "sk_ziwei_REPLACE_WITH_YOUR_KEY"


@function_tool(needs_approval=True)  # the SDK pauses before running this
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email on the user's behalf."""
    print(f"\n📧 [LOCAL] Sending email to {to}\n   subject: {subject}\n")
    return f"Email delivered to {to}."


async def main() -> None:
    agent = iztro_ziwei_agent(tools=[send_email], api_key=API_KEY)
    result = await Runner.run(
        agent,
        "I was born 1988-02-20 at 6am, female. Draft and send an encouraging email to "
        "me@example.com based on this year's outlook.",
    )

    # Native SDK HITL loop: approve/reject each pending tool, then resume.
    while result.interruptions:
        state = result.to_state()
        for item in result.interruptions:
            raw = item.raw_item
            name = getattr(raw, "name", None) or getattr(item, "tool_name", "tool")
            args = getattr(raw, "arguments", "")
            decision = input(f"\nApprove {name}({args})? [y/N] ").strip().lower()
            if decision in ("y", "yes"):
                state.approve(item)
            else:
                state.reject(item)
        result = await Runner.run(agent, state)

    print("\n=== Final reply ===")
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
