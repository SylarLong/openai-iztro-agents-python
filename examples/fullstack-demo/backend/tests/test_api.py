import sys
from pathlib import Path

from fastapi.testclient import TestClient

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPOSITORY_ROOT / "tests"))

from _mock import InMemoryConversations, agent_with, attach_session, mock_chat, sse_stream  # noqa: E402
from iztro_agents import ChatSession  # noqa: E402

import app.main as main  # noqa: E402
from app.store import MetadataStore  # noqa: E402


def test_conversation_lifecycle_and_stream(monkeypatch, tmp_path: Path):
    conversations = InMemoryConversations()
    chat = mock_chat(sse_stream(["命盘", "回答"]), sse_stream(["分支回答"]))
    metadata = MetadataStore(tmp_path / "demo.sqlite3")

    def session_factory(*, conversation_id=None, external_user_id=None):
        session = ChatSession(
            conversation_id=conversation_id,
            external_user_id=external_user_id,
            api_key="sk_ziwei_test",
            base_url="http://ziwei.test",
        )
        attach_session(session, conversations)
        return session

    async def fake_fork(self, *, item_count=None, external_user_id=None):
        items = await self.get_items()
        copied = items if item_count is None else items[:item_count]
        child = session_factory(external_user_id=external_user_id or self.external_user_id)
        await child.get_items()
        await child.add_items(list(copied))
        return child

    async def fake_list(external_user_id, **_kwargs):
        return [
            {"conversation_id": conversation_id}
            for conversation_id, owner in conversations.owners.items()
            if owner == external_user_id
        ]

    monkeypatch.setattr(main, "API_KEY", "sk_ziwei_test")
    monkeypatch.setattr(main, "store", metadata)
    monkeypatch.setattr(main, "_session", session_factory)
    monkeypatch.setattr(main, "_agent", lambda: agent_with(chat))
    monkeypatch.setattr(main, "list_user_conversations", fake_list)
    monkeypatch.setattr(ChatSession, "fork", fake_fork)

    client = TestClient(main.app)
    created_response = client.post(
        "/api/conversations",
        json={"external_user_id": "alice", "title": "新会话"},
    )
    assert created_response.status_code == 201
    conversation_id = created_response.json()["conversation_id"]

    stream_response = client.post(
        f"/api/conversations/{conversation_id}/messages/stream",
        json={"external_user_id": "alice", "message": "看看我的命盘"},
    )
    assert stream_response.status_code == 200
    assert "event: delta" in stream_response.text
    assert "命盘" in stream_response.text
    assert "event: done" in stream_response.text

    detail = client.get(
        f"/api/conversations/{conversation_id}",
        params={"external_user_id": "alice"},
    ).json()
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["text"] == "命盘回答"

    renamed = client.patch(
        f"/api/conversations/{conversation_id}",
        json={"external_user_id": "alice", "title": "事业分析"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "事业分析"

    forked_response = client.post(
        f"/api/conversations/{conversation_id}/fork",
        json={"external_user_id": "alice"},
    )
    assert forked_response.status_code == 201
    forked_id = forked_response.json()["conversation_id"]
    assert forked_response.json()["parent_conversation_id"] == conversation_id

    listed = client.get("/api/conversations", params={"external_user_id": "alice"}).json()
    assert {item["conversation_id"] for item in listed["items"]} == {
        conversation_id,
        forked_id,
    }

    deleted = client.delete(
        f"/api/conversations/{forked_id}",
        params={"external_user_id": "alice"},
    )
    assert deleted.status_code == 204
    assert forked_id not in conversations.store
