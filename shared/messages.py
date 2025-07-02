# Shared message types and utilities for Service-Oriented API Interface
import uuid
from datetime import datetime
from typing import Any, Dict


def generate_uuid() -> str:
    return str(uuid.uuid4())


def iso_timestamp() -> str:
    return datetime.utcnow().isoformat() + 'Z'


# Message format helpers
class MessageTypes:
    ASSIGN_TASK = "AssignTask"
    CANCEL_TASK = "CancelTask"
    TASK_STATUS_UPDATE = "TaskStatusUpdate"
    TASK_RESULT = "TaskResult"
    TASK_FAILED = "TaskFailed"
    ACK = "Ack"
    CLIENT_DISCOVERY_REQUEST = "ClientServiceDiscoveryRequest"
    SERVICE_ADVERTISEMENT = "ServiceAdvertisement"


def build_message(msg_type: str, payload: Dict[str, Any], message_id: str = None, timestamp: str = None) -> Dict[str, Any]:
    return {
        "type": msg_type,
        "messageId": message_id or generate_uuid(),
        "timestamp": timestamp or iso_timestamp(),
        "payload": payload
    }
