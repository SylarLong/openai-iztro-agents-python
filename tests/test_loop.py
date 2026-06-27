"""Offline SDK-native test: stock Runner + a local tool, with the model HTTP mocked.

Verifies the dev-tool round-trip (tool_calls -> run local tool -> resend -> final)
with no LLM and no network, by mocking the /v2/chat/completions endpoint. Runnable
under plain pytest.
"""

import asyncio
import json

import httpx
from agents import Agent, OpenAIChatCompletionsModel, Runner, function_tool
from openai import AsyncOpenAI


def _make_agent(handler, tools):
    client = AsyncOpenAI(
        base_url="http://test/v2",
        api_key="sk_ziwei_test",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    model = OpenAIChatCompletionsModel(model="ziwei-agent", openai_client=client)
    return Agent(name="Ziwei", model=model, tools=tools)


def test_tool_round_trip():
    executed = []

    @function_tool
    def add_to_calendar(date: str, title: str) -> str:
        """Add an event to the user's calendar."""
        executed.append((date, title))
        return f"Added '{title}' on {date}"

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        # iztro is never advertised — only the developer's tool.
        assert [t["function"]["name"] for t in body.get("tools", [])] == ["add_to_calendar"]
        has_tool_result = any(m.get("role") == "tool" for m in body.get("messages", []))
        if not has_tool_result:
            return httpx.Response(200, json={
                "id": "chatcmpl-1", "object": "chat.completion", "model": "ziwei-agent",
                "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
                    "role": "assistant", "content": None,
                    "tool_calls": [{"id": "call_1", "type": "function", "function": {
                        "name": "add_to_calendar",
                        "arguments": json.dumps({"date": "2026-07-01", "title": "Lucky"})}}]}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}})
        assert "Added" in body["messages"][-1]["content"]
        return httpx.Response(200, json={
            "id": "chatcmpl-2", "object": "chat.completion", "model": "ziwei-agent",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": "Booked July 1st."}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16}})

    async def run():
        agent = _make_agent(handler, [add_to_calendar])
        return await Runner.run(agent, "add a lucky day")

    result = asyncio.run(run())
    assert executed == [("2026-07-01", "Lucky")]
    assert "July 1st" in result.final_output
    # SDK observability comes for free:
    assert [type(i).__name__ for i in result.new_items] == ["ToolCallItem", "ToolCallOutputItem", "MessageOutputItem"]


if __name__ == "__main__":
    test_tool_round_trip()
    print("PASS: SDK-native offline tool round-trip")
