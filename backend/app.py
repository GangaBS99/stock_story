import traceback
import asyncio
import json
from typing import Optional, Dict, List

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import tiktoken

from sample_api import agent
from token_tracker import get_total_tool_tokens, add_tool_tokens
from ws_braodcast import active_connections
from kb_chatbot_integration import handle_knowledge_query

# ─────────────────────────────────────────────────────────────
# App setup
# ─────────────────────────────────────────────────────────────
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────
# Tokenizer
# ─────────────────────────────────────────────────────────────
encoding = tiktoken.encoding_for_model("gpt-4o")

def count_tokens(text: str) -> int:
    return len(encoding.encode(text or ""))

# ─────────────────────────────────────────────────────────────
# In-memory session store
# ─────────────────────────────────────────────────────────────
session_histories: Dict[str, List] = {}

# ─────────────────────────────────────────────────────────────
# Request model
# ─────────────────────────────────────────────────────────────
class MessageRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"

# ─────────────────────────────────────────────────────────────
# Suggestion logic (KEY PART)
# ─────────────────────────────────────────────────────────────
def generate_suggestions(bot_text: str) -> List[str]:
    text = bot_text.lower()

    if "weeks" in text or "specify" in text:
        return [
            "2025-08-01 to 2025-11-30",
            "Last quarter",
            "Previous 3 months"
        ]

    if "proceed" in text or "no data" in text or "not available" in text:
        return [
            "yes, proceed",
            "no, cancel",
          
        ]

    if "analysis" in text or "summary" in text:
        return [
            "Add following week",
            "Remove following week",
            "Show key risks"
        ]

    return []

# ─────────────────────────────────────────────────────────────
# API: Process message
# ─────────────────────────────────────────────────────────────
@app.post("/process_message")
async def handle_agent_request(request: MessageRequest):
    user_message = request.message.strip()
    session_id = request.session_id or "default"

    if not user_message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        history = session_histories.get(session_id, [])

        # Check knowledge base first
        kb_response = handle_knowledge_query(user_message)
        if kb_response:
            return {
                "output": kb_response["answer"],
                "suggestions": ["Tell me more", "Show other companies"],
                "sources": kb_response.get("sources", []),
                "confidence": kb_response.get("confidence", 0),
                "input_tokens": 0,
                "output_tokens": 0
            }

        # Token count (input)
        input_tokens = count_tokens(user_message)

        # Run agent safely (non-blocking)
        result = await asyncio.to_thread(
            agent.run_sync,
            user_message,
            message_history=history
        )

        session_histories[session_id] = result.all_messages()
        output_text = result.output or ""

        # Token count (output)
        output_tokens = count_tokens(output_text)
        add_tool_tokens(input_tokens, output_tokens)

        # Conversation token totals
        total_input_tokens = sum(
            count_tokens(msg.content)
            for msg in session_histories[session_id]
            if getattr(msg, "role", "") == "user"
        )

        total_output_tokens = sum(
            count_tokens(msg.content)
            for msg in session_histories[session_id]
            if getattr(msg, "role", "") == "assistant"
        )

        total_tokens_conversation = total_input_tokens + total_output_tokens

        total_tool_input, total_tool_output = get_total_tool_tokens()

        # Debug log
        print("─────────────────────────────")
        print(f"📨 Session ID: {session_id}")
        print(f"📝 User message: {user_message}")
        print(f"🔢 Input tokens: {input_tokens}")
        print(f"🟢 Output tokens: {output_tokens}")
        print(f"📚 Conversation tokens: {total_tokens_conversation}")
        print(f"🧮 Tool tokens: {total_tool_input + total_tool_output}")
        print("─────────────────────────────")

        # 🔥 Suggestions based on bot reply
        suggestions = generate_suggestions(output_text)

        return {
            "output": output_text,
            "suggestions": suggestions,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_input_tokens_conversation": total_input_tokens,
            "total_output_tokens_conversation": total_output_tokens,
            "total_tokens_this_request": input_tokens + output_tokens,
            "total_tokens_entire_conversation": total_tokens_conversation,
            "total_input_tokens_tools": total_tool_input,
            "total_output_tokens_tools": total_tool_output,
            "total_tokens_tools": total_tool_input + total_tool_output,
        }

    except Exception as e:
        print("❌ Exception in /process_message")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────────────────────────
# WebSocket: summary streaming
# ─────────────────────────────────────────────────────────────
@app.websocket("/ws/summary")
async def websocket_summary_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    print("📡 WebSocket client connected")

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60)
                print("🟢 WebSocket received:", data)
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        print("🔌 WebSocket client disconnected")
    finally:
        if websocket in active_connections:
            active_connections.remove(websocket)
