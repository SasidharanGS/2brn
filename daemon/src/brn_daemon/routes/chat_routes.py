import asyncio
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

class ChatRequest(BaseModel):
    question: str
    date_filter: str | None = None
    category_filter: str | None = None

@router.post("/chat")
async def chat_endpoint(body: ChatRequest):
    from brn_daemon.main import app_state
    service = app_state.get("chat_service")
    if not service:
        async def error_stream():
            yield "data: " + json.dumps({"chunk": "Chat service unavailable."}) + "\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    async def event_stream():
        try:
            async for chunk in service.chat(
                question=body.question,
                date_filter=body.date_filter,
                category_filter=body.category_filter,
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
