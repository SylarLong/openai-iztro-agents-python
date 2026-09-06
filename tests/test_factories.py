"""Config & wiring of the factories — no network, no key required.

Validates credential/base-url resolution (args, env vars, defaults, trailing-slash
trimming), the ``/v2`` suffix, and that ``iztro_ziwei_agent`` passes SDK arguments
straight through to a stock ``Agent``.
"""

import httpx
import pytest
from agents import Agent, ModelSettings, OpenAIChatCompletionsModel, Runner
from openai import AsyncOpenAI
from openai.types.shared import Reasoning

from iztro_agents import (
    DEFAULT_BASE_URL,
    IZTRO_HYBRID_MODEL,
    IZTRO_QIMEN_FAST_MODEL,
    IZTRO_QIMEN_MODEL,
    IZTRO_ZIWEI_FAST_MODEL,
    IZTRO_ZIWEI_MODEL,
    TOOL_EVENT_TYPE,
    ChatSession,
    IztroToolEvent,
    IztroToolsStreamEvent,
    IztroZiweiModel,
    iztro_hybrid_agent,
    iztro_hybrid_model,
    iztro_qimen_agent,
    iztro_qimen_fast_agent,
    iztro_qimen_fast_model,
    iztro_qimen_model,
    iztro_ziwei_agent,
    iztro_ziwei_fast_agent,
    iztro_ziwei_fast_model,
    iztro_ziwei_model,
)
from _mock import assistant_text, mock_chat
from iztro_agents.model import iztro_qimen_model as qimen_model_factory
from iztro_agents.model import iztro_ziwei_model as model_factory


def _base_url(model) -> str:
    return str(model._client.base_url)


# ── model factory ────────────────────────────────────────────────────────────

