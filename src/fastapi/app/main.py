from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Serve JSON files from: data/processed/...
DATA_DIR = Path("data/processed").resolve()

app = FastAPI(title="CS Match Data API")

# Allow your frontend dev server (Vite default)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True, "data_dir": str(DATA_DIR)}

# Mount static files: /data/... maps to data/processed/...
app.mount("/data", StaticFiles(directory=str(DATA_DIR)), name="data")