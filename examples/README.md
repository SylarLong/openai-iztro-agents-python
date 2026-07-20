# Examples — start here

These are small, runnable programs that show what the Ziwei (Purple Star Astrology /
紫微斗数) agent can do. They go from the **simplest** to the **more advanced** — work
through them in order. You do **not** need to be an experienced programmer; each file is
heavily commented and prints what it is doing.

## 1. One-time setup

**a) Install Python 3.10 or newer.** Check what you have:

```bash
python --version
```

**b) Install the package:**

```bash
pip install openai-iztro-agents
```

**c) Get an API key** (it looks like `sk_ziwei_...`) from the developer console.

**d) Tell the examples your key.** Easiest way — set it once in your terminal:

```bash
# Windows (PowerShell):
$env:ZIWEI_API_KEY = "sk_ziwei_your_key_here"

# macOS / Linux:
export ZIWEI_API_KEY="sk_ziwei_your_key_here"
```

(Or open any example and paste your key on the `API_KEY = ...` line.)

## 2. Run an example

From the project folder:

```bash
python examples/01_hello_ziwei.py
```

That's it. The reading prints to your screen.

## 3. The examples, simplest first

| File | What it teaches | Key idea |
|---|---|---|
| `01_hello_ziwei.py` | Your first program: one rich, professional, chart-grounded reading. | the basics |
| `02_prompt_gallery.py` | **The showcase** — the same chart read for personality, fortune (流年运势), career, love, and wealth. Copy any prompt. | depth & variety |
| `03_streaming_chat.py` | Show the reply as it's typed, live. | `Runner.run_streamed` |
| `04_memory_and_resume.py` | Remember a conversation and **resume it later** (save the id, reload it next request). | `ChatSession` |
| `05_basic_local_tool.py` | Let the agent call **one** of your Python functions. | `@function_tool` |
| `06_two_tools_at_once.py` | The agent calls **two** of your functions in one turn. | parallel tools |
| `07_multi_step_booking.py` | A two-step task: check your calendar, then book a free day. | tools used in sequence |
| `08_human_in_the_loop.py` | Make the agent **ask your permission** before a sensitive action (e.g. sending email). | `needs_approval=True` |
| `09_limit_length_and_cost.py` | Cap output size to bound **cost** in production (not a quality setting). | `ModelSettings(max_tokens=…)` |
| `10_chinese_chat.py` | Do everything in Chinese (中文全程对话). | unicode end-to-end |
| `11_agent_as_tool.py` | Use the Ziwei agent as **one tool** inside your own GPT agent. | agents-as-tools |
| `12_qimen_decision.py` | Analyze one concrete decision and, when needed, calculate action windows with Qimen. | `iztro_qimen_agent` + question time |
| `fullstack-demo/` | A React + FastAPI chat app with session list, rename, delete, fork, message editing, chart-tool history, and streaming. | production integration shape |

## A few words you'll see

- **The chart is automatic.** The agent reads and summarizes the Purple Star chart for you,
  on the server. You never write a tool to compute or summarize the chart — your tools are
  only for **your** world (calendar, email, notes, your own data).
- **Agent** — the Ziwei "brain" you talk to. You build it with `iztro_ziwei_agent(...)`.
- **Tool** — one of *your* Python functions the agent is allowed to call. You mark it with
  `@function_tool`. Your tools run locally on your computer.
- **Runner** — the thing that actually runs a turn: `Runner.run(agent, "your question")`.
- **Depth is the point.** Let the agent answer fully — the rich, chart-grounded reading is
  what makes this different from a generic chatbot. Shape *what* it covers and its tone in
  the `instructions` (see `02_prompt_gallery.py`), not by forcing it short.
- **ModelSettings** — knobs for the model. `max_tokens` is a hard ceiling on reply length
  for **cost control in production** (see `09_limit_length_and_cost.py`) — a budget limit,
  not a quality setting.
- **ChatSession** — optional memory, so the agent remembers earlier messages. History lives
  on the server under a conversation id; **save `session.session_id`** to resume the chat
  later (see `04_memory_and_resume.py`). `list_user_conversations(user_id)` lists a user's chats.
- **Qimen** — use `iztro_qimen_agent(...)` for one concrete, time-sensitive matter. It casts
  from the question time and needs no birth details; keep unrelated decisions in separate runs
  so each matter gets its own chart (see `12_qimen_decision.py`).

## If something goes wrong

- **`api_key is required`** → you didn't set `ZIWEI_API_KEY` and didn't paste a key.
- **`ModuleNotFoundError: No module named 'iztro_agents'`** → run `pip install openai-iztro-agents`.
- **Chinese text looks garbled on Windows** → example 10 already fixes this; for your own
  scripts add `import sys; sys.stdout.reconfigure(encoding="utf-8")` near the top.

Each example is self-contained — copy one, change the question, and you have your own app.
