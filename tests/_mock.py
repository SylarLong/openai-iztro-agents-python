"""Offline mock backends for the hosted Ziwei model and the conversation store.

These helpers let the whole test-suite run **deterministically, offline, and with no
API key** by swapping `httpx`'s transport for an in-process handler. Two backends:

* `mock_chat(...)` / `agent_with(...)` — fake the ``/v2/chat/completions`` endpoint the
  hosted Ziwei model talks to. Build assistant turns with `assistant_text(...)`,
  `assistant_tool_calls(...)`, and `sse_stream(...)`.
* `InMemoryConversations` + `attach_session(...)` — a tiny in-memory implementation of
  the ``/v2/platform/conversations`` endpoints that `ChatSession` uses for memory.

Everything here mirrors the real wire format, so a scenario written against these mocks
reads the same as the live example it can later become.
"""

from __future__ import annotations

import json
from typing import Any, Callable

import httpx
from agents import Agent, OpenAIChatCompletionsModel
from openai import AsyncOpenAI

TEST_BASE_URL = "http://ziwei.test"


# ─────────────────────────── chat-completions (the model) ───────────────────────────

def assistant_text(content: str, *, id: str = "chatcmpl-text", model: str = "iztro-ziwei-v3") -> dict:
    """A finished assistant message (``finish_reason='stop'``)."""
    return {
        "id": id, "object": "chat.completion", "model": model,
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def assistant_tool_calls(*calls: tuple[str, dict], id: str = "chatcmpl-tools",
                         model: str = "iztro-ziwei-v3") -> dict:
    """An assistant turn that requests one or more tool calls.

    Each ``call`` is ``(tool_name, arguments_dict)``. Pass several for a single
    parallel-tool-call turn.
    """
    tool_calls = [
        {"id": f"call_{i}", "type": "function",
         "function": {"name": name, "arguments": json.dumps(args)}}
        for i, (name, args) in enumerate(calls)
    ]
    return {
        "id": id, "object": "chat.completion", "model": model,
        "choices": [{"index": 0, "finish_reason": "tool_calls",
                     "message": {"role": "assistant", "content": None, "tool_calls": tool_calls}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def sse_stream(deltas: list[str], *, finish: str = "stop", id: str = "chatcmpl-stream",
               model: str = "iztro-ziwei-v3") -> httpx.Response:
    """A streamed assistant message as Server-Sent Events (one chunk per delta)."""
    chunks = [{"id": id, "object": "chat.completion.chunk", "model": model,
               "choices": [{"index": 0, "delta": {"role": "assistant", "content": d} if i == 0
                            else {"content": d}, "finish_reason": None}]}
              for i, d in enumerate(deltas)]
    chunks.append({"id": id, "object": "chat.completion.chunk", "model": model,
                   "choices": [{"index": 0, "delta": {}, "finish_reason": finish}]})
    body = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
    return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body.encode())


class _ChatHandler:
    """An httpx handler for ``/v2/chat/completions`` that records every request.

    Built from a sequence of *responders*: each is a dict (returned verbatim), an
    ``httpx.Response`` (e.g. a stream), or a ``callable(body) -> dict|Response``. The
    nth call to the endpoint uses the nth responder; the last responder repeats if the
    model loops more times than responders were given.
    """

    def __init__(self, responders: list[Any]):
        self._responders = responders
        self.requests: list[dict] = []  # parsed JSON bodies, in call order

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.requests.append(body)
        idx = min(len(self.requests) - 1, len(self._responders) - 1)
        responder = self._responders[idx]
        if callable(responder) and not isinstance(responder, httpx.Response):
            responder = responder(body)
        if isinstance(responder, httpx.Response):
            return responder
        return httpx.Response(200, json=responder)

    @property
    def advertised_tools(self) -> list[list[str]]:
        """Tool names offered to the model on each request (to assert iztro stays hidden)."""
        return [[t["function"]["name"] for t in b.get("tools", [])] for b in self.requests]


def mock_chat(*responders: Any) -> _ChatHandler:
    """Build a recording chat-completions handler from a sequence of responders."""
    return _ChatHandler(list(responders))


def agent_with(handler: _ChatHandler, *, tools: list | None = None,
               base_url: str = TEST_BASE_URL, **agent_kwargs: Any) -> Agent:
    """A stock SDK ``Agent`` whose hosted model is wired to ``handler`` (offline)."""
    client = AsyncOpenAI(
        base_url=f"{base_url}/v2", api_key="sk_ziwei_test",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    model = OpenAIChatCompletionsModel(model="iztro-ziwei-v3", openai_client=client)
    return Agent(name="Ziwei", model=model, tools=list(tools or []), **agent_kwargs)


# ─────────────────────────── conversations (the memory store) ───────────────────────

class InMemoryConversations:
    """A minimal in-memory stand-in for the ``/v2/platform/conversations`` API.

    Faithful enough that `ChatSession` (create-lazily, add/get/pop/clear) and
    `list_user_conversations` work end-to-end with no network. Inspect `store`,
    `owners`, and `auth_seen` from tests.
    """

    def __init__(self) -> None:
        self.store: dict[str, list[dict]] = {}
        self.owners: dict[str, str | None] = {}
        self.auth_seen: set[str] = set()
        self._counter = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.auth_seen.add(request.headers.get("authorization", ""))
        method, path = request.method, request.url.path
        parts = path.strip("/").split("/")  # v2/platform/...

        # POST /v2/platform/conversations  → create (server assigns id)
        if path.endswith("/platform/conversations") and method == "POST":
            self._counter += 1
            cid = f"conv_{self._counter}"
            body = json.loads(request.content) if request.content else {}
            self.store[cid] = []
            self.owners[cid] = body.get("external_user_id")
            return httpx.Response(200, json={"conversation_id": cid})

        # GET /v2/platform/users/{uid}/conversations  → list a user's chats
        if "users" in parts and path.endswith("/conversations") and method == "GET":
            uid = parts[parts.index("users") + 1]
            items = [{"conversation_id": c} for c, o in self.owners.items() if o == uid]
            return httpx.Response(200, json={"items": list(reversed(items))})

        # …/conversations/{cid}/items[...]
        if "/items" in path:
            cid = parts[parts.index("conversations") + 1]
            if cid not in self.store:
                return httpx.Response(404, json={"error": "no such conversation"})
            if path.endswith("/items/last") and method == "DELETE":
                item = self.store[cid].pop() if self.store[cid] else None
                return httpx.Response(200, json={"item": item})
            if method == "GET":
                return httpx.Response(200, json={"items": list(self.store[cid])})
            if method == "POST":
                self.store[cid].extend(json.loads(request.content)["items"])
                return httpx.Response(200, json={"ok": True})

        # DELETE /v2/platform/conversations/{cid}  → clear
        if "conversations" in parts and method == "DELETE":
            cid = parts[parts.index("conversations") + 1]
            self.store.pop(cid, None)
            self.owners.pop(cid, None)
            return httpx.Response(200, json={"ok": True})

        return httpx.Response(404, json={"error": f"unhandled {method} {path}"})


def attach_session(session, backend: InMemoryConversations) -> None:
    """Point a `ChatSession` at an in-memory backend, preserving its auth headers."""
    session._http = httpx.AsyncClient(
        transport=httpx.MockTransport(backend),
        headers=dict(session._http.headers),
    )
