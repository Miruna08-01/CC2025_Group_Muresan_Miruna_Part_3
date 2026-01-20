import os
import json
from typing import Any, Dict, List

from azure.storage.blob import BlobServiceClient

AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_BLOB_CONTAINER = os.getenv("AZURE_BLOB_CONTAINER")
LATEST_PREFIX = os.getenv("LATEST_PREFIX", "latest/").rstrip("/") + "/"
HIST_PREFIX = os.getenv("HISTORY_FILE", "history").rstrip("/") + "/"


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

def list_historical_folders(limit: int = 10) -> List[str]:
    """
    Returnează ultimele 'limit' foldere de tip historical/YYYY-MM-DD_.... (lexicografic)
    """
    container = _get_container_client()
    folders = set()

    for b in container.list_blobs(name_starts_with=HIST_PREFIX):
        name = b.name  # historical/2026-01-18_150442/device-E-001.json
        parts = name.split("/")
        if len(parts) >= 2:
            folders.add(parts[1])

    # sort desc (cele mai noi primele)
    out = sorted(list(folders), reverse=True)
    return out[:limit]

def read_historical_for_device(device_id: str, folders_limit: int = 3) -> List[Dict[str, Any]]:
    """
    Citește istoric din ultimele 'folders_limit' foldere.
    Returnează listă de records (timestamp, kwh, location, device_id)
    """
    container = _get_container_client()
    folders = list_historical_folders(limit=folders_limit)

    all_rows: List[Dict[str, Any]] = []
    for f in folders:
        blob_name = f"{HIST_PREFIX}{f}/device-{device_id}.json"
        try:
            payload = _download_json(container, blob_name)

            # cazul tău: payload poate fi dict cu 'records' (stringuri json)
            if isinstance(payload, dict) and "records" in payload:
                for rec in payload["records"]:
                    try:
                        obj = json.loads(rec)
                        obj["device_id"] = payload.get("device_id", device_id)
                        all_rows.append(obj)
                    except Exception:
                        pass

            # dacă e list direct
            elif isinstance(payload, list):
                for obj in payload:
                    if isinstance(obj, dict):
                        obj["device_id"] = obj.get("device_id", device_id)
                        all_rows.append(obj)

        except Exception:
            continue

    # sort după timestamp dacă există
    all_rows.sort(key=lambda x: x.get("timestamp", ""))
    return all_rows
def read_historical_all_devices(folders_limit: int = 1, max_devices: int = 50) -> List[Dict[str, Any]]:
    """
    ADMIN: Citește istoricul din ultimele 'folders_limit' foldere pentru toate device-urile.
    ATENȚIE: poate fi mare, de aia limităm.
    """
    container = _get_container_client()
    folders = list_historical_folders(limit=folders_limit)

    # luam device list din latest/ ca să știm ce device-uri există
    device_ids: List[str] = []
    for b in container.list_blobs(name_starts_with=LATEST_PREFIX):
        name = b.name
        if name.endswith(".json") and "/device-" in name:
            # latest/device-E-001.json
            base = name.split("/")[-1]  # device-E-001.json
            dev = base.replace("device-", "").replace(".json", "")
            device_ids.append(dev)

    device_ids = sorted(list(set(device_ids)))[:max_devices]

    rows: List[Dict[str, Any]] = []
    for dev in device_ids:
        rows.extend(read_historical_for_device(dev, folders_limit=folders_limit))

    rows.sort(key=lambda x: x.get("timestamp", ""))
    return rows