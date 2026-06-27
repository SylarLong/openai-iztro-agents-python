# openai-iztro-agents

Build your own **Ziwei (Purple Star Astrology / 紫微斗数) agent** in Python.

> `pip install openai-iztro-agents` → `import iztro_agents`
>
> 🟨 **Working in JavaScript / TypeScript?** See the sibling package [**openai-iztro-agents-js**](https://github.com/a5507203/openai-iztro-agents-js) — same design, JS conventions.

A thin layer on top of the [OpenAI Agents SDK](https://pypi.org/project/openai-agents/):

- The **hosted Ziwei agent and its iztro chart tools** run on the server (hidden) — exposed as a stock SDK model.
- **Your own function tools, MCP servers, and human-in-the-loop** run locally via the standard `Runner`.
- **Conversation memory** lives on the server via `ChatSession` (the OpenAI Conversations–style session).

You write ordinary OpenAI Agents SDK code — `Agent`, `Runner`, `@function_tool`, `agents.mcp`, `tool_choice`, `needs_approval` — and point the model at Ziwei.

## Install

```bash
pip install openai-iztro-agents
```

Get an API key (`sk_ziwei_*`) from the developer console.

## Quickstart

```python
import asyncio
from agents import Runner
from iztro_agents import iztro_ziwei_agent, ChatSession, function_tool

@function_tool
def add_to_calendar(date: str, title: str) -> str:
    """Add an event to the user's calendar. Runs locally."""
    return f"Added '{title}' on {date}"

async def main():
    agent = iztro_ziwei_agent(tools=[add_to_calendar], api_key="sk_ziwei_...")
    session = ChatSession(external_user_id="user_42")
    result = await Runner.run(
        agent,
        "I was born 1990-06-15 at 10am, male. Pick a good day next week and add it to my calendar.",
        session=session,
    )
    print(result.final_output)

asyncio.run(main())
```

`iztro_ziwei_agent(...)` returns a **stock `agents.Agent`** whose model is the hosted Ziwei agent — so everything from the OpenAI Agents SDK works unchanged (`result.new_items`, `Runner.run_streamed`, handoffs, tracing, …).

## Conversation memory & resume (ChatSession)

History is stored on the server with a **server-generated id**, owned by your `external_user_id`:

```python
from iztro_agents import ChatSession, list_user_conversations

session = ChatSession(external_user_id="user_42")     # ZIWEI_API_KEY from env
await Runner.run(agent, "My name is Alice.", session=session)
await Runner.run(agent, "What's my name?", session=session)   # remembers

conv_id = session.session_id          # save to resume later
ChatSession(conversation_id=conv_id)  # resume

# Manage a user's chats:
await list_user_conversations("user_42")
```

`session_id` precedence: explicit `conversation_id` > a server-assigned id created lazily on first use.

## Tool-call modes

Your tools use the SDK's native controls; the iztro tools are hidden (toggle with `enable_iztro_call`):

```python
from agents import ModelSettings
agent = iztro_ziwei_agent(
    tools=[...],
    model_settings=ModelSettings(tool_choice="auto", parallel_tool_calls=True),
)
```

## Human-in-the-loop (native SDK)

```python
@function_tool(needs_approval=True)
def send_email(to: str, subject: str, body: str) -> str: ...

result = await Runner.run(agent, "...")
while result.interruptions:          # SDK pauses before the tool runs
    state = result.to_state()
    for item in result.interruptions:
        state.approve(item)          # or state.reject(item)
    result = await Runner.run(agent, state)
```

## MCP servers

```python
from agents.mcp import MCPServerStdio
weather = MCPServerStdio(params={"command": "uvx", "args": ["mcp-server-weather"]})
agent = iztro_ziwei_agent(mcp_servers=[weather], api_key=KEY)
```

## Testing

```bash
# Fast, deterministic, offline (no key) — mocks the model + conversation HTTP:
pytest            # runs the whole offline suite (the live test self-skips)

# Live end-to-end against a deployed backend (opt-in):
ZIWEI_API_KEY=sk_ziwei_... pytest tests/test_live.py -v -s
# defaults to dev; prod via ZIWEI_BASE_URL=https://chat-api.iztro.com
```

The offline suite covers a wide range of scenarios — each test file is written so a
scenario can graduate into an `examples/` script:

| File | What it exercises |
|---|---|
| `tests/test_tool_loops.py` | plain chat, single/parallel/sequential tool calls, typed args, local-tool errors, unicode, `tool_choice`/`parallel_tool_calls`, and that iztro tools stay hidden |
| `tests/test_human_in_the_loop.py` | native `needs_approval` flow — approve, reject, and a mixed approve+reject turn |
| `tests/test_streaming.py` | `Runner.run_streamed` token deltas reassembling into `final_output` |
| `tests/test_session.py` | `ChatSession` memory — lazy id, add/get/pop/clear, multi-turn, ownership + listing, resume |
| `tests/test_factories.py` | credential/base-url resolution, `/v2` suffix, and SDK arg passthrough |

Shared offline backends live in `tests/_mock.py` (a fake chat-completions endpoint and an
in-memory conversation store).

## Notes

- Birth details are gathered by the Ziwei agent through the conversation — there is no `birth_info` parameter.
- The backend currently streams an answer as a single chunk (not token-by-token); `Runner.run_streamed` works but token-level streaming is a future backend enhancement.
- Streaming together with developer tools is not yet supported — use non-streaming `Runner.run` for tool loops.
- Multi-turn tool loops re-send the prompt each round, so they cost more tokens.
