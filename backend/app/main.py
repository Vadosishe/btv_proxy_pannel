from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.routers import auth, admin, agency, client_portal

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# Create tables automatically on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Corporate B2B VPN Orchestrator API",
    version="1.0.0",
    description="Multi-tenant B2B VPN orchestration platform for AmneziaWG v2 and 3X-UI v3"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(agency.router)
app.include_router(client_portal.router)

FRONTEND_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend"))

@app.get("/")
def serve_dashboard():
    return FileResponse(os.path.join(FRONTEND_PATH, "index.html"))

