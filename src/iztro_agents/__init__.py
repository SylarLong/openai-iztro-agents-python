"""iztro-agents — build your own Ziwei or Qimen agent.

A thin layer on top of the OpenAI Agents SDK. The hosted Iztro models and their
astrology tools are exposed as stock models; your own function tools, MCP servers, and
human-in-the-loop run locally via the standard SDK ``Runner``. Conversation memory
lives on the server via ``ChatSession`` (the OpenAI Conversations-style session).

    from iztro_agents import iztro_ziwei_agent, ChatSession, function_tool
    from agents import Runner

    @function_tool
    def add_to_calendar(date: str, title: str) -> str:
        ...  # runs locally

    agent = iztro_ziwei_agent(tools=[add_to_calendar], api_key="sk_ziwei_...")
    session = ChatSession(external_user_id="user_42")
    result = await Runner.run(agent, "Per my chart, add a good day to my calendar", session=session)
    print(result.final_output)
"""

# Re-export the SDK essentials so callers can `from iztro_agents import ...`.
from agents import Agent, Runner, function_tool

from .agent import iztro_qimen_agent, iztro_ziwei_agent
from .model import (
    DEFAULT_BASE_URL,
    IZTRO_QIMEN_MODEL,
    IZTRO_ZIWEI_MODEL,
    IztroModelResponse,
    IztroToolEvent,
    IztroToolsStreamEvent,
    IztroZiweiModel,
    TOOL_EVENT_TYPE,
    iztro_qimen_model,
    iztro_ziwei_model,
)
from .session import ChatSession, list_user_conversations

__all__ = [
    "iztro_ziwei_agent",
    "iztro_ziwei_model",
    "iztro_qimen_agent",
    "iztro_qimen_model",
    "IztroZiweiModel",
    "IztroModelResponse",
    "IztroToolEvent",
    "IztroToolsStreamEvent",
    "ChatSession",
    "list_user_conversations",
    # convenience re-exports from the OpenAI Agents SDK:
    "Agent",
    "Runner",
    "function_tool",
    "DEFAULT_BASE_URL",
    "IZTRO_ZIWEI_MODEL",
    "IZTRO_QIMEN_MODEL",
    "TOOL_EVENT_TYPE",
]

__version__ = "0.2.1"
