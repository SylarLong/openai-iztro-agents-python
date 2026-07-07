"""Factories for hosted Iztro models as stock OpenAI Agents SDK models.

The hosted models run astrology tools on the server and report which ran via a custom
``iztro_tools`` field on the chat-completion response. The base SDK drops every
non-standard field, so :class:`IztroZiweiModel` adds it back where it belongs:

* non-streaming → each ``result.raw_responses[i]`` is an :class:`IztroModelResponse`
  carrying that call's ``iztro_tools``;
* streaming → an :class:`IztroToolEvent` is emitted as each tool is called.

We never fake standard ``tool_calls`` (which would make the SDK try to execute the
server-side tools locally).
"""

from __future__ import annotations

import dataclasses
import os
from typing import Any

import pydantic
from agents import ModelResponse, OpenAIChatCompletionsModel
from openai import AsyncOpenAI

DEFAULT_BASE_URL = "https://chat-api.iztro.com"
IZTRO_ZIWEI_MODEL = "iztro-ziwei-v3"
IZTRO_QIMEN_MODEL = "iztro-qimen-v3"
TOOL_EVENT_TYPE = "tool_event"


@pydantic.dataclasses.dataclass
class IztroModelResponse(ModelResponse):
    """A stock :class:`~agents.ModelResponse` that also carries the hidden server-side
    iztro chart tools that ran for *this* model call.

    The base SDK drops the custom ``iztro_tools`` field; we add it back here so it rides
    the SDK's own structures. After ``Runner.run``, read it per model call::

        result = await Runner.run(agent, "...")
        for resp in result.raw_responses:           # one per model call
            print(getattr(resp, "iztro_tools", []))

    Because it lives on the response (not on the shared model), a multi-step run keeps
    every call's tools instead of overwriting them.
    """

    iztro_tools: list[str] = dataclasses.field(default_factory=list)
    tool_event: Any = None


class IztroToolEvent:
    """Streaming event emitted as the server runs an iztro chart tool, *before* the answer.

    During ``Runner.run_streamed(...)``, the model emits one of these as each batch of
    server-side iztro tools is called. It rides the SDK's normal event stream, so it
    surfaces in ``stream_events()`` as a ``raw_response_event`` whose ``.data`` is this
    object — handle it in the same ``if event.type`` loop as text deltas::

        async for event in streamed.stream_events():
            if event.type == "raw_response_event":
                if isinstance(event.data, IztroToolEvent):
                    print("iztro:", event.data.tools)
                elif isinstance(event.data, ResponseTextDeltaEvent):
                    print(event.data.delta, end="")

    ``.tools`` is the new labels for this batch; ``.type`` is the literal
    ``"tool_event"``.
    """

    type = TOOL_EVENT_TYPE

    def __init__(self, tools: list[str]):
        self.tools = list(tools)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"IztroToolEvent(tools={self.tools!r})"


# Backwards-compatible name kept for existing integrations.
IztroToolsStreamEvent = IztroToolEvent


def _extract_iztro_tools(obj: Any) -> list[str]:
    """Read the custom ``iztro_tools`` field off a raw ChatCompletion / ChatCompletionChunk.
    The openai client keeps unknown top-level fields (as an attribute and in ``model_extra``)."""
    val = getattr(obj, "iztro_tools", None)
    if val is None:
        extra = getattr(obj, "model_extra", None)
        if isinstance(extra, dict):
            val = extra.get("iztro_tools")
    return [str(x) for x in val] if isinstance(val, list) else []


