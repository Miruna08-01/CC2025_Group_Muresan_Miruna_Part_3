import os
import json
from typing import Any, Dict, List, Tuple
from azure.storage.blob import BlobServiceClient

AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_BLOB_CONTAINER = os.getenv("AZURE_BLOB_CONTAINER")

LATEST_PREFIX = os.getenv("LATEST_PREFIX", "latest/").rstrip("/") + "/"
HISTORICAL_PREFIX = os.getenv("HISTORICAL_PREFIX", "historical/").rstrip("/") + "/"


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
        "generation_timestamp": payload.get("generation_timestamp"),
    }


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
            print("[LATEST] failed", name, "err=", repr(e))

    out.sort(key=lambda x: x.get("device_id") or "")
    return out


def read_latest_total_for_device(device_id: str) -> Dict[str, Any]:
    container = _get_container_client()
    blob_name = f"{LATEST_PREFIX}device-{device_id}.json"
    payload = _download_json(container, blob_name)
    return _extract_device_total(payload, fallback_device_id=device_id)


# ---------------------------------------------------------
# ✅ HISTORICAL: citește ultimele N foldere din historical/
# ---------------------------------------------------------

def _list_historical_folders(container, folders_limit: int) -> List[str]:
    """
    Returnează lista folderelor sub historical/, ex:
    ['historical/2025-12-10_182826/', 'historical/2025-12-11_090000/', ...]
    """
    folders = set()
    for b in container.list_blobs(name_starts_with=HISTORICAL_PREFIX):
        name = b.name  # historical/2025-12-10_182826/device-E-001.json
        rest = name[len(HISTORICAL_PREFIX):]  # 2025-12-10_182826/device-E-001.json
        if "/" not in rest:
            continue
        folder = rest.split("/", 1)[0]
        folders.add(f"{HISTORICAL_PREFIX}{folder}/")

    # sort desc (cele mai noi primele)
    folders_sorted = sorted(folders, reverse=True)
    return folders_sorted[: max(1, folders_limit)]


def read_historical_all_devices(folders_limit: int = 7, max_devices: int = 200) -> List[Dict[str, Any]]:
    """
    Returnează row-uri pentru chart: pe fiecare zi-folder, pe fiecare device.
    """
    container = _get_container_client()
    rows: List[Dict[str, Any]] = []

    folders = _list_historical_folders(container, folders_limit=folders_limit)
    if not folders:
        print("[HIST] No folders found under", HISTORICAL_PREFIX)
        return []

    for folder_prefix in folders:
        device_count = 0

        for b in container.list_blobs(name_starts_with=folder_prefix):
            name = b.name  # historical/.../device-E-001.json
            if not name.endswith(".json"):
                continue
            base = name.split("/")[-1]  # device-E-001.json
            if not base.startswith("device-"):
                continue

            # fallback device id din filename
            fallback_device_id = base.replace("device-", "").replace(".json", "")

            try:
                payload = _download_json(container, name)
                item = _extract_device_total(payload, fallback_device_id=fallback_device_id)
                item["folder"] = folder_prefix.rstrip("/")  # pt etichetă chart
                rows.append(item)
                device_count += 1
            except Exception as e:
                print("[HIST] failed", name, "err=", repr(e))

            if device_count >= max_devices:
                break

    return rows
