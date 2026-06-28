"""Example 09 — Control output length & cost with a token limit (production knob).

By default, let the agent answer fully — that depth is the whole point (see examples 01
and 02). But in production you sometimes need a HARD ceiling on how much the model can
produce, to bound cost and latency. That ceiling is `max_tokens`, set via `ModelSettings`.

Important framing:
  • This is a COST / SIZE control, not a quality setting. A low cap can cut a reading off
    mid-sentence — that's expected.
  • To make answers genuinely shorter *and* clean, guide it in the instructions instead
    (e.g. "give a 3-bullet summary"). Use `max_tokens` as a safety ceiling on top of that.

────────────────────────────────────────────────────────────────────────────
RUN IT            python examples/09_limit_length_and_cost.py
WHAT YOU'LL SEE   The same request, first uncapped (full depth), then with max_tokens set.
────────────────────────────────────────────────────────────────────────────
"""

import asyncio
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ModelSettings carries model knobs: max_tokens, temperature, tool_choice, etc.
from agents import ModelSettings, Runner

from iztro_agents import iztro_ziwei_agent

API_KEY = os.environ.get("ZIWEI_API_KEY") or "sk_ziwei_REPLACE_WITH_YOUR_KEY"

INSTRUCTIONS = "你是一位资深紫微斗数命理师，请基于真实命盘给出专业、具体的解读。"
PROMPT = "我出生于 1990 年 6 月 15 日上午 10:00，男性。请给我一份详细的命盘解读。"


async def full_depth() -> None:
    """No cap — the agent answers as fully as the chart warrants (the default, recommended)."""
    agent = iztro_ziwei_agent(instructions=INSTRUCTIONS, api_key=API_KEY)
    result = await Runner.run(agent, PROMPT)
    print("─" * 60, "\n① FULL DEPTH (no token cap — this is the default)\n")
    print("🔮 iztro computed:", ", ".join(result.raw_responses[-1].iztro_tools))
    print(result.final_output)


async def capped(max_tokens: int) -> None:
    """Hard ceiling for cost control. Change `max_tokens` to trade depth for budget."""
    agent = iztro_ziwei_agent(
        instructions=INSTRUCTIONS,
        api_key=API_KEY,
        model_settings=ModelSettings(max_tokens=max_tokens),
    )
    result = await Runner.run(agent, PROMPT)
    print("\n" + "─" * 60, f"\n② CAPPED (max_tokens={max_tokens} — a cost/size ceiling)\n")
    print("🔮 iztro computed:", ", ".join(result.raw_responses[-1].iztro_tools))
    print(result.final_output)


async def main() -> None:
    await full_depth()
    # Try 120, 300, 800 and watch cost/length scale. Low values may truncate — that's the point.
    await capped(max_tokens=300)


if __name__ == "__main__":
    asyncio.run(main())
