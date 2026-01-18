import os
import json
from typing import List, Dict, Any
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

load_dotenv()
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_BLOB_CONTAINER = os.getenv("AZURE_BLOB_CONTAINER")

# poate fi "latest" sau "latest/"
LATEST_PREFIX = os.getenv("LATEST_PREFIX", "latest")


def _get_container_client():
    if not AZURE_STORAGE_CONNECTION_STRING or not AZURE_BLOB_CONTAINER:
        raise RuntimeError("Missing AZURE_STORAGE_CONNECTION_STRING or AZURE_BLOB_CONTAINER")

    # print util ca să vezi dacă se încarcă env-urile
    print("[BLOB] container=", AZURE_BLOB_CONTAINER)
    print("[BLOB] latest_prefix=", LATEST_PREFIX)

    service = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    return service.get_container_client(AZURE_BLOB_CONTAINER)


def list_latest_blob_names(limit: int = 50) -> List[str]:
    container = _get_container_client()
    prefix = LATEST_PREFIX.rstrip("/") + "/"

    names: List[str] = []
    for b in container.list_blobs(name_starts_with=prefix):
        names.append(b.name)
        if len(names) >= limit:
            break
    return names


def _parse_device_blob_payload(content: str) -> List[Dict[str, Any]]:
    """
    Acceptă:
      - dict { device_id, records: ["{...}", "{...}"] }
      - list [{...}, {...}]
    Întoarce listă de obiecte JSON.
    """
    payload = json.loads(content)

    # cazul tău: dict cu records string JSON
    if isinstance(payload, dict) and "records" in payload:
        out: List[Dict[str, Any]] = []
        device_id = payload.get("device_id")

        recs = payload.get("records", [])
        if isinstance(recs, list):
            for rec in recs:
                if not isinstance(rec, str):
                    continue
                try:
                    obj = json.loads(rec)
                    # inject device_id pentru chart/filter
                    if device_id and "device_id" not in obj:
                        obj["device_id"] = device_id
                    out.append(obj)
                except Exception:
                    pass
        return out

    # cazul alternativ: listă direct
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]

    return []


def read_latest_all_devices() -> List[Dict[str, Any]]:
    """
    Citește TOATE device-urile din latest/ și concatenează.
    """
    container = _get_container_client()
    prefix = LATEST_PREFIX.rstrip("/") + "/"

    all_items: List[Dict[str, Any]] = []

    print("[BLOB] listing blobs under:", prefix)

    for b in container.list_blobs(name_starts_with=prefix):
        name = b.name

        if not name.endswith(".json"):
            continue
        if "/device-" not in name:
            continue

        print("[BLOB] reading:", name)

        blob = container.get_blob_client(name)
        content = blob.download_blob().readall().decode("utf-8")

        try:
            items = _parse_device_blob_payload(content)
            print("[BLOB] parsed items:", len(items))
            all_items.extend(items)
        except Exception as e:
            print("[BLOB] parse failed:", name, "err=", e)

    print("[BLOB] TOTAL items:", len(all_items))
    return all_items


def read_latest_for_device(device_id: str) -> List[Dict[str, Any]]:
    """
    Citește latest/device-{device_id}.json
    """
    container = _get_container_client()
    prefix = LATEST_PREFIX.rstrip("/") + "/"
    blob_name = f"{prefix}device-{device_id}.json"

    print("[BLOB] reading device blob:", blob_name)

    blob = container.get_blob_client(blob_name)
    content = blob.download_blob().readall().decode("utf-8")

    items = _parse_device_blob_payload(content)
    print("[BLOB] device items:", len(items))
    return items
