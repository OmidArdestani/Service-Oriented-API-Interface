# WebSocket client for connecting to service providers (WSS)
import asyncio
import ssl
import websockets
import json
from shared.messages import build_message

class ServiceWebSocketClient:
    def __init__(self, endpoint, ssl_cert=None):
        self.endpoint = endpoint

    async def send_message_async(self, message):
        async with websockets.connect(self.endpoint) as websocket:
            await websocket.send(json.dumps(message))
            async for response in websocket:
                yield json.loads(response)

    def send_message(self, message):
        async def run():
            status_result = self.send_message_async(message)
            async for resp in status_result:
                return resp
        
        loop = asyncio.new_event_loop()
        resp = loop.run_until_complete(run())

        return resp