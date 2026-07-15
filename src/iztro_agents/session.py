"""ChatSession — server-side conversation memory for the OpenAI Agents SDK.

A ``Session`` implementation backed by the hosted Iztro conversation store, modeled
on the SDK's own ``OpenAIConversationsSession``: the **server generates the
conversation id** (lazily, on first use), and ``external_user_id`` records which of
*your* users owns it (so you can list/manage a user's chats). Pair it with the stock
``OpenAIChatCompletionsModel`` pointed at ``/v2/chat/completions``:

    from agents import Agent, Runner, OpenAIChatCompletionsModel
    from openai import AsyncOpenAI
    from iztro_agents import ChatSession

    model = OpenAIChatCompletionsModel(
        model="iztro-ziwei-v3",
        openai_client=AsyncOpenAI(base_url="https://chat-api.iztro.com/v2", api_key=KEY),
    )
    agent = Agent(name="Ziwei", model=model, tools=[...])

    # New conversation owned by your user (server assigns the id):
    session = ChatSession(external_user_id="user_42")          # ZIWEI_API_KEY from env
    await Runner.run(agent, "What city is the Golden Gate Bridge in?", session=session)
    await Runner.run(agent, "What state is it in?", session=session)   # remembers
    saved_id = session.session_id   # persist to resume later

    # Resume an existing conversation:
    session = ChatSession(conversation_id=saved_id)

List a user's conversations for management:  await list_user_conversations("user_42")
"""

from __future__ import annotations

import os
from typing import Any

import httpx

try:
    from agents.memory.session import SessionABC
except ImportError:  # pragma: no cover - layout fallback
    from agents.memory import SessionABC  # type: ignore

DEFAULT_BASE_URL = "https://chat-api.iztro.com"


def _resolve(api_key: str | None, base_url: str | None) -> tuple[str, str]:
    api_key = api_key or os.environ.get("ZIWEI_API_KEY")
    if not api_key:
        raise ValueError("api_key is required (pass api_key=... or set ZIWEI_API_KEY)")
    base = (base_url or os.environ.get("ZIWEI_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    return api_key, base


class ChatSession(SessionABC):
    """Server-side conversation history with a server-generated id.

    The conversation is created lazily on the first session operation. Accessing
    ``session_id`` before then raises (mirrors ``OpenAIConversationsSession``).
    """

    session_settings = None

    def __init__(
        self,
        *,
        conversation_id: str | None = None,
        external_user_id: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
    ):
        self._api_key, self._base = _resolve(api_key, base_url)
        self._timeout = timeout
        self._conversation_id = conversation_id
        self.external_user_id = external_user_id
        self._http = httpx.AsyncClient(
            timeout=timeout,
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
        )

    @property
    def session_id(self) -> str:
        if self._conversation_id is None:
            raise ValueError(
                "Conversation id not yet available. It is created lazily on the first "
                "session operation — call get_items()/add_items() (or run the agent) first."
            )
        return self._conversation_id

    @session_id.setter
    def session_id(self, value: str) -> None:
        self._conversation_id = value

    async def _ensure_conversation_id(self) -> str:
        if self._conversation_id is None:
            body = {"external_user_id": self.external_user_id} if self.external_user_id else {}
            resp = await self._http.post(f"{self._base}/v2/platform/conversations", json=body)
            resp.raise_for_status()
            self._conversation_id = resp.json()["conversation_id"]
        return self._conversation_id

    def _items_url(self, suffix: str = "") -> str:
        return f"{self._base}/v2/platform/conversations/{self._conversation_id}/items{suffix}"

    async def get_items(self, limit: int | None = None) -> list[dict[str, Any]]:
        await self._ensure_conversation_id()
        params = {"limit": limit} if limit else None
        resp = await self._http.get(self._items_url(), params=params)
        resp.raise_for_status()
        return resp.json().get("items", [])

    async def add_items(self, items: list[dict[str, Any]]) -> None:
        if not items:
            return
        await self._ensure_conversation_id()
        resp = await self._http.post(self._items_url(), json={"items": list(items)})
        resp.raise_for_status()

    async def pop_item(self) -> dict[str, Any] | None:
        await self._ensure_conversation_id()
        resp = await self._http.delete(self._items_url("/last"))
        resp.raise_for_status()
        return resp.json().get("item")

    async def clear_session(self) -> None:
        await self._ensure_conversation_id()
        resp = await self._http.delete(f"{self._base}/v2/platform/conversations/{self._conversation_id}")
        resp.raise_for_status()
        self._conversation_id = None

    async def fork(
        self,
        *,
        item_count: int | None = None,
        external_user_id: str | None = None,
    ) -> "ChatSession":
        """Copy this conversation into a new server-side conversation.

        ``item_count`` keeps the first N items. Leave it as ``None`` to copy the
        entire conversation. Keeping the prefix before a user message and then
        running the agent with replacement text is a safe way to implement message
        editing without mutating the original branch.

        The returned session owns its HTTP client; callers should close it when they
        are done. Pass ``external_user_id`` when resuming a session that was created
        without one so the fork appears in that user's conversation list.
        """
        if item_count is not None and item_count < 0:
            raise ValueError("item_count must be zero or greater")

        items = await self.get_items()
        copied_items = items if item_count is None else items[:item_count]
        forked = ChatSession(
            external_user_id=(
                external_user_id if external_user_id is not None else self.external_user_id
            ),
            api_key=self._api_key,
            base_url=self._base,
            timeout=self._timeout,
        )
        try:
            # get_items() also creates an intentionally empty fork when item_count is 0.
            await forked.get_items()
            await forked.add_items(list(copied_items))
        except Exception:
            await forked.close()
            raise
        return forked

    async def close(self) -> None:
        await self._http.aclose()

    @classmethod
    async def list_user_conversations(
        cls,
        external_user_id: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List all conversations owned by one application user."""
        return await list_user_conversations(
            external_user_id,
            api_key=api_key,
            base_url=base_url,
            limit=limit,
        )


async def list_user_conversations(
    external_user_id: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List the conversations owned by one of your users (most recent first)."""
    api_key, base = _resolve(api_key, base_url)
    async with httpx.AsyncClient(headers={"Authorization": f"Bearer {api_key}"}) as http:
        resp = await http.get(
            f"{base}/v2/platform/users/{external_user_id}/conversations",
            params={"limit": limit},
        )
        resp.raise_for_status()
        return resp.json().get("items", [])
