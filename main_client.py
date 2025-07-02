# Example main for running a client (Service Repository)
import uuid
import sys
from client.discovery_client import ClientDiscovery
from client.service_repository import ServiceRepository
from client.service_browser_gui import ServiceBrowser
from PyQt5.QtWidgets import QApplication

CLIENT_ID = str(uuid.uuid4())

repository = ServiceRepository()
discovery = ClientDiscovery(CLIENT_ID, repository)
discovery.start()

# Example: print discovered services every 10 seconds
try:
    app = QApplication(sys.argv)
    browser = ServiceBrowser(repository, discovery)
    browser.show()
    sys.exit(app.exec_())
except KeyboardInterrupt:
    discovery.stop()
    print("Client stopped.")
