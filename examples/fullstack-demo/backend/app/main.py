from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, AsyncIterator

import httpx
from agents import Runner
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from openai.types.responses import ResponseTextDeltaEvent
from pydantic import BaseModel, Field

from iztro_agents import ChatSession, IztroToolEvent, iztro_ziwei_agent, list_user_conversations

from .store import MetadataStore


BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")

# Quick local setup: paste a test key here. Restore the placeholder before committing.
INLINE_ZIWEI_API_KEY = "sk_ziwei_replace_me"
API_KEY = (
    INLINE_ZIWEI_API_KEY
    if INLINE_ZIWEI_API_KEY != "sk_ziwei_replace_me"
    else os.getenv("ZIWEI_API_KEY", "")
)
BASE_URL = os.getenv("ZIWEI_BASE_URL")
DATABASE_PATH = Path(
    os.getenv("DEMO_DATABASE_PATH", str(BACKEND_DIR / "data" / "demo.sqlite3"))
)
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "DEMO_CORS_ORIGINS",
        "http://localhost:5192,http://127.0.0.1:5192",
    ).split(",")
    if origin.strip()
]

store = MetadataStore(DATABASE_PATH)
app = FastAPI(title="Iztro Agents ChatSession Full-Stack Demo")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateConversationRequest(BaseModel):
    external_user_id: str = Field(min_length=1, max_length=128)
    title: str = Field(default="新会话", max_length=80)


class RenameConversationRequest(BaseModel):
    external_user_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=80)


class ForkConversationRequest(BaseModel):
    external_user_id: str = Field(min_length=1, max_length=128)
    item_count: int | None = Field(default=None, ge=0)
    title: str | None = Field(default=None, max_length=80)


class StreamMessageRequest(BaseModel):
    external_user_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=20_000)


def _clean(value: str) -> str:
    return " ".join(value.split())


def _require_api_key() -> None:
    if not API_KEY or API_KEY == "sk_ziwei_replace_me":
        raise HTTPException(
            status_code=503,
            detail="请先在 backend/.env 中配置 ZIWEI_API_KEY。",
        )


def _session(
    *,
    conversation_id: str | None = None,
    external_user_id: str | None = None,
) -> ChatSession:
    _require_api_key()
    return ChatSession(
        conversation_id=conversation_id,
        external_user_id=external_user_id,
        api_key=API_KEY,
        base_url=BASE_URL,
    )


def _agent():
    _require_api_key()
    return iztro_ziwei_agent(
        api_key=API_KEY,
        base_url=BASE_URL,
        instructions=(
            "你是一位清晰、可靠的紫微斗数助手。需要命盘时先确认出生日期、时辰和性别；"
            "说明判断依据，避免绝对化结论，并用简洁中文给出可行动的建议。"
        ),
    )


def _text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for part in content:
        if isinstance(part, str):
            parts.append(part)
            continue
        if not isinstance(part, dict):
            continue
        text = part.get("text")
        if isinstance(text, str):
            parts.append(text)
        elif isinstance(text, dict) and isinstance(text.get("value"), str):
            parts.append(text["value"])
    return "".join(parts)


def normalize_messages(
    items: list[dict[str, Any]],
    charts_by_item: dict[int, list[str]] | None = None,
) -> list[dict[str, Any]]:
    """Convert SDK response-input items into a small browser-friendly shape."""
    charts_by_item = charts_by_item or {}
    messages: list[dict[str, Any]] = []
    for item_index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        if role not in {"user", "assistant", "system"}:
            continue
        text = _text_from_content(item.get("content"))
        if not text:
            continue
        messages.append(
            {
                "id": str(item.get("id") or f"item-{item_index}"),
                "item_index": item_index,
                "role": role,
                "text": text,
                "charts": charts_by_item.get(item_index, []),
            }
        )
    return messages


def _summary(metadata: dict[str, Any]) -> dict[str, Any]:
    result = dict(metadata)
    result["charts"] = store.charts_for_conversation(metadata["conversation_id"])
    return result


async def _ensure_owned(conversation_id: str, external_user_id: str) -> dict[str, Any]:
    _require_api_key()
    metadata = store.get_conversation(conversation_id)
    if metadata:
        if metadata["external_user_id"] != external_user_id:
            raise HTTPException(status_code=404, detail="会话不存在。")
        return metadata

    remote_items = await list_user_conversations(
        external_user_id,
        api_key=API_KEY,
        base_url=BASE_URL,
        limit=100,
    )
    match = next(
        (
            item
            for item in remote_items
            if str(item.get("conversation_id") or item.get("id")) == conversation_id
        ),
        None,
    )
    if not match:
        raise HTTPException(status_code=404, detail="会话不存在。")
    return store.ensure_conversation(conversation_id, external_user_id)


