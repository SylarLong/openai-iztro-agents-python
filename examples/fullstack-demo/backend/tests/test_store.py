from pathlib import Path

from app.main import normalize_messages
from app.store import MetadataStore


def test_metadata_and_chart_calls(tmp_path: Path):
    store = MetadataStore(tmp_path / "demo.sqlite3")
    store.ensure_conversation("conv_1", "alice")
    store.title_from_first_message("conv_1", "这是一个足够长的第一条消息，用来自动生成会话标题。")
    store.record_chart_calls("conv_1", 1, ["ziwei-chart", "ziwei-chart", "annual-chart"])
    store.update_activity("conv_1", last_message="reply", item_count=2)

    conversation = store.list_conversations("alice")[0]
    assert conversation["title"].startswith("这是一个")
    assert conversation["last_message"] == "reply"
    assert conversation["item_count"] == 2
    assert store.charts_for_conversation("conv_1") == ["ziwei-chart", "annual-chart"]
    assert store.charts_by_item("conv_1") == {1: ["ziwei-chart", "annual-chart"]}


def test_fork_metadata_copies_only_prefix_tools(tmp_path: Path):
    store = MetadataStore(tmp_path / "demo.sqlite3")
    store.ensure_conversation("parent", "alice", title="原会话")
    store.ensure_conversation(
        "child",
        "alice",
        title="原会话 · 分支",
        parent_conversation_id="parent",
        forked_at_item=2,
    )
    store.record_chart_calls("parent", 1, ["natal-chart"])
    store.record_chart_calls("parent", 3, ["annual-chart"])
    store.copy_chart_calls("parent", "child", item_count=2)

    assert store.charts_for_conversation("child") == ["natal-chart"]
    assert store.get_conversation("child")["parent_conversation_id"] == "parent"


def test_normalize_sdk_message_items():
    messages = normalize_messages(
        [
            {"role": "user", "content": "问题"},
            {
                "id": "assistant_1",
                "role": "assistant",
                "type": "message",
                "content": [{"type": "output_text", "text": "回答"}],
            },
            {"type": "function_call", "name": "local_tool"},
        ],
        {1: ["ziwei-chart"]},
    )

    assert messages == [
        {"id": "item-0", "item_index": 0, "role": "user", "text": "问题", "charts": []},
        {
            "id": "assistant_1",
            "item_index": 1,
            "role": "assistant",
            "text": "回答",
            "charts": ["ziwei-chart"],
        },
    ]