class IztroZiweiModel(OpenAIChatCompletionsModel):
    """Stock chat-completions model that also surfaces the hidden server-side iztro tools.

    * Non-streaming (``Runner.run``): each ``result.raw_responses[i]`` is an
      :class:`IztroModelResponse` whose ``iztro_tools`` lists that call's tools.
    * Streaming (``Runner.run_streamed``): an :class:`IztroToolEvent` is emitted
      in ``stream_events()`` as each tool is called.

    ``model.last_tool_event`` is a convenience holding the most recent tool event.
    ``model.last_iztro_tools`` remains as a compatibility alias for the tools list.
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.last_tool_event: IztroToolEvent | None = None
        self.last_iztro_tools: list[str] = []
        # Buffer of new-label batches detected mid-stream, drained by stream_response
        # to emit IztroToolEvent at the right point in the event stream.
        self._stream_pending: list[list[str]] = []
        # iztro tools from the in-flight non-streaming call, read by get_response to
        # attach them to that call's IztroModelResponse.
        self._call_tools: list[str] = []

    async def get_response(self, *args: Any, **kwargs: Any) -> ModelResponse:  # type: ignore[override]
        # Non-streaming run. Let the base build the ModelResponse, then re-wrap it as an
        # IztroModelResponse carrying this call's iztro tools — so result.raw_responses[i]
        # exposes them per model call (no overwrite across a multi-step run).
        self._call_tools = []
        resp = await super().get_response(*args, **kwargs)
        return IztroModelResponse(
            output=resp.output,
            usage=resp.usage,
            response_id=resp.response_id,
            request_id=resp.request_id,
            iztro_tools=list(self._call_tools),
            tool_event=IztroToolEvent(self._call_tools) if self._call_tools else None,
        )

    async def stream_response(self, *args: Any, **kwargs: Any):  # type: ignore[override]
        # Wrap the base streamed events and splice in an IztroToolEvent as each
        # batch of server-side iztro tools is called. _capture_stream (run inside the
        # base generator) fills self._stream_pending; we drain it right before the next
        # base event, so the iztro event lands *before* the text it precedes.
        self.last_tool_event = None
        self.last_iztro_tools = []
        self._stream_pending = []
        async for event in super().stream_response(*args, **kwargs):
            while self._stream_pending:
                yield IztroToolEvent(self._stream_pending.pop(0))
            yield event
        while self._stream_pending:
            yield IztroToolEvent(self._stream_pending.pop(0))

    async def _fetch_response(self, *args: Any, **kwargs: Any):  # type: ignore[override]
        result = await super()._fetch_response(*args, **kwargs)
        if isinstance(result, tuple):
            # Streaming: (response, stream). Wrap the stream to capture from chunks.
            response, raw_stream = result
            return response, self._capture_stream(raw_stream)
        # Non-streaming: a ChatCompletion — the full list arrives at once.
        tools = _extract_iztro_tools(result)
        self._call_tools = tools  # picked up by get_response for this call's response
        if tools:
            self.last_tool_event = IztroToolEvent(tools)
            self.last_iztro_tools = tools
        return result

    async def _capture_stream(self, raw_stream: Any):
        # Tools arrive across multiple chunks as the model calls them (before the answer).
        # Accumulate + dedup: queue each NEW tool for an IztroToolEvent, keep the
        # full list in last_iztro_tools.
        seen: list[str] = []
        async for chunk in raw_stream:
            new = [t for t in _extract_iztro_tools(chunk) if t not in seen]
            if new:
                seen.extend(new)
                self.last_tool_event = IztroToolEvent(list(seen))
                self.last_iztro_tools = list(seen)
                self._stream_pending.append(list(new))  # → IztroToolEvent in stream_response
            yield chunk


def iztro_ziwei_model(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str = IZTRO_ZIWEI_MODEL,
) -> IztroZiweiModel:
    """Build the hosted Ziwei agent as a stock OpenAI Agents SDK model.

    ``api_key`` / ``base_url`` fall back to ``ZIWEI_API_KEY`` / ``ZIWEI_BASE_URL``. After a
    run, read the server-side iztro tools from
    ``result.raw_responses[i].tool_event`` / ``.iztro_tools`` (non-streaming) or
    from :class:`IztroToolEvent` (streaming).

        from agents import Agent, Runner
        from iztro_agents import iztro_ziwei_model

        model = iztro_ziwei_model(api_key=KEY)
        agent = Agent(name="Ziwei", model=model, tools=[...])
        result = await Runner.run(agent, "…")
        print(result.raw_responses[-1].iztro_tools)
    """
    api_key = api_key or os.environ.get("ZIWEI_API_KEY")
    if not api_key:
        raise ValueError("api_key is required (pass api_key=... or set ZIWEI_API_KEY)")
    base = (base_url or os.environ.get("ZIWEI_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    client = AsyncOpenAI(base_url=f"{base}/v2", api_key=api_key)
    return IztroZiweiModel(model=model, openai_client=client)


def iztro_qimen_model(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str = IZTRO_QIMEN_MODEL,
) -> IztroZiweiModel:
    """Build the hosted Qimen agent as a stock OpenAI Agents SDK model.

    Qimen uses the same transport and event surface as Ziwei. Server-side qimen tools
    such as ``qimen-qigua`` and ``qimen-yingqi`` appear in
    ``result.raw_responses[i].tool_event`` / ``.iztro_tools`` or as
    :class:`IztroToolEvent`.
    """
    return iztro_ziwei_model(api_key=api_key, base_url=base_url, model=model)
