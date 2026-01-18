import os
import json
from typing import List, Dict, Any

from azure.storage.blob import BlobServiceClient

AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_BLOB_CONTAINER = os.getenv("AZURE_BLOB_CONTAINER")

LATEST_PREFIX = os.getenv("LATEST_PREFIX", "latest")  # folder/prefix: latest/


def _get_container_client():
    if not AZURE_STORAGE_CONNECTION_STRING or not AZURE_BLOB_CONTAINER:
        raise RuntimeError("Missing AZURE_STORAGE_CONNECTION_STRING or AZURE_BLOB_CONTAINER")
    service = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    return service.get_container_client(AZURE_BLOB_CONTAINER)


def read_latest_all_devices() -> List[Dict[str, Any]]:
    """
    Reads ALL device json files from prefix 'latest/' and concatenates into one list.
    Expects each blob to contain a JSON array.
    Example blobs:
      latest/device-E-001.json
      latest/device-E-002.json
    """
    container = _get_container_client()
    prefix = LATEST_PREFIX.rstrip("/") + "/"

    items: List[Dict[str, Any]] = []

    # list blobs under latest/
    blob_list = container.list_blobs(name_starts_with=prefix)

    for b in blob_list:
        name = b.name
        if not name.endswith(".json"):
            continue
        # optional: only take device-*.json
        if "/device-" not in name:
            continue

        blob = container.get_blob_client(name)
        content = blob.download_blob().readall().decode("utf-8")

        try:
            data = json.loads(content)
            if isinstance(data, list):
                items.extend(data)
        except Exception:
            # ignore bad json
            pass

    return items


def read_latest_for_device(device_id: str) -> List[Dict[str, Any]]:
    """
    Reads latest data for one device, from blob:
      latest/device-{device_id}.json
    Returns JSON array.
    """
    container = _get_container_client()
    prefix = LATEST_PREFIX.rstrip("/") + "/"
    blob_name = f"{prefix}device-{device_id}.json"

    blob = container.get_blob_client(blob_name)
    content = blob.download_blob().readall().decode("utf-8")
    data = json.loads(content)
    return data if isinstance(data, list) else []
