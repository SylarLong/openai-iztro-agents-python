"""Diverse, offline tool-loop scenarios for the hosted Ziwei model + local tools.

Every test mocks ``/v2/chat/completions`` (no key, no network) and exercises a
different shape of the passthrough loop: plain chat, single/parallel/sequential tool
calls, typed arguments, local errors, unicode, and SDK tool-call settings. Each one is
a self-contained scenario that can graduate into an ``examples/`` script.
"""

import asyncio

from agents import ModelSettings, Runner, function_tool

from _mock import agent_with, assistant_text, assistant_tool_calls, mock_chat


def _run(agent, prompt):
    return asyncio.run(Runner.run(agent, prompt))


# 1) Pure chat: no developer tools, no tool calls — a single assistant message.
def test_plain_chat_no_tools():
    handler = mock_chat(assistant_text("紫微星坐命，主贵气。"))
    agent = agent_with(handler)
    result = _run(agent, "概述我的命宫主星")
    assert result.final_output == "紫微星坐命，主贵气。"
    assert [type(i).__name__ for i in result.new_items] == ["MessageOutputItem"]
    # With no developer tools, none are advertised (iztro stays hidden server-side).
    assert handler.advertised_tools == [[]]


# 2) Single tool with richly-typed arguments (str, int, list) round-trips intact.
def test_single_tool_typed_args():
    captured = {}

    @function_tool
    def plan_itinerary(city: str, days: int, activities: list[str]) -> str:
        """Draft a travel itinerary. Runs locally."""
        captured.update(city=city, days=days, activities=activities)
        return f"{days}-day plan for {city}: {', '.join(activities)}"

    handler = mock_chat(
        assistant_tool_calls(("plan_itinerary",
                              {"city": "Kyoto", "days": 3, "activities": ["temples", "tea"]})),
        assistant_text("Your Kyoto trip is set."),
    )
    result = _run(agent_with(handler, tools=[plan_itinerary]), "plan a lucky trip")
    assert captured == {"city": "Kyoto", "days": 3, "activities": ["temples", "tea"]}
    assert result.final_output == "Your Kyoto trip is set."
    # The developer tool is advertised; iztro never is.
    assert handler.advertised_tools[0] == ["plan_itinerary"]


# 3) Parallel tool calls: two tools requested in one assistant turn.
def test_parallel_tool_calls():
    order = []

    @function_tool
    def get_lucky_color(element: str) -> str:
        """Lucky color for a five-element type."""
        order.append(("color", element))
        return {"wood": "green", "fire": "red"}.get(element, "white")

    @function_tool
    def get_lucky_number(element: str) -> int:
        """Lucky number for a five-element type."""
        order.append(("number", element))
        return 3

    handler = mock_chat(
        assistant_tool_calls(("get_lucky_color", {"element": "fire"}),
                             ("get_lucky_number", {"element": "fire"})),
        assistant_text("Red, and the number 3."),
    )
    result = _run(agent_with(handler, tools=[get_lucky_color, get_lucky_number]), "lucky color and number?")
    assert {name for name, _ in order} == {"color", "number"}
    # Both tool outputs come back before the final message.
    assert [type(i).__name__ for i in result.new_items] == [
        "ToolCallItem", "ToolCallItem", "ToolCallOutputItem", "ToolCallOutputItem", "MessageOutputItem"]
    assert "Red" in result.final_output


# 4) Sequential multi-step: tool A, then (next round) tool B, then a final answer.
def test_sequential_multi_step():
    steps = []

    @function_tool
    def lookup_birth_chart(date: str) -> str:
        """Step 1: compute the chart."""
        steps.append("chart")
        return "命宫: 太阳"

    @function_tool
    def add_to_calendar(date: str, title: str) -> str:
        """Step 2: book the day."""
        steps.append("calendar")
        return f"Added '{title}' on {date}"

    handler = mock_chat(
        assistant_tool_calls(("lookup_birth_chart", {"date": "1990-06-15"})),
        assistant_tool_calls(("add_to_calendar", {"date": "2026-07-01", "title": "吉日"})),
        assistant_text("Chart read; July 1st booked."),
    )
    result = _run(agent_with(handler, tools=[lookup_birth_chart, add_to_calendar]), "read my chart then book a good day")
    assert steps == ["chart", "calendar"]  # strict ordering across rounds
    assert len(handler.requests) == 3       # three model round-trips
    assert "booked" in result.final_output


