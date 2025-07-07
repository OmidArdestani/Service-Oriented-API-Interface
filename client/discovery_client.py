# UDP Discovery for client (Service Repository)
import socket
import json
import threading
import time
from shared import discovery
from shared.discovery import UDP_CLIENT_DISCOVERY_PORT, UDP_SERVICE_DISCOVERY_PORT
from shared.messages import MessageTypes

class ClientDiscovery:
    def __init__(self, client_id, repository):
        self.client_id = client_id
        self.repository = repository
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # Bind to local UDP port for discovery
        local_ip = discovery.get_local_ip()
        self.sock.bind((local_ip, UDP_CLIENT_DISCOVERY_PORT))
        self.running = False

    def send_discovery_request(self):
        """Send discovery requests to all target networks"""
        msg = {
            "discoveryType": MessageTypes.CLIENT_DISCOVERY_REQUEST,
            "clientId": self.client_id,
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }

        # Get all broadcast addresses for multi-network discovery
        broadcast_addresses = discovery.get_broadcast_addresses()
        if not broadcast_addresses:
            broadcast_addresses = ["192.168.255.255"]

        print(f"Sending discovery request.")

        for broadcast_ip in broadcast_addresses:
            try:
                broadcast_addr = (broadcast_ip, UDP_SERVICE_DISCOVERY_PORT)
                self.sock.sendto(json.dumps(msg).encode(), broadcast_addr)
            except Exception as e:
                print(f"Failed to send discovery to {broadcast_ip}: {e}")

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
