import asyncio
import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

from backend.agents.orchestrator import build_graph, get_checkpointer
from backend.mcp_server.tools.memory_tools import (
    mcp_memory_write, mcp_intent_log, mcp_response_logger,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    response: str
    intent: str
    citations: list
    has_model_output: bool


@router.post("/")
async def chat(request: ChatRequest):
    """
    Process a chat message through the orchestrator graph.
    Returns the full response (non-streaming).
    """
    session_id = request.session_id or str(uuid.uuid4())

    # Build graph with checkpointer for conversation persistence
    try:
        checkpointer = get_checkpointer()
        graph = build_graph(checkpointer=checkpointer)
    except Exception:
        # Fallback without checkpointer if Redis is unavailable
        graph = build_graph(checkpointer=None)

    config = {"configurable": {"thread_id": session_id}}

    # Invoke the graph (run sync call in thread to avoid blocking the event loop)
    result = await asyncio.to_thread(
        graph.invoke,
        {
            "messages": [HumanMessage(content=request.message)],
            "current_query": request.message,
            "session_id": session_id,
            "intent": "",
            "retrieved_chunks": [],
            "formatted_context": "",
            "model_output": {},
            "response": "",
            "citations": [],
        },
        config,
    )

    response_text = result.get("response", "I could not generate a response.")
    intent = result.get("intent", "general_chat")
    citations = result.get("citations", [])
    model_output = result.get("model_output", {})

    # Log to audit trail
    try:
        mcp_memory_write(session_id, {"role": "user", "content": request.message})
        mcp_memory_write(session_id, {"role": "assistant", "content": response_text})
        mcp_intent_log(session_id, intent, request.message)
        mcp_response_logger(session_id, request.message, response_text, citations)
    except Exception:
        pass  # Don't fail the response if logging fails

    return ChatResponse(
        session_id=session_id,
        response=response_text,
        intent=intent,
        citations=citations,
        has_model_output=bool(model_output),
    )


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """
    Process a chat message and stream the response via SSE.
    Uses Server-Sent Events for real-time token streaming.
    """
    session_id = request.session_id or str(uuid.uuid4())

    async def event_generator():
        try:
            # Send session ID first
            yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"

            # Build graph
            try:
                checkpointer = get_checkpointer()
                graph = build_graph(checkpointer=checkpointer)
            except Exception:
                graph = build_graph(checkpointer=None)

            config = {"configurable": {"thread_id": session_id}}

            # Stream through the graph nodes
            intent_sent = False
            full_response = ""
            citations = []

            for event in graph.stream(
                {
                    "messages": [HumanMessage(content=request.message)],
                    "current_query": request.message,
                    "session_id": session_id,
                    "intent": "",
                    "retrieved_chunks": [],
                    "formatted_context": "",
                    "model_output": {},
                    "response": "",
                    "citations": [],
                },
                config=config,
                stream_mode="updates",
            ):
                for node_name, node_output in event.items():
                    # Send intent classification
                    if "intent" in node_output and not intent_sent:
                        yield f"data: {json.dumps({'type': 'intent', 'intent': node_output['intent']})}\n\n"
                        intent_sent = True

                    # Send retrieval status
                    if "retrieved_chunks" in node_output:
                        chunk_count = len(node_output.get("retrieved_chunks", []))
                        yield f"data: {json.dumps({'type': 'retrieval', 'chunk_count': chunk_count})}\n\n"

                    # Send model output notification
                    if "model_output" in node_output and node_output["model_output"]:
                        yield f"data: {json.dumps({'type': 'model_output', 'has_output': True})}\n\n"

                    # Send the response
                    if "response" in node_output and node_output["response"]:
                        full_response = node_output["response"]
                        citations = node_output.get("citations", [])
                        yield f"data: {json.dumps({'type': 'response', 'content': full_response})}\n\n"

            # Send completion signal
            yield f"data: {json.dumps({'type': 'done', 'citations': citations})}\n\n"

            # Log to audit trail
            try:
                mcp_memory_write(session_id, {"role": "user", "content": request.message})
                mcp_memory_write(session_id, {"role": "assistant", "content": full_response})
                mcp_intent_log(session_id, "", request.message)
                mcp_response_logger(session_id, request.message, full_response, citations)
            except Exception:
                pass

        except Exception as e:
            logger.exception("Error in chat stream")
            yield f"data: {json.dumps({'type': 'error', 'message': 'An internal error occurred. Please try again.'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
