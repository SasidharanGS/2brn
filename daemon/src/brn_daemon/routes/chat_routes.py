import asyncio
import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from brn_daemon.context import AppContext, get_context

logger = logging.getLogger(__name__)

router = APIRouter()

class ChatRequest(BaseModel):
    question: str
    date_filter: str | None = None
    # multi-select category scope; category_filter (singular) kept for back-compat
    category_filters: list[str] | None = None
    category_filter: str | None = None

@router.post("/chat")
async def chat_endpoint(body: ChatRequest, ctx: AppContext = Depends(get_context)):
    service = ctx.chat_service
    if not service:
        async def error_stream():
            yield "data: " + json.dumps({"chunk": "Chat service unavailable."}) + "\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    categories = body.category_filters or ([body.category_filter] if body.category_filter else None)

    async def event_stream():
        try:
            async for chunk in service.chat(
                question=body.question,
                date_filter=body.date_filter,
                categories=categories,
            ):
                yield "data: " + json.dumps({"chunk": chunk}) + "\n\n"
            yield "data: [DONE]\n\n"
        except asyncio.CancelledError:
            logger.debug("Chat SSE client disconnected")
            return
        except RuntimeError as exc:
            logger.exception("Chat stream error")
            yield "data: " + json.dumps({"error": str(exc)}) + "\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            logger.exception("Chat stream error")
            yield "data: " + json.dumps({"chunk": f"Error: {exc}"}) + "\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
