import os
import json
from typing import Any, Dict, List

from azure.storage.blob import BlobServiceClient

AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_BLOB_CONTAINER = os.getenv("AZURE_BLOB_CONTAINER")
LATEST_PREFIX = os.getenv("LATEST_PREFIX", "latest/").rstrip("/") + "/"


def _get_container_client():
    if not AZURE_STORAGE_CONNECTION_STRING or not AZURE_BLOB_CONTAINER:
        raise RuntimeError("Missing AZURE_STORAGE_CONNECTION_STRING or AZURE_BLOB_CONTAINER")

    service = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    return service.get_container_client(AZURE_BLOB_CONTAINER)


def _download_json(container, blob_name: str) -> Dict[str, Any]:
    blob = container.get_blob_client(blob_name)
    raw = blob.download_blob().readall().decode("utf-8")
    return json.loads(raw)


def _extract_device_total(payload: Dict[str, Any], fallback_device_id: str | None = None) -> Dict[str, Any]:
    return {
        "device_id": payload.get("device_id") or fallback_device_id,
        "total_kwh": payload.get("total_kwh"),
    }


# ✅ ADMIN: toate device-urile (doar device_id + total_kwh)
def read_latest_totals_all_devices() -> List[Dict[str, Any]]:
    container = _get_container_client()
    out: List[Dict[str, Any]] = []

    for b in container.list_blobs(name_starts_with=LATEST_PREFIX):
        name = b.name
        if not (name.endswith(".json") and "/device-" in name):
            continue

        try:
            payload = _download_json(container, name)
            out.append(_extract_device_total(payload))
        except Exception as e:
            print("[BLOB] failed", name, "err=", repr(e))
            continue

    out.sort(key=lambda x: x.get("device_id") or "")
    return out


# ✅ USER: doar device-ul lui (doar device_id + total_kwh)
def read_latest_total_for_device(device_id: str) -> Dict[str, Any]:
    container = _get_container_client()
    blob_name = f"{LATEST_PREFIX}device-{device_id}.json"  # ex: latest/device-E-001.json
    payload = _download_json(container, blob_name)
    return _extract_device_total(payload, fallback_device_id=device_id)
