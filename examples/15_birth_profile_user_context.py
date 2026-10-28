"""Birth information from UserContext.

WHEN TO USE
Your app already saves each customer's birth information in their account.
Use this when different signed-in customers use the same chat assistant.
Your developer loads the signed-in customer's profile into UserContext.

WHAT TO CHANGE
The sample user_context / userContext below contains one customer's data.
Replace those values with that customer's saved account information.
UserContext is a type defined in this example, not an SDK import.

IMPORTANT
Context stays inside your app. Passing context alone does not tell the model
the birthday. The instructions function below reads the birth fields and
explicitly supplies them to the model. Never include passwords or API keys.

BEFORE RUNNING
Set ZIWEI_API_KEY to your API key. Keep it on your server.
Run: python examples/15_birth_profile_user_context.py
"""

import asyncio
import os
from dataclasses import dataclass
from agents import Agent, ModelSettings, RunContextWrapper, Runner
from openai.types.shared import Reasoning
from iztro_agents import ChatSession, iztro_ziwei_model


@dataclass
class UserContext:
    birthday: str
    birth_time: str
    gender: str


def instructions(wrapper: RunContextWrapper[UserContext], agent: Agent[UserContext]) -> str:
    # This is the bridge that makes the saved birth information visible to the model.
    profile = wrapper.context
    return (
        "Reply in English using plain language. "
        f"Birth profile: Gregorian birthday={profile.birthday}; "
        f"local birth time={profile.birth_time}; gender={profile.gender}."
    )


async def main() -> None:
    # Read the API key from the environment; do not paste it into a chat message.
    api_key = os.environ["ZIWEI_API_KEY"]
    # Sample account data: your developer loads this from the signed-in user's account.
    user_context: UserContext = UserContext(
        birthday="1993-11-07", birth_time="10:00 AM", gender="female",
    )
    agent = Agent[UserContext](
        name="Ziwei", instructions=instructions,
        model=iztro_ziwei_model(api_key=api_key),
        model_settings=ModelSettings(reasoning=Reasoning(effort="none")),
    )
    # Use the signed-in customer's own ID. Never share one session between customers.
    session = ChatSession(external_user_id="authenticated_user_123", api_key=api_key)
    try:
        result = await Runner.run(
            agent, "How might my career change in 2028?", session=session, context=user_context,
        )
        print(result.final_output)

        # Same session: the customer does not need to repeat their birth information.
        result = await Runner.run(
            agent, "Compare that with 2029.", session=session, context=user_context,
        )
        print(result.final_output)
        # Save this ID in your app if the customer will resume this chat later.
        print("session_id:", session.session_id)
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())