def _sse(event: str, payload: Any) -> bytes:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {body}\n\n".encode("utf-8")


def _stream_response(events: AsyncIterator[bytes]) -> StreamingResponse:
    return StreamingResponse(
        events,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_turn(
    session: ChatSession,
    conversation_id: str,
    message: str,
) -> AsyncIterator[bytes]:
    tools: list[str] = []
    try:
        metadata = store.get_conversation(conversation_id)
        if metadata:
            yield _sse("conversation", _summary(metadata))

        streamed = Runner.run_streamed(_agent(), message, session=session)
        async for event in streamed.stream_events():
            if event.type != "raw_response_event":
                continue
            if isinstance(event.data, IztroToolEvent):
                new_tools = [tool for tool in event.data.tools if tool not in tools]
                if new_tools:
                    tools.extend(new_tools)
                    yield _sse("chart", {"tools": new_tools})
            elif isinstance(event.data, ResponseTextDeltaEvent) and event.data.delta:
                yield _sse("delta", {"delta": event.data.delta})

        items = await session.get_items()
        assistant_index = next(
            (
                index
                for index in range(len(items) - 1, -1, -1)
                if isinstance(items[index], dict) and items[index].get("role") == "assistant"
            ),
            max(len(items) - 1, 0),
        )
        store.record_chart_calls(conversation_id, assistant_index, tools)
        store.title_from_first_message(conversation_id, message)
        final_output = streamed.final_output if isinstance(streamed.final_output, str) else ""
        store.update_activity(
            conversation_id,
            last_message=final_output[:160],
            item_count=len(items),
        )
        yield _sse(
            "done",
            {
                "conversation_id": conversation_id,
                "text": final_output,
                "charts": tools,
                "item_count": len(items),
            },
        )
    except asyncio.CancelledError:
        raise
    except Exception as error:
        yield _sse("error", {"message": _error_message(error)})
    finally:
        await session.close()


def _error_message(error: Exception) -> str:
    if isinstance(error, HTTPException):
        return str(error.detail)
    if isinstance(error, httpx.HTTPStatusError):
        try:
            data = error.response.json()
            if isinstance(data, dict):
                return str(data.get("detail") or data.get("error") or data)
        except ValueError:
            pass
        return error.response.text or str(error)
    return str(error) or "请求失败。"


@app.exception_handler(httpx.HTTPStatusError)
async def httpx_status_error_handler(_request: Request, error: httpx.HTTPStatusError):
    return JSONResponse(
        status_code=error.response.status_code,
        content={"detail": _error_message(error)},
    )


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "ok": True,
        "configured": bool(API_KEY and API_KEY != "sk_ziwei_replace_me"),
        "iztro_api_base_url": BASE_URL or "https://chat-api.iztro.com",
    }


@app.get("/api/conversations")
async def conversations(
    external_user_id: str = Query(min_length=1, max_length=128),
) -> dict[str, Any]:
    _require_api_key()
    remote_items = await list_user_conversations(
        external_user_id,
        api_key=API_KEY,
        base_url=BASE_URL,
        limit=100,
    )
    remote_ids: set[str] = set()
    for item in remote_items:
        conversation_id = str(item.get("conversation_id") or item.get("id") or "")
        if not conversation_id:
            continue
        remote_ids.add(conversation_id)
        store.ensure_conversation(conversation_id, external_user_id)

    items = [
        _summary(metadata)
        for metadata in store.list_conversations(external_user_id)
        if metadata["conversation_id"] in remote_ids
    ]
    return {"items": items}


@app.post("/api/conversations", status_code=201)
async def create_conversation(request: CreateConversationRequest) -> dict[str, Any]:
    external_user_id = _clean(request.external_user_id)
    title = _clean(request.title) or "新会话"
    session = _session(external_user_id=external_user_id)
    try:
        await session.get_items()
        metadata = store.ensure_conversation(
            session.session_id,
            external_user_id,
            title=title,
        )
        return _summary(metadata)
    finally:
        await session.close()


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    external_user_id: str = Query(min_length=1, max_length=128),
) -> dict[str, Any]:
    metadata = await _ensure_owned(conversation_id, external_user_id)
    session = _session(conversation_id=conversation_id, external_user_id=external_user_id)
    try:
        items = await session.get_items()
    finally:
        await session.close()
    messages = normalize_messages(items, store.charts_by_item(conversation_id))
    store.update_activity(conversation_id, item_count=len(items))
    refreshed = store.get_conversation(conversation_id) or metadata
    return {**_summary(refreshed), "messages": messages}


