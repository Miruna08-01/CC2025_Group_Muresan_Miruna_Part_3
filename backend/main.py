import os
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from auth import require_auth
from blob_reader import (
    read_latest_all_devices,
    read_latest_for_device,
    list_latest_blob_names,
)

load_dotenv()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ok pt proiect (poți restrânge după)
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"[REQ] {request.method} {request.url.path}")
    resp = await call_next(request)
    print(f"[RESP] {request.method} {request.url.path} -> {resp.status_code}")
    return resp


@app.get("/api/profile")
def profile(user=Depends(require_auth)):
    return {
        "email": user["email"],
        "role": user["role"],
        "device_id": user["device_id"],
    }


@app.get("/api/data")
def data(user=Depends(require_auth)):

    # ✅ ADMIN -> toate device-urile
    if user["role"] == "admin":
        dataset = read_latest_all_devices()
        print("[ADMIN] returning ALL devices, count =", len(dataset))
        return {
            "role": "admin",
            "items": dataset,
            "count": len(dataset)
        }

    # ✅ USER -> doar device-ul lui
    if user["role"] == "user":
        if not user["device_id"]:
            raise HTTPException(status_code=403, detail="No device_id claim for this user")

        dataset = read_latest_for_device(user["device_id"])
        print("[USER] returning ONLY device =", user["device_id"], "count =", len(dataset))
        return {
            "role": "user",
            "device_id": user["device_id"],
            "items": dataset,
            "count": len(dataset)
        }

    # ✅ orice alt rol -> blocked
    raise HTTPException(status_code=403, detail="Insufficient permissions")



# ---- DEBUG endpoints (fără auth) ----
@app.get("/debug/list")
def debug_list():
    names = list_latest_blob_names(limit=50)
    return {"count": len(names), "names": names}


@app.get("/debug/blob")
def debug_blob():
    data = read_latest_all_devices()
    return {"count": len(data), "sample": data[:3]}


if __name__ == "__main__":
    import uvicorn

    # local: uvicorn main:app --reload --port 3001
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "3001")), reload=True)
