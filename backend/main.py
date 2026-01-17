import os
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from auth import require_auth
from blob_reader import read_latest_dataset

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ok pentru proiect; poți restricționa la domeniul frontendului
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"[REQ] {request.method} {request.url.path}")
    return await call_next(request)

@app.get("/api/profile")
def profile(user=Depends(require_auth)):
    return {"email": user["email"], "role": user["role"], "device_id": user["device_id"]}

@app.get("/api/data")
def data(user=Depends(require_auth)):
    dataset = read_latest_dataset()

    if user["role"] == "admin":
        print("[DATA_ACCESS_ADMIN]", user["email"], "count=", len(dataset))
        return {"role": "admin", "items": dataset, "count": len(dataset)}

    if user["role"] != "user":
        print("[AUTHZ] Unknown role", user["email"])
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    if not user["device_id"]:
        print("[AUTHZ] User without device_id", user["email"])
        raise HTTPException(status_code=403, detail="No device_id claim for this user")

    filtered = [x for x in dataset if x.get("device_id") == user["device_id"]]
    print("[DATA_ACCESS_USER]", user["email"], user["device_id"], "count=", len(filtered))
    return {"role": "user", "device_id": user["device_id"], "items": filtered, "count": len(filtered)}

# local run helper (optional)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "3001")), reload=True)
