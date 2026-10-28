"""Birth information provided in chat.

WHEN TO USE
You do not have the person's birth information saved. Let the customer type
it in the conversation, just as they would tell a human consultant.

WHAT TO CHANGE
The first chat message below shows what the customer would type. The second
message asks a follow-up without repeating their birth information.
If details are missing, the assistant is instructed to ask instead of guessing.
ChatSession keeps the messages together so follow-ups use the same profile.

BEFORE RUNNING
Set ZIWEI_API_KEY to your API key. Keep it on your server.
Run: python examples/16_birth_profile_conversation.py
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
            "Before calculating, ask for the Gregorian birth date, local birth "
            "time (including AM/PM), and gender if they are missing or ambiguous."
        ),
        model_settings=ModelSettings(reasoning=Reasoning(effort="none")),
    )
    # Use the signed-in customer's own ID. Never share one session between customers.
    session = ChatSession(external_user_id="authenticated_user_123", api_key=api_key)
    try:
        result = await Runner.run(
            agent, "I am female, born on November 7, 1993 (Gregorian calendar), at 10:00 AM local time. How might my career change in 2028?", session=session,
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
