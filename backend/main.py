from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from auth import require_auth
from blob_reader import read_latest_dataset

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/profile")
def profile(user=Depends(require_auth)):
    return {
        "email": user["email"],
        "role": user["role"],
        "device_id": user["device_id"],
    }


@app.get("/api/data")
def get_data(user=Depends(require_auth)):
    dataset = read_latest_dataset()

    # Admin sees everything
    if user["role"] == "admin":
        print("DATA_ACCESS_ADMIN ", user["email"])
        return {"items": dataset, "count": len(dataset)}

    # User sees only his device
    if not user["device_id"]:
        print("DATA_ACCESS_FORBIDDEN_NO_DEVICE", user["email"])
        raise HTTPException(status_code=403, detail="No device_id claim in token")

    filtered = [x for x in dataset if x.get("device_id") == user["device_id"]]
    print("DATA_ACCESS_USER", user["email"], user["device_id"], len(filtered))
    return {"items": filtered, "count": len(filtered)}
