"""Config & wiring of the factories — no network, no key required.

Validates credential/base-url resolution (args, env vars, defaults, trailing-slash
trimming), the ``/v2`` suffix, and that ``iztro_ziwei_agent`` passes SDK arguments
straight through to a stock ``Agent``.
"""

import pytest
from agents import Agent, OpenAIChatCompletionsModel

from iztro_agents import (
    DEFAULT_BASE_URL,
    IZTRO_ZIWEI_MODEL,
    ChatSession,
    iztro_ziwei_agent,
    iztro_ziwei_model,
)
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
    model = iztro_ziwei_model(api_key="k")
    assert model.model == IZTRO_ZIWEI_MODEL


def test_model_custom_model_name():
    model = iztro_ziwei_model(api_key="k", model="iztro-ziwei-v9")
    assert model.model == "iztro-ziwei-v9"


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


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
