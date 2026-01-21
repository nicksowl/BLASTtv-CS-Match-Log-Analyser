from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# Serve JSON files from: data/processed/...
DATA_DIR = Path("data/processed").resolve()

# Where the Docker image copies the Vite build output
# (from the Dockerfile: COPY --from=frontend-build /frontend/dist ./frontend_dist)
FRONTEND_DIST = Path("frontend_dist").resolve()

app = FastAPI(title="CS Match Data API")

# Allow your frontend dev server (Vite default)
# (When running in Docker and serving the built frontend from FastAPI, CORS is basically irrelevant,
# but keeping it doesn't hurt.)
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
    return {
        "ok": True,
        "data_dir": str(DATA_DIR),
        "frontend_dist": str(FRONTEND_DIST),
        "frontend_dist_exists": FRONTEND_DIST.exists(),
    }

# Mount static files: /data/... maps to data/processed/...
app.mount("/data", StaticFiles(directory=str(DATA_DIR)), name="data")

# Serve the built frontend (only if it exists, e.g. in Docker/prod)
if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/")
    def index():
        return FileResponse(str(FRONTEND_DIST / "index.html"))

    # SPA fallback: if the path isn't a real file, return index.html
    # (Needed for React Router / client-side routes)
    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        candidate = FRONTEND_DIST / full_path
        if candidate.exists() and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(FRONTEND_DIST / "index.html"))