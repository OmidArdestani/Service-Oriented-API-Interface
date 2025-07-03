
from datetime import datetime
import uuid
import abc
from service_provider.discovery_service import ServiceDiscoveryBroadcaster
from service_provider.ws_server import ServiceWebSocketServer

class ServiceProviderBase:
    """
    Base class for service providers.
    This class provides a structure for service providers to implement their capabilities.
    """

    SERVICE_ID      = str(uuid.uuid4())
    SERVICE_NAME    = "Logic Pipeline Test Runner"
    SERVICE_VERSION = "1.0.0"
    PORT            = 8081
    ENDPOINT        = f"localhost:{PORT}"
    CAPABILITIES    = []

    service_info    = {}

    # Store task statuses and results
    task_store      = {}

    def __init__(self, name, version, port, capabilities):
        self.task_store      = {}
        self.SERVICE_NAME    = name
        self.SERVICE_VERSION = version
        self.PORT            = port
        self.CAPABILITIES    = capabilities
        self.ENDPOINT        = f"localhost:{self.PORT}"

        self.service_info = {
        "serviceId": self.SERVICE_ID,
        "serviceName": self.SERVICE_NAME,
        "serviceVersion": self.SERVICE_VERSION,
        "endpoint": self.ENDPOINT,
        "capabilities": self.CAPABILITIES,
        "status": "Online",
        "load": 0.0
    }

    @abc.abstractmethod
    def handle_assign_task(self, task_id, operation, parameters, base_result):
        raise NotImplementedError("Subclasses must implement handle_message method")
    
    def handle_get_status(self, msg, websocket):
        import json
        import asyncio
        payload = msg.get("payload", {})
        task_id = payload.get("taskId")
        task_status = self.task_store.get(task_id, {}).get("status", "Unknown")
        status_resp = {
            "type": "Status",
            "serviceId": self.service_info["serviceId"],
            "serviceName": self.service_info["serviceName"],
            "taskId": task_id,
            "taskStatus": task_status,
            "status": self.service_info["status"],
            "load": self.service_info["load"]
        }
        coro = websocket.send(json.dumps(status_resp))
        if asyncio.iscoroutine(coro):
            return coro
        return None

    def handle_get_result(self, msg, websocket):
        import json
        import asyncio
        payload = msg.get("payload", {})
        task_id = payload.get("taskId")
        result = self.task_store.get(task_id, {}).get("result")
        if result:
            coro = websocket.send(json.dumps(result))
            if asyncio.iscoroutine(coro):
                return coro
        else:
            # No result yet
            no_result = {"type": "TaskResult", "error": "Result not ready"}
            coro = websocket.send(json.dumps(no_result))
            if asyncio.iscoroutine(coro):
                return coro
        return None

    def dummy_service_logic_base(self, msg, websocket):
        import uuid

        payload    = msg.get("payload", {})
        task_id    = payload.get("taskId", str(uuid.uuid4()))
        parameters = payload.get("taskParameters", {})

        # Mark as processing
        base_result = {
            "type": "TaskResult",
            "messageId": msg.get("messageId", "") + "-result",
            "timestamp": datetime.now().isoformat() + "Z",
            "payload": {
                "taskId": task_id,
                "status": "Processing",
                "resultData": {},
                "originalClientId": payload.get("callbackClientId", "")
            }
        }

        if msg.get("type") == "AssignTask":
            operation = payload.get("operation")
            self.task_store[task_id] = {"status": "Processing", "result": None}
            self.CAPABILITIES[operation]["status"] = "Busy"

            self.handle_assign_task(task_id, operation, parameters, base_result)

            return self.handle_get_status(msg, websocket)

        elif msg.get("type") == "GetStatus":
            return self.handle_get_status(msg, websocket)

        elif msg.get("type") == "GetResult":
            return self.handle_get_result(msg, websocket)

        return None


    def run(self):
        broadcaster = ServiceDiscoveryBroadcaster(self.service_info)
        broadcaster.start()
        ws_server = ServiceWebSocketServer('localhost', self.PORT, None, None, self.dummy_service_logic_base)

        import asyncio
        asyncio.get_event_loop().run_until_complete(ws_server.start())
        asyncio.get_event_loop().run_forever()

