import os
import json
from azure.storage.blob import BlobServiceClient


AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_BLOB_CONTAINER = os.getenv("AZURE_BLOB_CONTAINER")
LATEST_BLOB_NAME = os.getenv("LATEST_BLOB_NAME", "latest.json")


def read_latest_dataset():
    """
    Reads JSON array from Azure Blob.
    The file should be something like:
      [
        {"timestamp":"2026-01-01T10:00:00", "device_id":"deviceA", "value":10},
        ...
      ]
    """
    if not AZURE_STORAGE_CONNECTION_STRING or not AZURE_BLOB_CONTAINER:
        # fallback local test if Blob isn't configured
        return [
            {"timestamp": "2026-01-01T10:00:00", "device_id": "deviceA", "value": 10},
            {"timestamp": "2026-01-01T10:00:00", "device_id": "deviceB", "value": 20},
            {"timestamp": "2026-01-01T10:05:00", "device_id": "deviceA", "value": 15},
        ]

    service = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    container = service.get_container_client(AZURE_BLOB_CONTAINER)

    blob = container.get_blob_client(LATEST_BLOB_NAME)
    content = blob.download_blob().readall().decode("utf-8")
    return json.loads(content)
