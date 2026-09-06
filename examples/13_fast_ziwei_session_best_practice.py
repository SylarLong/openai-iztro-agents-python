"""Example 13 — Fast Ziwei managed session (illustrative best-practice shape).

This mirrors a common customer integration: configure the person's profile once in the
agent instructions, choose the faster, lower-token Ziwei model, and reuse one ChatSession
for follow-up turns instead of repeating birth details.

This is an example, not a complete production backend. Keep the API key server-side,
derive ``external_user_id`` from your authenticated user, and persist ``session_id`` in
your own database when the conversation must survive a process restart.

RUN IT   python examples/13_fast_ziwei_session_best_practice.py
"""

import asyncio
import os
from datetime import datetime

from agents import ModelSettings, Runner
from openai.types.shared import Reasoning

from iztro_agents import ChatSession, iztro_ziwei_fast_agent


def require_api_key() -> str:
    api_key = os.environ.get("ZIWEI_API_KEY")
    if not api_key:
        raise RuntimeError("Set ZIWEI_API_KEY before running this example.")
    return api_key


def message_with_local_time(message: str) -> str:
    sent_at = datetime.now().astimezone().isoformat(timespec="seconds")
    return f"{message}\n发送时间：{sent_at}"


async def main() -> None:
    api_key = require_api_key()
    agent = iztro_ziwei_fast_agent(
        api_key=api_key,
        instructions=(
            "回答尽可能精短有力、通俗易懂；列出关键词、原因和结论即可。"
            "用户未明确要求时不主动提供建议，回答控制在 100 字左右。"
            "分析对象：birthday=1993-11-07，birth_hour=10，gender=女。"
        ),
        model_settings=ModelSettings(reasoning=Reasoning(effort="none")),
    )
    session = ChatSession(external_user_id="authenticated_user_123", api_key=api_key)

    try:
        questions = (
            "分析我 2028 年的事业变化。",
            "继续比较 2029 年与 2028 年的事业变化。",
            "分析我在感情关系中需要注意的模式。",
        )
        for question in questions:
            result = await Runner.run(agent, message_with_local_time(question), session=session)
            print(result.final_output)

        print("session_id:", session.session_id)
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())