def test_model_requires_api_key(monkeypatch):
    monkeypatch.delenv("ZIWEI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="api_key is required"):
        iztro_ziwei_model()


def test_model_api_key_from_env(monkeypatch):
    monkeypatch.setenv("ZIWEI_API_KEY", "sk_ziwei_env")
    monkeypatch.delenv("ZIWEI_BASE_URL", raising=False)
    model = iztro_ziwei_model()
    assert isinstance(model, OpenAIChatCompletionsModel)
    assert _base_url(model) == f"{DEFAULT_BASE_URL}/v2/"   # default base + /v2


def test_model_base_url_precedence_and_trailing_slash(monkeypatch):
    monkeypatch.setenv("ZIWEI_BASE_URL", "http://from-env.test")
    # Explicit arg wins over the env var; a trailing slash is trimmed before /v2.
    model = iztro_ziwei_model(api_key="k", base_url="http://explicit.test/")
    assert _base_url(model) == "http://explicit.test/v2/"

    # With no arg, the env var is used.
    model_env = iztro_ziwei_model(api_key="k")
    assert _base_url(model_env) == "http://from-env.test/v2/"


def test_model_default_constants():
    assert DEFAULT_BASE_URL == "https://chat-api.iztro.com"
    assert IZTRO_ZIWEI_MODEL == "iztro-ziwei-v3"
    assert IZTRO_QIMEN_MODEL == "iztro-qimen-v3"
    assert IZTRO_HYBRID_MODEL == "iztro-hybrid-v3"
    assert IZTRO_ZIWEI_FAST_MODEL == "iztro-ziwei-v3-fast"
    assert IZTRO_QIMEN_FAST_MODEL == "iztro-qimen-v3-fast"
    assert TOOL_EVENT_TYPE == "tool_event"
    model = iztro_ziwei_model(api_key="k")
    assert model.model == IZTRO_ZIWEI_MODEL


def test_tool_event_alias_keeps_old_import_working():
    event = IztroToolEvent(["qimen-qigua"])
    assert event.type == "tool_event"
    assert event.tools == ["qimen-qigua"]
    assert isinstance(event, IztroToolsStreamEvent)


def test_qimen_model_factory_uses_qimen_model():
    model = iztro_qimen_model(api_key="k")
    assert isinstance(model, OpenAIChatCompletionsModel)
    assert model.model == IZTRO_QIMEN_MODEL
    assert _base_url(model) == f"{DEFAULT_BASE_URL}/v2/"


def test_hybrid_model_factory_uses_hybrid_model():
    model = iztro_hybrid_model(api_key="k")
    assert isinstance(model, OpenAIChatCompletionsModel)
    assert model.model == IZTRO_HYBRID_MODEL
    assert _base_url(model) == f"{DEFAULT_BASE_URL}/v2/"


def test_fast_model_factories_use_fast_models():
    ziwei = iztro_ziwei_fast_model(api_key="k")
    qimen = iztro_qimen_fast_model(api_key="k")

    assert ziwei.model == IZTRO_ZIWEI_FAST_MODEL
    assert qimen.model == IZTRO_QIMEN_FAST_MODEL


def test_model_custom_model_name():
    model = iztro_ziwei_model(api_key="k", model="iztro-ziwei-v9")
    assert model.model == "iztro-ziwei-v9"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("model_name", "effort"),
    (
        (IZTRO_ZIWEI_MODEL, "none"),
        (IZTRO_ZIWEI_MODEL, "low"),
        (IZTRO_ZIWEI_MODEL, "high"),
        (IZTRO_QIMEN_MODEL, "none"),
        (IZTRO_QIMEN_MODEL, "low"),
        (IZTRO_QIMEN_MODEL, "high"),
        (IZTRO_HYBRID_MODEL, "none"),
        (IZTRO_HYBRID_MODEL, "low"),
        (IZTRO_HYBRID_MODEL, "high"),
        (IZTRO_ZIWEI_FAST_MODEL, "none"),
        (IZTRO_ZIWEI_FAST_MODEL, "low"),
        (IZTRO_ZIWEI_FAST_MODEL, "high"),
        (IZTRO_QIMEN_FAST_MODEL, "none"),
        (IZTRO_QIMEN_FAST_MODEL, "low"),
        (IZTRO_QIMEN_FAST_MODEL, "high"),
    ),
)
async def test_native_reasoning_effort_reaches_wire(model_name, effort):
    handler = mock_chat(assistant_text("ok", model=model_name))
    client = AsyncOpenAI(
        base_url="http://ziwei.test/v2",
        api_key="k",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    model = IztroZiweiModel(model=model_name, openai_client=client)
    agent = Agent(
        name="Iztro",
        model=model,
        model_settings=ModelSettings(
            max_tokens=123,
            reasoning=Reasoning(effort=effort),
            metadata={"current_datetime": "2026-07-20T14:30:00+08:00"},
        ),
    )

    await Runner.run(agent, "hi")

    request = handler.requests[0]
    assert request["reasoning_effort"] == effort
    assert "thinking" not in request
    assert request["max_tokens"] == 123
    assert request["metadata"]["current_datetime"] == "2026-07-20T14:30:00+08:00"


@pytest.mark.asyncio
async def test_default_factory_omits_reasoning_effort():
    handler = mock_chat(assistant_text("ok"))
    client = AsyncOpenAI(
        base_url="http://ziwei.test/v2",
        api_key="k",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    model = IztroZiweiModel(model=IZTRO_ZIWEI_MODEL, openai_client=client)

    await Runner.run(Agent(name="Ziwei", model=model), "hi")

    assert "reasoning_effort" not in handler.requests[0]
    assert "thinking" not in handler.requests[0]


# ── agent factory ────────────────────────────────────────────────────────────

def test_agent_is_stock_agent_with_passthrough():
    from agents import function_tool

    @function_tool
    def my_tool() -> str:
        """A local tool."""
        return "ok"

    sentinel_mcp = object()  # stand-in MCP server; just checking it's forwarded
    agent = iztro_ziwei_agent(
        name="Stargazer",
        instructions="Be concise.",
        tools=[my_tool],
        mcp_servers=[sentinel_mcp],
        api_key="k",
        model_name="iztro-ziwei-v9",
    )
    assert isinstance(agent, Agent)
    assert agent.name == "Stargazer"
    assert agent.instructions == "Be concise."
    assert [t.name for t in agent.tools] == ["my_tool"]
    assert agent.mcp_servers == [sentinel_mcp]
    assert isinstance(agent.model, OpenAIChatCompletionsModel)
    assert agent.model.model == "iztro-ziwei-v9"


def test_agent_defaults_empty_tools():
    agent = iztro_ziwei_agent(api_key="k")
    assert agent.name == "Ziwei"
    assert agent.tools == []
    assert agent.mcp_servers == []


def test_qimen_agent_factory_uses_qimen_model():
    agent = iztro_qimen_agent(api_key="k")
    assert isinstance(agent, Agent)
    assert agent.name == "Qimen"
    assert isinstance(agent.model, OpenAIChatCompletionsModel)
    assert agent.model.model == IZTRO_QIMEN_MODEL
    assert agent.tools == []
    assert agent.mcp_servers == []


def test_fast_agent_factories_use_fast_models():
    ziwei = iztro_ziwei_fast_agent(api_key="k")
    qimen = iztro_qimen_fast_agent(api_key="k")

    assert ziwei.name == "Ziwei Fast"
    assert qimen.name == "Qimen Fast"
    assert ziwei.model.model == IZTRO_ZIWEI_FAST_MODEL
    assert qimen.model.model == IZTRO_QIMEN_FAST_MODEL
    assert ziwei.tools == []
    assert qimen.tools == []


def test_hybrid_agent_factory_uses_hybrid_model():
    agent = iztro_hybrid_agent(api_key="k")
    assert isinstance(agent, Agent)
    assert agent.name == "Ziwei + Qimen"
    assert isinstance(agent.model, OpenAIChatCompletionsModel)
    assert agent.model.model == IZTRO_HYBRID_MODEL
    assert agent.tools == []
    assert agent.mcp_servers == []


def test_agent_forwards_extra_kwargs():
    # Unknown-to-the-factory kwargs (e.g. tool_use_behavior) reach the SDK Agent.
    agent = iztro_ziwei_agent(api_key="k", tool_use_behavior="stop_on_first_tool")
    assert agent.tool_use_behavior == "stop_on_first_tool"


def test_agent_requires_api_key(monkeypatch):
    monkeypatch.delenv("ZIWEI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="api_key is required"):
        iztro_ziwei_agent()


# ── session factory ──────────────────────────────────────────────────────────

def test_session_requires_api_key(monkeypatch):
    monkeypatch.delenv("ZIWEI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="api_key is required"):
        ChatSession(external_user_id="user_42")


def test_reexport_identity():
    # The package re-exports the same factory object documented in model.py.
    assert iztro_ziwei_model is model_factory
    assert iztro_qimen_model is qimen_model_factory


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
