"""Example 04 — Conversation memory & RESUME: pick a chat up later (ChatSession).

The agent remembers a conversation because the history lives on the SERVER under a
conversation id. The one thing YOU keep is that id: `session.session_id`.

  • First visit  → start a ChatSession (the server assigns an id), chat, then SAVE the id.
  • Come back later → rebuild `ChatSession(conversation_id=saved_id)` and keep going —
                      even in a brand-new process, or after your server restarts.

This is exactly what a chat backend does: store the id per user, reload it next request.
The two phases below share NOTHING except `saved_id` — no Python objects are reused.

RUN IT   python examples/04_memory_and_resume.py
"""

import asyncio
import os

from agents import Runner

from iztro_agents import ChatSession, iztro_ziwei_agent

API_KEY = os.environ.get("ZIWEI_API_KEY") or "sk_ziwei_REPLACE_WITH_YOUR_KEY"


def build_agent():
    return iztro_ziwei_agent(instructions="You are a helpful assistant. Answer briefly.", api_key=API_KEY)


async def first_visit() -> str:
    """Start a new conversation and return the id you must save to resume it later."""
    agent = build_agent()
    # external_user_id records which of YOUR users owns this chat; the server makes the id.
    session = ChatSession(external_user_id="user_42", api_key=API_KEY)

    print("── First visit ──")
    print("T1:", (await Runner.run(agent, "My name is Alice, born 1990-06-15.", session=session)).final_output)
    print("T2:", (await Runner.run(agent, "What's my name and birth date?", session=session)).final_output)

    saved_id = session.session_id          # ← persist this (e.g. db.save(user_id, saved_id))
    print("saved conversation id:", saved_id)
    await session.close()
    return saved_id


async def come_back_later(saved_id: str) -> None:
    """A later request / new process: rebuild the session from ONLY the saved id."""
    agent = build_agent()
    session = ChatSession(conversation_id=saved_id, api_key=API_KEY)   # resume

    print("\n── Come back later (resumed from the id) ──")
    print("T3:", (await Runner.run(agent, "What did I first tell you?", session=session)).final_output)
    await session.close()


async def main() -> None:
    saved_id = await first_visit()
    # ... time passes, the process could exit here; all you need is saved_id ...
    await come_back_later(saved_id)


if __name__ == "__main__":
    asyncio.run(main())