# 5) Several tools available; iztro is never advertised on any round.
def test_iztro_never_advertised():
    @function_tool
    def tool_a() -> str:
        """A."""
        return "a"

    @function_tool
    def tool_b() -> str:
        """B."""
        return "b"

    handler = mock_chat(
        assistant_tool_calls(("tool_b", {})),
        assistant_text("done"),
    )
    _run(agent_with(handler, tools=[tool_a, tool_b]), "use a tool")
    # On every request only the developer tools are offered — never an iztro_* tool.
    for advertised in handler.advertised_tools:
        assert set(advertised) == {"tool_a", "tool_b"}
        assert not any(name.startswith("iztro") for name in advertised)


# 6) A local tool that raises: the SDK feeds the error back and the model recovers.
def test_local_tool_error_recovers():
    @function_tool
    def divine(question: str) -> str:
        """Always fails this run."""
        raise RuntimeError("oracle offline")

    seen_error = {}

    def second_round(body):
        tool_msg = body["messages"][-1]
        seen_error["content"] = tool_msg.get("content", "")
        return assistant_text("Let me try a different reading instead.")

    handler = mock_chat(
        assistant_tool_calls(("divine", {"question": "career?"})),
        second_round,
    )
    result = _run(agent_with(handler, tools=[divine]), "what about my career?")
    assert "Error" in seen_error["content"] and "oracle offline" in seen_error["content"]
    assert result.final_output == "Let me try a different reading instead."


# 7) Unicode all the way through: Chinese prompt, Chinese tool args and output.
def test_unicode_round_trip():
    got = {}

    @function_tool
    def 记录笔记(标题: str, 内容: str) -> str:
        """记录一条笔记。"""
        got.update(标题=标题, 内容=内容)
        return f"已记录《{标题}》"

    handler = mock_chat(
        assistant_tool_calls(("记录笔记", {"标题": "流年运势", "内容": "丙午年宜稳健"})),
        assistant_text("已为你记录流年笔记。"),
    )
    result = _run(agent_with(handler, tools=[记录笔记]), "帮我记一条流年笔记")
    assert got == {"标题": "流年运势", "内容": "丙午年宜稳健"}
    assert result.final_output == "已为你记录流年笔记。"


# 8) SDK tool-call settings (tool_choice / parallel_tool_calls) reach the wire.
def test_tool_settings_passthrough():
    @function_tool
    def noop() -> str:
        """No-op."""
        return "ok"

    handler = mock_chat(
        assistant_tool_calls(("noop", {})),
        assistant_text("finished"),
    )
    agent = agent_with(
        handler, tools=[noop],
        model_settings=ModelSettings(tool_choice="required", parallel_tool_calls=True),
    )
    _run(agent, "go")
    first = handler.requests[0]
    assert first["tool_choice"] == "required"
    assert first["parallel_tool_calls"] is True


def test_qimen_question_time_metadata_passthrough():
    """The documented ModelSettings form must reach Chat Completions unchanged."""
    handler = mock_chat(assistant_text("ok"))
    agent = agent_with(
        handler,
        model_settings=ModelSettings(
            metadata={"current_datetime": "2026-07-20T14:30:00+08:00"}
        ),
    )

    _run(agent, "Should I move this partnership forward now?")

    assert handler.requests[0]["metadata"] == {
        "current_datetime": "2026-07-20T14:30:00+08:00"
    }


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("PASS", name)
