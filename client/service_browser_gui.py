import sys
import threading
import time
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem, QPushButton, QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QTextEdit, QCheckBox, QScrollArea, QFrame, QSpinBox, QDoubleSpinBox
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QHeaderView
from client.discovery_client import ClientDiscovery
from client.service_repository import ServiceRepository
from client.ws_client import ServiceWebSocketClient
from shared.messages import build_message, MessageTypes
import uuid
import asyncio

class ServiceSettingsDialog(QDialog):
    def __init__(self, service_name, cap_name, cap_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{service_name} - {cap_name} Settings")
        self.inputs = {}

        # Create a widget to hold the form layout
        form_widget = QFrame()
        layout = QFormLayout()
        for setting in cap_settings:
            for k, v in setting.items():
                label = f"{k}: {v}"
                if k.lower() == "bool":
                    inp = QCheckBox()
                    inp.setObjectName(k)
                elif k.lower() == "int":
                    inp = QSpinBox()
                    inp.setObjectName(k)
                elif k.lower() == "float":
                    inp = QDoubleSpinBox()
                    inp.setObjectName(k)
                elif k.lower() == "string":
                    inp = QLineEdit()
                    inp.setObjectName(k)

                layout.addRow(label, inp)
                self.inputs[v] = inp

        self.result_box = QTextEdit()
        self.result_box.setReadOnly(True)
        layout.addRow("Result:", self.result_box)
        self.send_btn = QPushButton("Send Request")
        self.send_btn.clicked.connect(self.on_send_request)
        layout.addWidget(self.send_btn)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        form_widget.setLayout(layout)
        # Add scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form_widget)
        main_layout = QVBoxLayout()
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)
        self._on_send_callback = None

    def get_values(self):
        values = {}
        for k, inp in self.inputs.items():
            if isinstance(inp, QCheckBox):
                values[k] = inp.isChecked()
            elif isinstance(inp, QSpinBox):
                values[k] = inp.value()
            elif isinstance(inp, QDoubleSpinBox):
                values[k] = inp.value()
            elif isinstance(inp, QLineEdit):
                values[k] = inp.text()
            else:
                values[k] = None
        return values
    
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
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
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
        # Include capability statuses in the snapshot for more granular change detection
        new_snapshot = [
            (
            svc.get("serviceId"),
            svc.get("status"),
            svc.get("load"),
            str(svc.get("capabilities")),
            tuple(
                (cap_key, cap.get("status", "Unknown"))
                for cap_key, cap in svc.get("capabilities", {}).items()
            )
            )
            for svc in services
        ]
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
            capabilities = svc.get("capabilities", {})
            for cap_key, cap in capabilities.items():
                status = cap.get("status", "Unknown")
                cap_item = QTreeWidgetItem([cap_key, status, ""])
                cap_item.setData(0, Qt.UserRole, (svc, cap_key))
                provider_item.addChild(cap_item)
            self.tree.addTopLevelItem(provider_item)

    def on_item_double_clicked(self, item, column):
        data = item.data(0, Qt.UserRole)
        if isinstance(data, tuple):
            svc, cap_key = data
            capabilities = svc.get("capabilities", {})
            cap_settings = capabilities.get(cap_key, {}).get("settings", [])
            dlg = ServiceSettingsDialog(svc.get("serviceName", "Unknown"), cap_key, cap_settings, self)
            dlg.set_on_send_callback(lambda params, dialog: self.handle_service_request(svc, cap_key, params, dialog))
            dlg.exec_()

    def handle_service_request(self, svc, cap_key, params, dialog):
        endpoint = self._get_ws_endpoint(svc)
        if not endpoint:
            dialog.set_result("No endpoint found for this service provider.")
            return

        task_id = str(uuid.uuid4())
        self.client = ServiceWebSocketClient(endpoint)

        self._send_assign_task_message(svc, cap_key, params, task_id)

        # Start a timer to check the result and status every 1s in a background thread
        def poll_result():
            self._check_for_result(svc, task_id, dialog)

        self.timer = QTimer(dialog)
        self.timer.timeout.connect(poll_result)
        self.timer.start(2000)

    def _get_ws_endpoint(self, svc):
        endpoint = svc.get("endpoint")
        if endpoint and not (endpoint.startswith("ws://") or endpoint.startswith("wss://")):
            endpoint = f"ws://{endpoint}"

        return endpoint

    def _send_assign_task_message(self, svc, cap_key, params, task_id):
        assign_msg = build_message(
            MessageTypes.ASSIGN_TASK,
            {
                "taskId": task_id,
                "serviceName": svc.get("serviceName"),
                "operation": cap_key,
                "taskParameters": params,
                "callbackClientId": "client-gui-test"
            }
        )

        # Send AssignTask
        self.client.send_message(assign_msg)

    def _check_for_result(self, svc, task_id, dialog):
        try:
            result = self._send_get_status_message(svc, task_id)
            if result == "Done":
                response = self._send_get_result_message(svc, task_id)

                if response:
                    dialog.set_result(str(response))
                else:
                    dialog.set_result("No response received.")

                self.timer.stop()

        except Exception as e:
            dialog.set_result(f"Error: {e}")

    def _send_get_status_message(self, svc, task_id):
        status_msg = build_message(
            "GetStatus",
            {
                "serviceId": svc.get("serviceId"),
                "serviceName": svc.get("serviceName"),
                "taskId": task_id
            }
        )

        response = self.client.send_message(status_msg)
        if isinstance(response, dict):
            return response.get("taskStatus")
        
        return None

    def _send_get_result_message(self, svc, task_id):
        result_msg = build_message(
            "GetResult",
            {
                "serviceId": svc.get("serviceId"),
                "serviceName": svc.get("serviceName"),
                "taskId": task_id
            }
        )

        # Send GetResult and return the received result
        return self.client.send_message(result_msg)


