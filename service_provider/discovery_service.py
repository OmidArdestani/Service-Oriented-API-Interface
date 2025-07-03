# UDP Discovery for service provider
import socket
import json
import threading
import time
from shared.discovery import UDP_SERVICE_DISCOVERY_PORT, UDP_BROADCAST_IP, HEARTBEAT_INTERVAL_SEC
from shared.messages import MessageTypes

class ServiceDiscoveryBroadcaster:
    def __init__(self, service_info):
        self.service_info = service_info
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('0.0.0.0', UDP_SERVICE_DISCOVERY_PORT))
        self.running = False

    def broadcast(self, addr=None):
        msg = self.service_info.copy()
        msg['discoveryType'] = MessageTypes.SERVICE_ADVERTISEMENT
        msg['timestamp'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        target_addr = addr if addr else (UDP_BROADCAST_IP, UDP_SERVICE_DISCOVERY_PORT)
        self.sock.sendto(json.dumps(msg).encode(), target_addr)

    def listen(self):
        self.running = True
        while self.running:
            try:
                data, sender_addr = self.sock.recvfrom(4096)
                msg = json.loads(data.decode())
                if msg.get('discoveryType') == MessageTypes.CLIENT_DISCOVERY_REQUEST:
                    self.broadcast(addr=sender_addr)
            except Exception as e:
                print(f"Service discovery listen error: {e}")

    def start(self):
        threading.Thread(target=self.listen, daemon=True).start()
        threading.Thread(target=self.periodic_broadcast, daemon=True).start()

    def periodic_broadcast(self):
        while self.running:
            self.broadcast()
            time.sleep(HEARTBEAT_INTERVAL_SEC)

    def stop(self):
        self.running = False
        self.sock.close()
