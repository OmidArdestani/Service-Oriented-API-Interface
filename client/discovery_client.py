# UDP Discovery for client (Service Repository)
import socket
import json
import threading
import time
from shared.discovery import UDP_CLIENT_DISCOVERY_PORT, UDP_SERVICE_DISCOVERY_PORT, UDP_BROADCAST_IP, HEARTBEAT_INTERVAL_SEC
from shared.messages import MessageTypes, build_message

class ClientDiscovery:
    def __init__(self, client_id, repository):
        self.client_id = client_id
        self.repository = repository
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.bind(('', UDP_CLIENT_DISCOVERY_PORT))
        self.running = False

    def send_discovery_request(self):
        msg = {
            "discoveryType": MessageTypes.CLIENT_DISCOVERY_REQUEST,
            "clientId": self.client_id,
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }
        self.sock.sendto(json.dumps(msg).encode(), (UDP_BROADCAST_IP, UDP_SERVICE_DISCOVERY_PORT))

    def listen(self):
        self.running = True
        while self.running:
            try:
                data, _ = self.sock.recvfrom(4096)
                msg = json.loads(data.decode())
                if msg.get('discoveryType') == MessageTypes.SERVICE_ADVERTISEMENT:
                    self.repository.update_service(msg)
            except Exception as e:
                print(f"Discovery listen error: {e}")

    def start(self):
        threading.Thread(target=self.listen, daemon=True).start()
        self.send_discovery_request()
        threading.Thread(target=self.periodic_discovery, daemon=True).start()

    def periodic_discovery(self):
        while self.running:
            self.send_discovery_request()
            time.sleep(300)  # every 5 minutes

    def stop(self):
        self.running = False
        self.sock.close()
