# WebSocket client for connecting to service providers (WSS)
import asyncio
import ssl
import websockets
import json
from shared.messages import build_message

class ServiceWebSocketClient:
    def __init__(self, endpoint, ssl_cert=None):
        self.endpoint = endpoint

    async def send_message(self, message):
        async with websockets.connect(self.endpoint) as websocket:
            await websocket.send(json.dumps(message))
            async for response in websocket:
                yield json.loads(response)
