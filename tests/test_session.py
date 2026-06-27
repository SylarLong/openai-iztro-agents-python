"""ChatSession memory semantics against an in-memory conversation store — offline.

Covers lazy server-side id creation, add/get/pop/clear, multi-turn accumulation,
ownership by ``external_user_id`` + ``list_user_conversations``, resuming an explicit
id without a create call, and that the auth header is sent.
"""

import asyncio

import httpx

import iztro_agents.session as session_mod
from iztro_agents import ChatSession, list_user_conversations

from _mock import InMemoryConversations, attach_session


def _session(backend, **kw):
    s = ChatSession(api_key="sk_ziwei_test", base_url="http://ziwei.test", **kw)
    attach_session(s, backend)
    return s


def test_id_is_lazy_then_assigned():
    backend = InMemoryConversations()
    s = _session(backend, external_user_id="user_42")

    async def go():
        # Before any operation, the id does not exist yet.
        raised = False
        try:
            _ = s.session_id
        except ValueError:
            raised = True
        assert raised, "session_id should raise before the conversation is created"

        await s.add_items([{"role": "user", "content": "hi"}])
        assert s.session_id == "conv_1"       # server assigned it on first use
        assert backend.owners["conv_1"] == "user_42"
        await s.close()

    asyncio.run(go())


def test_add_get_pop_clear():
    backend = InMemoryConversations()
    s = _session(backend)

    async def go():
        await s.add_items([{"role": "user", "content": "born 1990-06-15"},
                           {"role": "assistant", "content": "noted"}])
        items = await s.get_items()
        assert [i["content"] for i in items] == ["born 1990-06-15", "noted"]

        popped = await s.pop_item()
        assert popped["content"] == "noted"
        assert [i["content"] for i in await s.get_items()] == ["born 1990-06-15"]

        cid = s.session_id
        await s.clear_session()
        assert cid not in backend.store        # conversation deleted on the server
        assert s._conversation_id is None      # next op will create a fresh one

        await s.add_items([{"role": "user", "content": "again"}])
        assert s.session_id != cid             # a brand-new conversation id
        await s.close()

    asyncio.run(go())


def test_multi_turn_accumulates():
    backend = InMemoryConversations()
    s = _session(backend)

    async def go():
        # Two "turns" each append a user+assistant pair to the same conversation.
        await s.add_items([{"role": "user", "content": "q1"}, {"role": "assistant", "content": "a1"}])
        await s.add_items([{"role": "user", "content": "q2"}, {"role": "assistant", "content": "a2"}])
        contents = [i["content"] for i in await s.get_items()]
        assert contents == ["q1", "a1", "q2", "a2"]   # history grows, order preserved
        await s.close()

    asyncio.run(go())


def test_ownership_and_listing(monkeypatch):
    backend = InMemoryConversations()

    # Make the public list_user_conversations talk to our in-memory backend.
    real_client = httpx.AsyncClient

    def offline_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(backend)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(session_mod.httpx, "AsyncClient", offline_client)

    async def go():
        s1 = _session(backend, external_user_id="alice")
        s2 = _session(backend, external_user_id="alice")
        s3 = _session(backend, external_user_id="bob")
        await s1.add_items([{"role": "user", "content": "a"}])
        await s2.add_items([{"role": "user", "content": "b"}])
        await s3.add_items([{"role": "user", "content": "c"}])

        convs = await list_user_conversations(
            "alice", api_key="sk_ziwei_test", base_url="http://ziwei.test")
        ids = {c["conversation_id"] for c in convs}
        assert ids == {s1.session_id, s2.session_id}   # only alice's chats
        assert s3.session_id not in ids                 # bob's is excluded
        for s in (s1, s2, s3):
            await s.close()

    asyncio.run(go())


def test_resume_explicit_id_skips_create():
    backend = InMemoryConversations()
    # Pre-seed a conversation as if it already existed on the server.
    backend.store["conv_existing"] = [{"role": "user", "content": "earlier"}]
    backend.owners["conv_existing"] = "user_42"

    s = _session(backend, conversation_id="conv_existing")

    async def go():
        assert s.session_id == "conv_existing"       # available immediately, no create
        items = await s.get_items()
        assert items[0]["content"] == "earlier"
        assert backend._counter == 0                  # no POST /conversations happened
        await s.close()

    asyncio.run(go())


def test_auth_header_sent():
    backend = InMemoryConversations()
    s = _session(backend)

    async def go():
        await s.add_items([{"role": "user", "content": "x"}])
        assert "Bearer sk_ziwei_test" in backend.auth_seen
        await s.close()

    asyncio.run(go())


if __name__ == "__main__":
    import inspect

    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            if inspect.signature(fn).parameters:
                print("SKIP", name, "(needs a pytest fixture — run via pytest)")
                continue
            fn()
            print("PASS", name)
