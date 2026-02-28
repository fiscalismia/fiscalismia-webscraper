"""Quick test script for the CDP WebSocket streaming endpoints."""

import asyncio
import json
import os
import aiohttp
import websockets
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.environ.get("TEST_BEARER_TOKEN")
if not TOKEN:
  raise RuntimeError("TEST_BEARER_TOKEN not set in .env")
BASE = "http://127.0.0.1:3003/fastapi/fiscalismia/stream"


async def test():
  # 1) Start a new screencast session
  headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
  async with aiohttp.ClientSession() as http:
    async with http.post(f"{BASE}/start", headers=headers, json={"url": "https://example.com"}) as resp:
      result = await resp.json()
      session_id = result["session_id"]
      print(f"Created session: {session_id}")

  # 2) Connect to WebSocket (auth via query param)
  ws_uri = f"ws://127.0.0.1:3003/fastapi/fiscalismia/stream/{session_id}/ws?token={TOKEN}"
  async with websockets.connect(ws_uri) as ws:
    frames_received = 0
    for i in range(3):
      try:
        msg = await asyncio.wait_for(ws.recv(), timeout=10)
      except asyncio.TimeoutError:
        print(f"  No more frames (timeout after {frames_received} frames)")
        break
      data = json.loads(msg)
      msg_type = data.get("type", "unknown")
      if msg_type == "frame":
        frame_data = data.get("data", "")
        frames_received += 1
        print(f"Frame {frames_received}: {len(frame_data)} chars of base64 JPEG")
      else:
        print(f"Message: type={msg_type}")
    if frames_received > 0:
      print(f"WebSocket streaming works! ({frames_received} frame(s) received)")
    else:
      print("ERROR: No frames received")


asyncio.run(test())
