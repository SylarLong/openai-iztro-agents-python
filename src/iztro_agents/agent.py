"""Thin factory that returns a stock OpenAI Agents SDK ``Agent`` wired to Ziwei."""

from __future__ import annotations

from typing import Any

from agents import Agent

from .model import IZTRO_QIMEN_MODEL, IZTRO_ZIWEI_MODEL, iztro_qimen_model, iztro_ziwei_model


def iztro_ziwei_agent(
    *,
    name: str = "Ziwei",
    instructions: str | None = None,
    tools: list[Any] | None = None,
    mcp_servers: list[Any] | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    model_name: str = IZTRO_ZIWEI_MODEL,
    **agent_kwargs: Any,
) -> Agent:
    """Return a stock ``agents.Agent`` whose model is the hosted Ziwei agent.

    Use it with the normal SDK: ``Runner.run(agent, "…", session=ChatSession(...))``.
    Developer ``tools`` (define with ``@function_tool``) and ``mcp_servers``
    (``agents.mcp``) run locally; the iztro chart tools stay hidden on the server.
    Human-in-the-loop and tool-call modes are native SDK features (``needs_approval``,
    ``ModelSettings.tool_choice``).

        from iztro_agents import iztro_ziwei_agent, ChatSession, function_tool
        from agents import Runner

        @function_tool
        def add_to_calendar(date: str, title: str) -> str: ...

        agent = iztro_ziwei_agent(tools=[add_to_calendar], api_key=KEY)
        session = ChatSession(external_user_id="user_42")
        result = await Runner.run(agent, "…", session=session)

    Which server-side tools ran is on ``result.raw_responses[i].tool_event`` /
    ``.iztro_tools`` (non-streaming) or surfaces as :class:`IztroToolEvent`
    (streaming).
    """
    return Agent(
        name=name,
        instructions=instructions,
        model=iztro_ziwei_model(api_key=api_key, base_url=base_url, model=model_name),
        tools=list(tools or []),
        mcp_servers=list(mcp_servers or []),
        **agent_kwargs,
    )


def iztro_qimen_agent(
    *,
    name: str = "Qimen",
    instructions: str | None = None,
    tools: list[Any] | None = None,
    mcp_servers: list[Any] | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    model_name: str = IZTRO_QIMEN_MODEL,
    **agent_kwargs: Any,
) -> Agent:
    """Return a stock ``agents.Agent`` whose model is the hosted Qimen agent.

    The Qimen model casts one chart from the question time for one concrete matter; it
    needs no birth details. It calls hosted ``qimen-qigua`` first and, when timing is
    relevant, ``qimen-yingqi`` after selecting the necessary yongshen. Pin a user's
    local question time with ``ModelSettings(metadata={"current_datetime": ...})``.

    Developer ``tools`` and ``mcp_servers`` run locally through the OpenAI Agents SDK.
    The Qimen tools stay hosted and are surfaced through ``tool_event`` /
    ``iztro_tools`` and :class:`IztroToolEvent`, the same way as
    ``iztro_ziwei_agent``.
    """
    return Agent(
        name=name,
        instructions=instructions,
        model=iztro_qimen_model(api_key=api_key, base_url=base_url, model=model_name),
        tools=list(tools or []),
        mcp_servers=list(mcp_servers or []),
        **agent_kwargs,
    )
