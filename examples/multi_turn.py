"""Multi-turn memory + resume + listing a user's conversations (ChatSession).

History lives on the server, keyed by a server-generated conversation id and owned by
your ``external_user_id``.

Run:  python examples/multi_turn.py
"""

import asyncio
import os

from agents import Runner

from iztro_agents import ChatSession, iztro_ziwei_agent, list_user_conversations

# ── Paste your API key here (from the developer console), or set ZIWEI_API_KEY. ──
API_KEY = os.environ.get("ZIWEI_API_KEY") or "sk_ziwei_REPLACE_WITH_YOUR_KEY"


async def main() -> None:
    agent = iztro_ziwei_agent(instructions="You are a helpful assistant. Answer briefly.", api_key=API_KEY)

    # New conversation owned by your user — the server assigns the id.
    session = ChatSession(external_user_id="user_42", api_key=API_KEY)
    print("T1:", (await Runner.run(agent, "My name is Alice, born 1990-06-15.", session=session)).final_output)
    print("T2:", (await Runner.run(agent, "What's my name and birth date?", session=session)).final_output)

    conv_id = session.session_id  # server-generated; save this to resume later
    print("conversation id:", conv_id)

    # Manage a user's chats.
    convs = await list_user_conversations("user_42", api_key=API_KEY)
    print("user_42 conversations:", [c["conversation_id"] for c in convs])

    # Resume that conversation in a fresh session.
    resumed = ChatSession(conversation_id=conv_id, api_key=API_KEY)
    print("Resumed:", (await Runner.run(agent, "What did I first tell you?", session=resumed)).final_output)

    await session.close()
    await resumed.close()


if __name__ == "__main__":
    asyncio.run(main())
