# Example main for running a service provider
import uuid
from service_provider.discovery_service import ServiceDiscoveryBroadcaster
from service_provider.ws_server import ServiceWebSocketServer


SERVICE_ID = str(uuid.uuid4())
SERVICE_NAME = "ImageProcessingService"
SERVICE_VERSION = "1.2.0"
ENDPOINT = "127.0.0.1:8080"
CAPABILITIES = [
    {"key": "resizeImage", "settings": [{"string": "inputPath"}, {"string": "output"}, {"int": "width"}, {"int": "height"}]},
    {"key": "applyFilter", "settings": [{"string": "name"}, {"float": "size"}]},
    {"key": "convertFormat", "settings": [{"float": "format"}]}
]

service_info = {
    "serviceId": SERVICE_ID,
    "serviceName": SERVICE_NAME,
    "serviceVersion": SERVICE_VERSION,
    "endpoint": ENDPOINT,
    "capabilities": CAPABILITIES,
    "status": "Online",
    "load": 0.0
}

# Store task statuses and results
task_store = {}

def handle_assign_task(msg, websocket):
    import uuid
    global task_store
    payload = msg.get("payload", {})
    task_id = payload.get("taskId", str(uuid.uuid4()))
    # Mark as processing
    task_store[task_id] = {"status": "Processing", "result": None}
    # Simulate processing (immediate for demo)
    if payload.get("operation") == "resizeImage":
        result = {
            "type": "TaskResult",
            "messageId": msg.get("messageId", "") + "-result",
            "timestamp": "2025-07-02T12:00:00Z",
            "payload": {
                "taskId": task_id,
                "status": "Completed",
                "resultData": {
                    "outputImagePath": payload.get("taskParameters", {}).get("outputPath", "output.jpg"),
                    "processedByServiceId": service_info["serviceId"],
                    "executionDurationMs": 1234
                },
                "originalClientId": payload.get("callbackClientId", "")
            }
        }
        # Store result and mark as done
        task_store[task_id]["result"] = result
        task_store[task_id]["status"] = "Done"

def handle_get_status(msg, websocket):
    import json
    import asyncio
    payload = msg.get("payload", {})
    task_id = payload.get("taskId")
    task_status = task_store.get(task_id, {}).get("status", "Unknown")
    status_resp = {
        "type": "Status",
        "serviceId": service_info["serviceId"],
        "serviceName": service_info["serviceName"],
        "taskId": task_id,
        "taskStatus": task_status,
        "status": service_info["status"],
        "load": service_info["load"]
    }
    coro = websocket.send(json.dumps(status_resp))
    if asyncio.iscoroutine(coro):
        return coro
    return None

def handle_get_result(msg, websocket):
    import json
    import asyncio
    payload = msg.get("payload", {})
    task_id = payload.get("taskId")
    result = task_store.get(task_id, {}).get("result")
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

def dummy_service_logic(msg, websocket):
    import asyncio
    if msg.get("type") == "AssignTask":
        asyncio.get_event_loop().call_later(10, handle_assign_task, msg, websocket)

        return handle_get_status(msg, websocket)

    elif msg.get("type") == "GetStatus":
        return handle_get_status(msg, websocket)

    elif msg.get("type") == "GetResult":
        return handle_get_result(msg, websocket)

    return None

def main():
    broadcaster = ServiceDiscoveryBroadcaster(service_info)
    broadcaster.start()
    ws_server = ServiceWebSocketServer('0.0.0.0', 8080, None, None, dummy_service_logic)
    
    import asyncio
    asyncio.get_event_loop().run_until_complete(ws_server.start())
    asyncio.get_event_loop().run_forever()

if __name__ == "__main__":
    main()
