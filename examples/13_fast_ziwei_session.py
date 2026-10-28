"""Example 13 — Fast Ziwei managed session.

This mirrors a common customer integration: configure the person's profile once in the
agent instructions, choose the faster, lower-token Ziwei model, and reuse one ChatSession
for follow-up turns instead of repeating birth details.

This is an example, not a complete production backend. Keep the API key server-side,
derive ``external_user_id`` from your authenticated user, and persist ``session_id`` in
your own database when the conversation must survive a process restart.

RUN IT   python examples/13_fast_ziwei_session.py
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
    return f"{message}\nSent at: {sent_at}"


async def main() -> None:
    api_key = require_api_key()
    agent = iztro_ziwei_fast_agent(
        api_key=api_key,
        instructions=(
            "Reply in English using plain language. Include key points, reasons, and a conclusion. "
            "Keep replies around 100 words and offer advice only when asked. "
            "Birth profile: Gregorian birthday=1993-11-07, local birth time=10:00 AM, gender=female. "
        ),
        model_settings=ModelSettings(reasoning=Reasoning(effort="none")),
    )
    session = ChatSession(external_user_id="authenticated_user_123", api_key=api_key)

    try:
        questions = (
            "How might my career change in 2028?",
            "Compare my career outlook in 2029 with 2028.",
            "What patterns should I watch for in romantic relationships?",
        )
        for question in questions:
            result = await Runner.run(agent, message_with_local_time(question), session=session)
            print(result.final_output)

        print("session_id:", session.session_id)
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())
