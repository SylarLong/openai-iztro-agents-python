"""Example 12 — Qimen: one concrete decision plus optional timing.

Qimen is different from a natal Ziwei reading. It casts one chart from the question time
for one current matter, so no birth date, birth hour, or gender is required.

────────────────────────────────────────────────────────────────────────────
RUN IT            python examples/12_qimen_decision.py
WHAT YOU'LL SEE   A chart-grounded decision, timing windows, and hosted tool events.
────────────────────────────────────────────────────────────────────────────
"""

import asyncio
import os
import sys

from agents import ModelSettings, Runner

from iztro_agents import iztro_qimen_agent

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

API_KEY = os.environ.get("ZIWEI_API_KEY") or "sk_ziwei_REPLACE_WITH_YOUR_KEY"


async def main() -> None:
    agent = iztro_qimen_agent(
        api_key=API_KEY,
        instructions=(
            "请先给明确结论，再列出关键宫位证据、风险、应期和可执行建议。"
            "不要把应期触发日表述为必然成功。"
        ),
        # Optional. Pin the user's local question time when you need a reproducible chart.
        # Otherwise the hosted service uses the request time.
        model_settings=ModelSettings(
            metadata={"current_datetime": "2026-07-20T14:30:00+08:00"}
        ),
    )

    result = await Runner.run(
        agent,
        (
            "我们正在谈一项渠道合作，已经沟通两次，但分成和上线时间还没定。"
            "现在适合主动推进、继续谈判，还是暂缓？如果适合推进，请给出近期时间窗口和行动建议。"
        ),
    )

    for response in result.raw_responses:
        if response.tool_event:
            print("🔮 hosted Qimen tools:", " -> ".join(response.tool_event.tools))
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
