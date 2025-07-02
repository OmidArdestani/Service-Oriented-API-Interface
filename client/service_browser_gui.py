import sys
import threading
import time
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem, QPushButton, QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QTextEdit
from PyQt5.QtCore import Qt
from client.discovery_client import ClientDiscovery
from client.service_repository import ServiceRepository
from client.ws_client import ServiceWebSocketClient
from shared.messages import build_message, MessageTypes
import uuid
import asyncio

class ServiceSettingsDialog(QDialog):
    def __init__(self, service_name, capability, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{service_name} - {capability['key']} Settings")
        self.inputs = {}
        layout = QFormLayout()
        for setting in capability.get('settings', []):
            for k, v in setting.items():
                label = f"{k}: {v}"
                inp = QLineEdit()
                inp.setObjectName(k)
                layout.addRow(label, inp)
                self.inputs[k] = inp
        self.result_box = QTextEdit()
        self.result_box.setReadOnly(True)
        layout.addRow("Result:", self.result_box)
        self.send_btn = QPushButton("Send Request")
        self.send_btn.clicked.connect(self.on_send_request)
        layout.addWidget(self.send_btn)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.setLayout(layout)
        self._on_send_callback = None

    def get_values(self):
        return {k: inp.text() for k, inp in self.inputs.items()}
    
    def set_result(self, text):
        self.result_box.setPlainText(text)
        self.setEnabled(True)

    def on_send_request(self):
        if self._on_send_callback:
            self.setEnabled(False)
            self.result_box.setPlainText("Waiting for result...")
            self._on_send_callback(self.get_values(), self)

    def set_on_send_callback(self, callback):
        self._on_send_callback = callback

class ServiceBrowser(QWidget):
    def __init__(self, repository, discovery):
        super().__init__()
        self.repository = repository
        self.discovery = discovery
        self.setWindowTitle("Service-Oriented API Interface - Service Browser")
        self.setGeometry(100, 100, 600, 400)
        self.layout = QVBoxLayout()
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Service Provider", "Status", "Load"])
        self.layout.addWidget(QLabel("Discovered Service Providers:"))
        self.layout.addWidget(self.tree)
        self.refresh_btn = QPushButton("Refresh Services")
        self.refresh_btn.clicked.connect(self.manual_refresh)
        self.layout.addWidget(self.refresh_btn)
        self.setLayout(self.layout)
        self.update_thread = threading.Thread(target=self.periodic_update, daemon=True)
        self.update_thread.start()
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)

    def manual_refresh(self):
        self.discovery.send_discovery_request()
        self.update_tree()

    def periodic_update(self):
        while True:
            self.update_tree()
            time.sleep(5)

    def update_tree(self):
        services = self.repository.get_services()
        # Only update if there are changes
        new_snapshot = [(svc.get("serviceId"), svc.get("status"), svc.get("load"), str(svc.get("capabilities"))) for svc in services]
        if hasattr(self, '_last_snapshot') and self._last_snapshot == new_snapshot:
            return
        self._last_snapshot = new_snapshot
        self.tree.clear()
        for svc in services:
            provider_item = QTreeWidgetItem([
                svc.get("serviceName", "Unknown"),
                svc.get("status", "Unknown"),
                str(svc.get("load", ""))
            ])
            provider_item.setData(0, Qt.UserRole, svc)
            # Capabilities
            for cap in svc.get("capabilities", []):
                cap_item = QTreeWidgetItem([cap.get("key", ""), "", ""])
                cap_item.setData(0, Qt.UserRole, (svc, cap))
                provider_item.addChild(cap_item)
            self.tree.addTopLevelItem(provider_item)

    def on_item_double_clicked(self, item, column):
        data = item.data(0, Qt.UserRole)
        if isinstance(data, tuple):
            svc, cap = data
            dlg = ServiceSettingsDialog(svc.get("serviceName", "Unknown"), cap, self)
            dlg.set_on_send_callback(lambda params, dialog: self.handle_service_request(svc, cap, params, dialog))
            dlg.exec_()

    def handle_service_request(self, svc, cap, params, dialog):
        # Send real WebSocket request to the selected service provider
        endpoint = svc.get("endpoint")
        # Ensure endpoint has ws:// or wss:// scheme
        if endpoint and not (endpoint.startswith("ws://") or endpoint.startswith("wss://")):
            endpoint = f"ws://{endpoint}"
        if not endpoint:
            dialog.set_result("No endpoint found for this service provider.")
            return
        # Build AssignTask message
        task_id = str(uuid.uuid4())
        message = build_message(
            MessageTypes.ASSIGN_TASK,
            {
                "taskId": task_id,
                "serviceName": svc.get("serviceName"),
                "operation": cap.get("key"),
                "taskParameters": params,
                "callbackClientId": "client-gui-test"
            }
        )
        # Build GetStatus and GetResult messages
        status_message = build_message(
            "GetStatus",
            {
                "serviceId": svc.get("serviceId"),
                "serviceName": svc.get("serviceName"),
                "taskId": task_id
            }
        )
        result_message = build_message(
            "GetResult",
            {
                "serviceId": svc.get("serviceId"),
                "serviceName": svc.get("serviceName"),
                "taskId": task_id
            }
        )
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            client = ServiceWebSocketClient(f"{endpoint}")
            async def send_and_poll():
                import asyncio

                # Send AssignTask
                send_result = client.send_message(message)
                if hasattr(send_result, "__await__"):
                    await send_result
                else:
                    async for _ in send_result:
                        break  # Just send once if generator

                # Poll for status
                status = None
                for _ in range(60):  # up to 60 seconds
                    await asyncio.sleep(1)

                    status_result = client.send_message(status_message)
                    async for resp in status_result:
                        if resp.get("type") == "Status":
                            status = resp.get("taskStatus")

                            break

                    if status == "Done":
                        break

                if status != "Done":
                    return "Task did not complete in time."

                # Get result
                result_result = client.send_message(result_message)
                async for resp in result_result:
                    if resp.get("type") == "TaskResult":
                        return resp

                return "No result received."

            resp = loop.run_until_complete(send_and_poll())
            if resp:
                dialog.set_result(str(resp))
            else:
                dialog.set_result("No response received.")

        except Exception as e:
            dialog.set_result(f"Error: {e}")


