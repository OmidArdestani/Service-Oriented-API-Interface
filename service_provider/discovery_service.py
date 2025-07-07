# UDP Discovery for service provider with multi-provider support
import socket
import json
import threading
import time
import random
from shared.discovery import UDP_SERVICE_DISCOVERY_PORT, HEARTBEAT_INTERVAL_SEC
from shared.messages import MessageTypes

class ServiceDiscoveryBroadcaster:
    def __init__(self, service_info):
        self.service_info = service_info
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.running = False
        self.is_primary = False
        self.registered_providers = {}  # For primary provider: {provider_id: {info, last_heartbeat}}
        self.primary_provider_addr = None  # For secondary providers
        self.provider_id = f"provider_{int(time.time())}_{random.randint(1000, 9999)}"

        try:
            self.sock.bind(('0.0.0.0', UDP_SERVICE_DISCOVERY_PORT))
            self.is_primary = True
            print(f"Primary provider {self.provider_id} bound to discovery port")
        except OSError as e:
            print(f"Could not bind to discovery port: {e}")
            print(f"Attempting to register as secondary provider {self.provider_id}")
            self._setup_as_secondary()

    def _setup_as_secondary(self):
        """Setup this provider as a secondary provider that registers with the primary"""
        # Create a new socket for secondary provider communication
        self.secondary_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.secondary_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        # Try to find and register with primary provider
        self._find_and_register_with_primary()

    def broadcast(self, target_addr=None):
        msg = self.service_info.copy()
        msg['discoveryType'] = MessageTypes.SERVICE_ADVERTISEMENT
        msg['providerId'] = self.provider_id
        msg['timestamp'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

        # Use appropriate socket based on provider type
        sock_to_use = self.sock if self.is_primary else self.secondary_sock
        sock_to_use.sendto(json.dumps(msg).encode(), target_addr)

    def listen(self):
        """Listen for discovery messages - different behavior for primary vs secondary"""
        self.running = True

        if self.is_primary:
            self._listen_as_primary()
        else:
            self._listen_as_secondary()

    def _listen_as_primary(self):
        """Primary provider listens for client requests and provider registrations"""
        while self.running:
            try:
                data, sender_addr = self.sock.recvfrom(4096)
                msg = json.loads(data.decode())
                msg_type = msg.get('discoveryType')

                if msg_type == MessageTypes.CLIENT_DISCOVERY_REQUEST:
                    # Respond for self
                    self.broadcast(target_addr=sender_addr)
                    # Notify registered providers
                    self._notify_registered_providers(sender_addr)

                elif msg_type == MessageTypes.PROVIDER_DISCOVERY_REQUEST:
                    # Respond to provider discovery request
                    response = {
                        'discoveryType': MessageTypes.PROVIDER_DISCOVERY_RESPONSE,
                        'providerId': self.provider_id,
                        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                    }
                    self.sock.sendto(json.dumps(response).encode(), sender_addr)

                elif msg_type == MessageTypes.PROVIDER_REGISTRATION:
                    # Register a secondary provider
                    provider_id = msg.get('providerId')
                    if provider_id:
                        self.registered_providers[provider_id] = {
                            'info': msg.get('serviceInfo', {}),
                            'addr': sender_addr,
                            'last_heartbeat': time.time()
                        }
                        print(f"Registered provider {provider_id} from {sender_addr}")

                elif msg_type == MessageTypes.PROVIDER_HEARTBEAT:
                    # Update heartbeat for registered provider
                    provider_id = msg.get('providerId')
                    if provider_id in self.registered_providers:
                        self.registered_providers[provider_id]['last_heartbeat'] = time.time()

            except Exception as e:
                if self.running:  # Only log if we're supposed to be running
                    print(f"Primary provider listen error: {e}")
    
    def _listen_as_secondary(self):
        """Secondary provider listens for notifications from primary"""
        while self.running:
            try:
                self.secondary_sock.settimeout(1.0)  # Short timeout to check running status
                data, sender_addr = self.secondary_sock.recvfrom(4096)
                msg = json.loads(data.decode())
                
                if msg.get('discoveryType') == MessageTypes.PROVIDER_NOTIFICATION:
                    # Primary is notifying us of a client discovery request
                    client_addr = tuple(msg.get('clientAddr', []))
                    if client_addr:
                        self.broadcast(target_addr=client_addr)

            except socket.timeout:
                continue  # Normal timeout, check if still running
            except Exception as e:
                if self.running:
                    print(f"Secondary provider listen error: {e}")

    def _notify_registered_providers(self, client_addr):
        """Notify all registered providers of a client discovery request"""
        notification = {
            'discoveryType': MessageTypes.PROVIDER_NOTIFICATION,
            'clientAddr': list(client_addr),
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }

        # Clean up stale providers (no heartbeat for 60 seconds)
        current_time = time.time()
        stale_providers = [
            pid for pid, info in self.registered_providers.items()
            if current_time - info['last_heartbeat'] > 60
        ]
        for pid in stale_providers:
            print(f"Removing stale provider {pid}")
            del self.registered_providers[pid]

        # Notify active providers
        for provider_id, provider_info in self.registered_providers.items():
            try:
                self.sock.sendto(
                    json.dumps(notification).encode(),
                    provider_info['addr']
                )
            except Exception as e:
                print(f"Error notifying provider {provider_id}: {e}")

    def start(self):
        """Start the discovery service"""
        threading.Thread(target=self.listen, daemon=True).start()
        # threading.Thread(target=self.periodic_broadcast, daemon=True).start()

        # Secondary providers need to send heartbeats
        if not self.is_primary:
            threading.Thread(target=self._send_heartbeats, daemon=True).start()

    # def periodic_broadcast(self):
    #     """Periodic broadcast - only for primary provider or when no primary found"""
    #     while self.running:
    #         if self.is_primary:
    #             self.broadcast()
    #         # Secondary providers don't do periodic broadcasts to avoid spam
    #         time.sleep(HEARTBEAT_INTERVAL_SEC)

    def _send_heartbeats(self):
        """Send heartbeats to primary provider (secondary providers only)"""
        while self.running and not self.is_primary and self.primary_provider_addr:
            try:
                heartbeat = {
                    'discoveryType': MessageTypes.PROVIDER_HEARTBEAT,
                    'providerId': self.provider_id,
                    'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                }
                self.secondary_sock.sendto(
                    json.dumps(heartbeat).encode(),
                    self.primary_provider_addr
                )
                time.sleep(30)  # Send heartbeat every 30 seconds
            except Exception as e:
                print(f"Error sending heartbeat: {e}")
                time.sleep(30)

    def stop(self):
        """Stop the discovery service and clean up"""
        self.running = False

        # If this is a secondary provider, unregister from primary
        if not self.is_primary and self.primary_provider_addr:
            try:
                unregister_msg = {
                    'discoveryType': 'ProviderUnregistration',
                    'providerId': self.provider_id,
                    'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                }
                self.secondary_sock.sendto(
                    json.dumps(unregister_msg).encode(),
                    self.primary_provider_addr
                )
            except Exception as e:
                print(f"Error unregistering from primary: {e}")

        # Close sockets
        try:
            self.sock.close()
        except:
            pass

        if hasattr(self, 'secondary_sock'):
            try:
                self.secondary_sock.close()
            except:
                pass

    def get_status(self):
        """Get status information about this discovery service"""
        status = {
            'provider_id': self.provider_id,
            'is_primary': self.is_primary,
            'running': self.running,
            'service_info': self.service_info
        }

        if self.is_primary:
            status['registered_providers'] = len(self.registered_providers)
            status['provider_list'] = list(self.registered_providers.keys())
        else:
            status['primary_provider_addr'] = self.primary_provider_addr

        return status

    def _find_and_register_with_primary(self):
        """Find the primary provider and register with it"""
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # Send provider discovery request
                discovery_msg = {
                    'discoveryType': MessageTypes.PROVIDER_DISCOVERY_REQUEST,
                    'providerId': self.provider_id,
                    'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                }

                self.secondary_sock.sendto(
                    json.dumps(discovery_msg).encode(), 
                    ('127.0.0.1', UDP_SERVICE_DISCOVERY_PORT)
                )

                # Wait for response
                self.secondary_sock.settimeout(2.0)  # 2 second timeout
                data, addr = self.secondary_sock.recvfrom(4096)
                msg = json.loads(data.decode())

                if msg.get('discoveryType') == MessageTypes.PROVIDER_DISCOVERY_RESPONSE:
                    self.primary_provider_addr = addr
                    print(f"Found primary provider at {addr}")
                    self._register_with_primary()
                    return

            except socket.timeout:
                print(f"Attempt {attempt + 1}: No primary provider found, retrying...")
                time.sleep(1)
            except Exception as e:
                print(f"Error finding primary provider: {e}")

        print("Could not find primary provider. This service will not be discoverable.")

    def _register_with_primary(self):
        """Register this provider with the primary provider"""
        if not self.primary_provider_addr:
            return

        registration_msg = {
            'discoveryType': MessageTypes.PROVIDER_REGISTRATION,
            'providerId': self.provider_id,
            'serviceInfo': self.service_info,
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }

        try:
            self.secondary_sock.sendto(
                json.dumps(registration_msg).encode(),
                self.primary_provider_addr
            )
            print(f"Registered with primary provider at {self.primary_provider_addr}")
        except Exception as e:
            print(f"Error registering with primary provider: {e}")