@app.patch("/api/conversations/{conversation_id}")
async def rename_conversation(
    conversation_id: str,
    request: RenameConversationRequest,
) -> dict[str, Any]:
    await _ensure_owned(conversation_id, request.external_user_id)
    title = _clean(request.title)
    if not title:
        raise HTTPException(status_code=400, detail="标题不能为空。")
    store.rename_conversation(conversation_id, title)
    return _summary(store.get_conversation(conversation_id) or {})


@app.delete("/api/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    external_user_id: str = Query(min_length=1, max_length=128),
) -> None:
    await _ensure_owned(conversation_id, external_user_id)
    session = _session(conversation_id=conversation_id, external_user_id=external_user_id)
    try:
        await session.clear_session()
    finally:
        await session.close()
    store.delete_conversation(conversation_id)


@app.post("/api/conversations/{conversation_id}/fork", status_code=201)
async def fork_conversation(
    conversation_id: str,
    request: ForkConversationRequest,
) -> dict[str, Any]:
    parent = await _ensure_owned(conversation_id, request.external_user_id)
    source = _session(conversation_id=conversation_id, external_user_id=request.external_user_id)
    forked: ChatSession | None = None
    try:
        source_items = await source.get_items()
        item_count = len(source_items) if request.item_count is None else request.item_count
        if item_count > len(source_items):
            raise HTTPException(status_code=400, detail="分支位置超出会话长度。")
        forked = await source.fork(
            item_count=item_count,
            external_user_id=request.external_user_id,
        )
        title = _clean(request.title or "") or f"{parent['title']} · 分支"
        metadata = store.ensure_conversation(
            forked.session_id,
            request.external_user_id,
            title=title[:80],
            parent_conversation_id=conversation_id,
            forked_at_item=item_count,
        )
        copied_messages = normalize_messages(source_items[:item_count])
        last_message = copied_messages[-1]["text"][:160] if copied_messages else ""
        store.update_activity(
            forked.session_id,
            last_message=last_message,
            item_count=item_count,
        )
        store.copy_chart_calls(
            conversation_id,
            forked.session_id,
            item_count=item_count,
        )
        return _summary(metadata)
    finally:
        await source.close()
        if forked is not None:
            await forked.close()


@app.post("/api/conversations/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: str,
    request: StreamMessageRequest,
) -> StreamingResponse:
    await _ensure_owned(conversation_id, request.external_user_id)
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="消息不能为空。")
    session = _session(conversation_id=conversation_id, external_user_id=request.external_user_id)
    return _stream_response(_stream_turn(session, conversation_id, message))


@app.post("/api/conversations/{conversation_id}/messages/{item_index}/edit/stream")
async def edit_message(
    conversation_id: str,
    item_index: int,
    request: StreamMessageRequest,
) -> StreamingResponse:
    parent = await _ensure_owned(conversation_id, request.external_user_id)
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="消息不能为空。")

    source = _session(conversation_id=conversation_id, external_user_id=request.external_user_id)
    forked: ChatSession | None = None
    try:
        items = await source.get_items()
        if item_index < 0 or item_index >= len(items):
            raise HTTPException(status_code=404, detail="要编辑的消息不存在。")
        item = items[item_index]
        if not isinstance(item, dict) or item.get("role") != "user":
            raise HTTPException(status_code=400, detail="只能编辑用户消息。")

        forked = await source.fork(
            item_count=item_index,
            external_user_id=request.external_user_id,
        )
        store.ensure_conversation(
            forked.session_id,
            request.external_user_id,
            title=f"{parent['title']} · 编辑分支"[:80],
            parent_conversation_id=conversation_id,
            forked_at_item=item_index,
        )
        store.copy_chart_calls(
            conversation_id,
            forked.session_id,
            item_count=item_index,
        )
        stream = _stream_turn(forked, forked.session_id, message)
        forked = None  # ownership is transferred to the streaming generator
        return _stream_response(stream)
    finally:
        await source.close()
        if forked is not None:
            await forked.close()
