"""Streaming chat via ``Runner.run_streamed`` — offline, against a mocked SSE backend.

The hosted backend streams a plain answer (no developer tools while streaming). We
assert the token deltas arrive in order and that ``final_output`` reassembles them.
"""

import asyncio

from agents import Runner
from openai.types.responses import ResponseTextDeltaEvent

from _mock import agent_with, mock_chat, sse_stream


def _stream(agent, prompt):
    async def go():
        streamed = Runner.run_streamed(agent, prompt)
        deltas = []
        async for ev in streamed.stream_events():
            if ev.type == "raw_response_event" and isinstance(ev.data, ResponseTextDeltaEvent):
                deltas.append(ev.data.delta)
        return deltas, streamed.final_output
    return asyncio.run(go())


def test_stream_deltas_reassemble():
    handler = mock_chat(sse_stream(["Your ", "Purple ", "Star ", "shines."]))
    deltas, final = _stream(agent_with(handler), "describe my star")
    assert deltas == ["Your ", "Purple ", "Star ", "shines."]
    assert final == "Your Purple Star shines."


def test_stream_unicode():
    handler = mock_chat(sse_stream(["紫微", "在", "命宫"]))
    deltas, final = _stream(agent_with(handler), "我的命宫主星？")
    assert "".join(deltas) == "紫微在命宫"
    assert final == "紫微在命宫"


if __name__ == "__main__":
    test_stream_deltas_reassemble()
    test_stream_unicode()
    print("PASS streaming")
