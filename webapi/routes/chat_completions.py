"""OpenAI-compatible /v1/chat/completions endpoint.

This stub satisfies the workspace capability probe and forwards
real requests to the session-based chat endpoint.
"""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from hermes_state import SessionDB
from webapi.deps import create_agent, get_session_db, get_runtime_model


router = APIRouter(prefix="/v1", tags=["openai-compat"])


class ChatCompletionMessage(BaseModel):
    role: str = "user"
    content: str = ""


class ChatCompletionRequest(BaseModel):
    model: str | None = None
    messages: list[ChatCompletionMessage] = Field(default_factory=list)
    max_tokens: int | None = None
    temperature: float | None = None
    stream: bool = False


@router.options("/chat/completions")
async def chat_completions_options() -> JSONResponse:
    return JSONResponse(
        content={"status": "ok"},
        headers={
            "Allow": "POST, OPTIONS",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
        },
    )


@router.post("/chat/completions")
async def chat_completions(
    payload: ChatCompletionRequest,
    session_db: Annotated[SessionDB, Depends(get_session_db)],
) -> JSONResponse:
    if not payload.messages:
        raise HTTPException(status_code=400, detail="messages is required")

    user_message = ""
    for msg in reversed(payload.messages):
        if msg.role == "user":
            user_message = msg.content
            break

    if not user_message:
        raise HTTPException(status_code=400, detail="no user message found")

    session_id = str(uuid.uuid4())
    session_db.create_session(session_id, title="API Chat")

    agent = create_agent(
        session_id=session_id,
        session_db=session_db,
        model=payload.model,
    )

    result = await run_in_threadpool(
        agent.run_conversation,
        user_message,
        conversation_history=[],
    )

    response_text = result.get("final_response", "")

    return JSONResponse(content={
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "model": payload.model or get_runtime_model(),
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    })
