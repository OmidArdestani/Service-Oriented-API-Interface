# WebSocket server for service provider (WSS)
import asyncio
import websockets
import json
from shared.messages import MessageTypes, build_message

class ServiceWebSocketServer:
    def __init__(self, host, port, ssl_cert, ssl_key, service_logic):
        self.host = host
        self.port = port
        self.service_logic = service_logic
        if ssl_cert and ssl_key:
            import ssl
            self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            self.ssl_context.load_cert_chain(certfile=ssl_cert, keyfile=ssl_key)
        else:
            self.ssl_context = None

    async def handler(self, websocket, path):
        async for message in websocket:
            try:
                msg = json.loads(message)
                response = await self.service_logic(msg, websocket)
                if response:
                    await websocket.send(json.dumps(response))
            except Exception as e:
                print(f"WebSocket error: {e}")

    def start(self):
        if self.ssl_context:
            return websockets.serve(self.handler, self.host, self.port, ssl=self.ssl_context)
        else:
            return websockets.serve(self.handler, self.host, self.port)
