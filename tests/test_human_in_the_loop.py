"""Human-in-the-loop via the native SDK approval flow — offline.

A ``@function_tool(needs_approval=True)`` pauses the run; ``Runner.run`` returns with
``interruptions``. We approve/reject and resume by running the saved state. Covers the
approve path, the reject path, and a mix of both in one turn.
"""

import asyncio

from agents import Runner, function_tool

from _mock import agent_with, assistant_text, assistant_tool_calls, mock_chat


def _resume_with(agent, decisions: dict[str, bool]):
    """Run, then approve/reject each pending tool by name per ``decisions``, until done."""
    async def go():
        result = await Runner.run(agent, "act on my chart")
        rounds = [len(result.interruptions)]
        while result.interruptions:
            state = result.to_state()
            for item in result.interruptions:
                name = getattr(item.raw_item, "name", "tool")
                state.approve(item) if decisions.get(name, False) else state.reject(item)
            result = await Runner.run(agent, state)
            rounds.append(len(result.interruptions))
        return result, rounds
    return asyncio.run(go())


def test_hitl_approve():
    sent = []

    @function_tool(needs_approval=True)
    def send_email(to: str, body: str) -> str:
        """Send an email on the user's behalf."""
        sent.append((to, body))
        return f"sent to {to}"

    handler = mock_chat(
        assistant_tool_calls(("send_email", {"to": "me@example.com", "body": "good year ahead"})),
        assistant_text("Email sent — onward to a bright year."),
    )
    result, rounds = _resume_with(agent_with(handler, tools=[send_email]), {"send_email": True})
    assert rounds[0] == 1                      # paused for approval
    assert sent == [("me@example.com", "good year ahead")]
    assert "Email sent" in result.final_output


def test_hitl_reject():
    sent = []

    @function_tool(needs_approval=True)
    def send_email(to: str, body: str) -> str:
        """Send an email on the user's behalf."""
        sent.append((to, body))
        return f"sent to {to}"

    handler = mock_chat(
        assistant_tool_calls(("send_email", {"to": "me@example.com", "body": "draft"})),
        assistant_text("Understood — I won't send anything."),
    )
    result, rounds = _resume_with(agent_with(handler, tools=[send_email]), {"send_email": False})
    assert rounds[0] == 1
    assert sent == []                          # rejected → never executed locally
    assert "won't send" in result.final_output


def test_hitl_mixed_in_one_turn():
    executed = []

    @function_tool(needs_approval=True)
    def book_flight(dest: str) -> str:
        """Book a flight."""
        executed.append(("flight", dest))
        return f"flight to {dest} booked"

    @function_tool(needs_approval=True)
    def wire_money(amount: int) -> str:
        """Wire money."""
        executed.append(("money", amount))
        return f"wired {amount}"

    handler = mock_chat(
        assistant_tool_calls(("book_flight", {"dest": "Tokyo"}), ("wire_money", {"amount": 5000})),
        assistant_text("Flight booked; the transfer was held back."),
    )
    # Two tools pause together; approve the flight, reject the wire.
    result, rounds = _resume_with(
        agent_with(handler, tools=[book_flight, wire_money]),
        {"book_flight": True, "wire_money": False},
    )
    assert rounds[0] == 2                       # both paused in the same turn
    assert executed == [("flight", "Tokyo")]   # only the approved one ran
    assert "Flight booked" in result.final_output


if __name__ == "__main__":
    test_hitl_approve()
    test_hitl_reject()
    test_hitl_mixed_in_one_turn()
    print("PASS human-in-the-loop")
