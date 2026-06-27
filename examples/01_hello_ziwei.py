"""Example 01 — Hello, Ziwei. Your first program: one rich, professional reading.

You give your birth details, and the agent returns a genuine 紫微斗数 (Purple Star
Astrology) reading — grounded in your actual chart (命宫主星、四化、十二宫), not generic
horoscope filler. This is the difference from a plain chatbot: the chart is computed and
summarized on the server automatically, then read like a professional would.

────────────────────────────────────────────────────────────────────────────
BEFORE YOU RUN
  1. pip install openai-iztro-agents
  2. Get an API key (sk_ziwei_…) from the developer console.
  3. Set it once:   PowerShell:  $env:ZIWEI_API_KEY = "sk_ziwei_..."
                    macOS/Linux: export ZIWEI_API_KEY="sk_ziwei_..."
RUN IT            python examples/01_hello_ziwei.py
WHAT YOU'LL SEE   A structured, specific personality + life reading for the birth details.

NEXT  → examples/02_prompt_gallery.py shows many themes (fortune, career, love, wealth).
────────────────────────────────────────────────────────────────────────────
"""

import asyncio
import os
import sys

# Make Chinese print correctly on Windows terminals.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from agents import Runner

from iztro_agents import iztro_ziwei_agent

# ── Paste your API key between the quotes, or leave it and use ZIWEI_API_KEY. ──
API_KEY = os.environ.get("ZIWEI_API_KEY") or "sk_ziwei_REPLACE_WITH_YOUR_KEY"


async def main() -> None:
    # The `instructions` set the agent's expertise and depth. This is where you make it
    # read like a seasoned 紫微斗数 master rather than a generic assistant: ask it to cite
    # the actual chart and be specific. The chart itself is computed for you on the server.
    agent = iztro_ziwei_agent(
        instructions=(
            "你是一位资深的紫微斗数命理师。请基于用户的真实命盘给出专业、具体、有条理的解读：\n"
            "- 点出命宫主星、身宫、关键的四化（化禄/化权/化科/化忌）与重要宫位；\n"
            "- 结合星曜组合给出有依据的判断，避免空泛的套话；\n"
            "- 分段叙述：性格特质、天赋优势、需要注意的课题、可落地的建议。\n"
            "请用用户使用的语言作答，语气温暖而专业。"
        ),
        api_key=API_KEY,
    )

    # The agent reads the chart automatically — you only supply the birth details.
    result = await Runner.run(
        agent,
        "我出生于 1990 年 6 月 15 日上午 10:00，男性。请给我一份完整的个人性格与人生格局解读。",
    )

    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
