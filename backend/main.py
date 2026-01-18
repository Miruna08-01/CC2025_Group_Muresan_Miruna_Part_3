import os
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from auth import require_auth
from blob_reader import read_latest_all_devices, read_latest_for_device

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

@app.get("/api/profile")
def profile(user=Depends(require_auth)):
    print("[PROFILE] email=", user.get("email"), "role=", user.get("role"), "device_id=", user.get("device_id"))
    return {"email": user["email"], "role": user["role"], "device_id": user["device_id"]}

@app.get("/api/data")
def data(user=Depends(require_auth)):
    role = user.get("role")
    device_id = user.get("device_id")
    email = user.get("email")

    print("[DATA] email=", email, "role=", role, "device_id=", device_id)
    print("[ENV] has_conn=", bool(os.getenv("AZURE_STORAGE_CONNECTION_STRING")),
          "container=", os.getenv("AZURE_BLOB_CONTAINER"),
          "prefix=", os.getenv("LATEST_PREFIX"))

    # ✅ ADMIN -> all devices
    if role == "admin":
        dataset = read_latest_all_devices()
        print("[DATA_ACCESS_ADMIN]", email, "count=", len(dataset))
        return {"role": "admin", "items": dataset, "count": len(dataset)}

    # ✅ USER -> only own device
    if role == "user":
        if not device_id:
            print("[AUTHZ] missing device_id for", email)
            raise HTTPException(status_code=403, detail="No device_id claim for this user")

        dataset = read_latest_for_device(device_id)
        print("[DATA_ACCESS_USER]", email, device_id, "count=", len(dataset))
        return {"role": "user", "device_id": device_id, "items": dataset, "count": len(dataset)}

    print("[AUTHZ] Unknown role:", role, "for", email)
    raise HTTPException(status_code=403, detail="Insufficient permissions")

@app.get("/debug/env")
def debug_env():
    # NU printează cheia, doar dacă există
    return {
        "has_connection_string": bool(os.getenv("AZURE_STORAGE_CONNECTION_STRING")),
        "container": os.getenv("AZURE_BLOB_CONTAINER"),
        "latest_prefix": os.getenv("LATEST_PREFIX"),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "3001")), reload=True)
