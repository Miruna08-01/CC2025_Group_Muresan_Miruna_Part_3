import os
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from auth import require_auth
from blob_reader import read_latest_total_for_device, read_latest_totals_all_devices

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

# def fake_user():
#     return {"email": "local@test.com", "role": "admin", "device_id": "E-001"}
@app.get("/api/profile")
def profile(user=Depends(require_auth)):
    return {
        "email": user["email"],
        "role": user["role"],
        "device_id": user["device_id"],
        "token_id": user.get("sub"),  # <-- asta e "token id"
    }

@app.get("/api/data")
def data(user=Depends(require_auth)):
    role = user.get("role")
    device_id = user.get("device_id")

    # ✅ ADMIN -> toate device-urile
    if role == "admin":
        rows = read_latest_totals_all_devices()  # ex: [{"device_id":"E-001","total_kwh":450.67}, ...]
        return {
            "role": "admin",
            "device_id": device_id,   # o să fie null la admin, e OK
            "data": rows,             # IMPORTANT: data, nu items
            "count": len(rows),
        }

    # ✅ USER -> doar device-ul lui
    if role == "user":
        if not device_id:
            raise HTTPException(status_code=403, detail="No device_id claim for this user")

        row = read_latest_total_for_device(device_id)  # ex: {"device_id":"E-001","total_kwh":450.67}
        return {
            "role": "user",
            "device_id": device_id,
            "data": [row],            # IMPORTANT: tot data (list), ca la admin
            "count": 1,
        }

    raise HTTPException(status_code=403, detail="Insufficient permissions")