import os
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from auth import require_auth
from blob_reader import read_latest_total_for_device, read_latest_totals_all_devices
from blob_reader import (
    read_latest_total_for_device,
    read_latest_totals_all_devices,
    read_historical_all_devices,
)
load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"[REQ] {request.method} {request.url.path}")
    resp = await call_next(request)
    return resp

def fake_user():
    return {"email": "local@test.com", "role": "admin", "device_id": "E-001"}
@app.get("/api/profile")
def profile(user=Depends(require_auth)):
    return {
        "email": user["email"],
        "role": user["role"],
        "device_id": user["device_id"],
    }

@app.get("/api/data")
def data(user=Depends(require_auth)):
    role = user.get("role")
    device_id = user.get("device_id")

    # ADMIN -> listă cu toate device-urile
    if role == "admin":
        item = read_latest_totals_all_devices()
        return {
            "role": role,
            "device_id": device_id,
            "data": [item]
        }

    # USER -> listă cu un singur device (al lui)
    if role == "user":
        if not device_id:
            raise HTTPException(status_code=403, detail="No   device_id claim for this user")

        item = read_latest_total_for_device(device_id)
        return {
            "role": role,
            "device_id": device_id,
            "data": [item]
        }

    raise HTTPException(status_code=403, detail="Insufficient permissions")

@app.get("/api/history")
def history(user=Depends(require_auth), folders_limit: int = 2):
    role = user.get("role")


    if role == "admin":
        rows = read_historical_all_devices(folders_limit=folders_limit, max_devices=50)
        return {"role": "admin", "items": rows, "count": len(rows)}
    if role == "user":
        raise HTTPException(status_code=403, detail="User cannot see history of devices")
    raise HTTPException(status_code=403, detail="Insufficient permissions")