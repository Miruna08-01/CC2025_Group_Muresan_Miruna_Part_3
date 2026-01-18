import os
import json
from azure.storage.blob import BlobServiceClient


AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_BLOB_CONTAINER = os.getenv("AZURE_BLOB_CONTAINER")
LATEST_BLOB_NAME = os.getenv("LATEST_BLOB_NAME", "latest.json")



def read_device_latest(device_id: str):
    service = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    container = service.get_container_client(AZURE_BLOB_CONTAINER)

    blob_name = f"latest/device-{device_id}.json"
    blob = container.get_blob_client(blob_name)

    content = blob.download_blob().readall().decode("utf-8")
    return json.loads(content)