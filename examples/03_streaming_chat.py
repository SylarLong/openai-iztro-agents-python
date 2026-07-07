"""Example 03 — Streaming: print the answer as it is written.

Same as example 01, but instead of waiting for the whole reply, we print it piece by
piece as it arrives — the "typing" effect you see in chat apps. Use this when you want
the user to start reading immediately.

────────────────────────────────────────────────────────────────────────────
RUN IT      python examples/03_streaming_chat.py
WHAT YOU'LL SEE   The reading appears gradually, word by word, then a final summary line.
NOTE        Streaming is for plain chat. If you also need local tools (examples 06–07),
            use the normal `Runner.run` instead.
────────────────────────────────────────────────────────────────────────────
"""

import asyncio
import os

from agents import Runner
# This event type represents one small chunk ("delta") of streamed text.
from openai.types.responses import ResponseTextDeltaEvent

# Emitted as the server runs a hidden iztro chart tool — arrives in the same event stream.
from iztro_agents import iztro_ziwei_agent, IztroToolEvent

API_KEY = os.environ.get("ZIWEI_API_KEY") or "sk_ziwei_REPLACE_WITH_YOUR_KEY"


async def main() -> None:
    agent = iztro_ziwei_agent(
        instructions="You are a helpful Ziwei astrology guide.",
        api_key=API_KEY,
    )

    # `run_streamed` returns immediately; the text arrives over time as events.
    streamed = Runner.run_streamed(
        agent,
        "Born 1988-02-20 at 6am, female. Give me an uplifting outlook for this year.",
    )

    print(">> The reading is being written:\n")
    async for event in streamed.stream_events():
        # Both text chunks and iztro tool calls arrive as raw_response_events; branch on
        # the data type. (Other event types — tool items, agent updates — are ignored.)
        if event.type == "raw_response_event":
            if isinstance(event.data, IztroToolEvent):
                # The server just ran these chart tools — printed live, as they happen,
                # before the text that uses them.
                print(f"\n🔮 iztro computed: {', '.join(event.data.tools)}\n")
            elif isinstance(event.data, ResponseTextDeltaEvent):
                # end="" and flush=True keep it on one growing line, like live typing.
                print(event.data.delta, end="", flush=True)

    # Once streaming ends, the whole text is also available in one piece.
    print("\n\n=== Full reply (for reference) ===")
    print(streamed.final_output)


if __name__ == "__main__":
    asyncio.run(main())
