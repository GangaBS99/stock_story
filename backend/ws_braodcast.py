# ws_braodcast.py
from typing import List
import json
from fastapi import WebSocket

active_connections: List[WebSocket] = []

async def broadcast_summary(summary_result):
    summary_data = {
        "type": "summary",
        "date_range": summary_result.date_range,
        "summary": summary_result.summary
    }

    for ws in active_connections[:]:  # Iterate over a copy
        try:
            await ws.send_text(json.dumps(summary_data))
        except Exception as e:
            print(f"❌ Failed to send summary: {e}")
            try:
                await ws.close()
            except:
                pass
            if ws in active_connections:
                active_connections.remove(ws)
