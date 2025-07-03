# Example main for running a service provider
import uuid
from service_provider.discovery_service import ServiceDiscoveryBroadcaster
from service_provider.ws_server import ServiceWebSocketServer
from service_provider_base import ServiceProviderBase


SERVICE_ID = str(uuid.uuid4())
SERVICE_NAME = "ImageProcessingService"
SERVICE_VERSION = "1.2.0"
PORT = 8080
CAPABILITIES = {
    "resizeImage" : {
        "status": "Ready",
        "settings": [
            {"string": "inputPath"},
            {"string": "output"}, 
            {"int": "width"}, 
            {"int": "height"}
        ]
    },
    "applyFilter" : {
        "status": "Ready",
        "settings": [
            {"string": "name"}, 
            {"float": "size"}
        ]
    },
    "convertFormat" : {
        "status": "Ready",
        "settings": [
            {"float": "format"}
        ]
    }
}

class ServiceProviderBEBuilder(ServiceProviderBase):

    def __init__(self):
        super().__init__(SERVICE_NAME, SERVICE_VERSION, PORT, CAPABILITIES)

    def resize_image(self, task_id, parameters, base_result):
        begin_date = parameters.get("inputPath", "")
        base_result["payload"]["resultData"] = {
            "inputPath": begin_date,
            "changeLists": [
                {"number": 101, "date": begin_date or "2024-01-01"},
                {"number": 102, "date": "2024-01-02"}
            ],
            "processedByServiceId": self.service_info["serviceId"],
            "executionDurationMs": 1234
        }
        # Store result and mark as done
        self.task_store[task_id]["result"] = base_result
        self.task_store[task_id]["status"] = "Done"
        CAPABILITIES["getChangeLists"]["status"] = "Ready"

    def apply_filter(self, task_id, parameters, base_result):
        change_list_number = parameters.get("changeListNumber", 0)
        be_file_output_path = parameters.get("BEFileOutputPath", "output/")
        be_file_name = parameters.get("BEFileName", "output.be")
        base_result["payload"]["resultData"] = {
            "changeListNumber": change_list_number,
            "BEFileOutputPath": be_file_output_path,
            "BEFileName": be_file_name,
            "outputFilePath": f"{be_file_output_path}/{be_file_name}",
            "processedByServiceId": self.service_info["serviceId"],
            "executionDurationMs": 1234
        }
        # Store result and mark as done
        self.task_store[task_id]["result"] = base_result
        self.task_store[task_id]["status"] = "Done"
        CAPABILITIES["runBuildOnChangeList"]["status"] = "Ready"

    def convert_format(self, task_id, parameters, base_result):
        be_file_output_path = parameters.get("BEFileOutputPath", "output/")
        be_file_name = parameters.get("BEFileName", "output.be")
        base_result["payload"]["resultData"] = {
            "BEFileOutputPath": be_file_output_path,
            "BEFileName": be_file_name,
            "outputFilePath": f"{be_file_output_path}/{be_file_name}",
            "processedByServiceId": self.service_info["serviceId"],
            "executionDurationMs": 1234
        }
        # Store result and mark as done
        self.task_store[task_id]["result"] = base_result
        self.task_store[task_id]["status"] = "Done"
        CAPABILITIES["runBuildOnLatest"]["status"] = "Ready"

    def handle_assign_task(self, task_id, operation, parameters, base_result):
        import threading

        if operation == "resizeImage":
            thread = threading.Thread(target=self.resize_image, args=(task_id, parameters, base_result))
            thread.start()
        elif operation == "applyFilter":
            thread = threading.Thread(target=self.apply_filter, args=(task_id, parameters, base_result))
            thread.start()
        elif operation == "convertFormat":
            thread = threading.Thread(target=self.convert_format, args=(task_id, parameters, base_result))
            thread.start()

if __name__ == "__main__":
    ServiceProviderBEBuilder().run()