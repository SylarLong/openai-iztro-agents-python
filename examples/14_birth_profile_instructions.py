"""Birth information in instructions.

WHEN TO USE
You already know the person's birthday, birth time and gender, and this chat
will always discuss that person. This is the simplest option to start with.

WHAT TO CHANGE
Edit the birth profile inside instructions below. Use a Gregorian date and
local clock time with AM/PM. Do not enter a time-branch number.

BEFORE RUNNING
Set ZIWEI_API_KEY to your API key. Keep it on your server.
Run: python examples/14_birth_profile_instructions.py
"""

import asyncio
import os
from agents import ModelSettings, Runner
from openai.types.shared import Reasoning
from iztro_agents import ChatSession, iztro_ziwei_agent


async def main() -> None:
    # Read the API key from the environment; do not paste it into a chat message.
    api_key = os.environ["ZIWEI_API_KEY"]
    agent = iztro_ziwei_agent(
        api_key=api_key,
        instructions=(
            "Reply in English using plain language. "
            # Change THESE three values to the person's birth information.
            "Birth profile: Gregorian birthday=1993-11-07; "
            "local birth time=10:00 AM; gender=female."
        ),
        model_settings=ModelSettings(reasoning=Reasoning(effort="none")),
    )
    # Use the signed-in customer's own ID. Never share one session between customers.
    session = ChatSession(external_user_id="authenticated_user_123", api_key=api_key)
    try:
        result = await Runner.run(
            agent, "How might my career change in 2028?", session=session,
        )
        print(result.final_output)

        # Same session: the customer does not need to repeat their birth information.
        result = await Runner.run(
            agent, "Compare that with 2029.", session=session,
        )
        print(result.final_output)
        # Save this ID in your app if the customer will resume this chat later.
        print("session_id:", session.session_id)
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())
