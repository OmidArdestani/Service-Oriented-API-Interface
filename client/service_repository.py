# Service Repository for discovered services
import threading
import time
from typing import Dict, Any

class ServiceRepository:
    def __init__(self):
        self.services = {}  # serviceId -> service info dict
        self.lock = threading.Lock()

    def update_service(self, service_info: Dict[str, Any]):
        with self.lock:
            sid = service_info['serviceId']
            service_info['lastSeenTimestamp'] = time.time()
            self.services[sid] = service_info

    def get_services(self, service_name=None):
        with self.lock:
            if service_name:
                return [s for s in self.services.values() if s['serviceName'] == service_name and s['status'] == 'Online']
            return list(self.services.values())

    def expire_services(self, expiry_seconds):
        now = time.time()
        with self.lock:
            expired = [sid for sid, s in self.services.items() if now - s['lastSeenTimestamp'] > expiry_seconds]
            for sid in expired:
                del self.services[sid]
