import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.api.routes import router
from app.api.websocket import router as websocket_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Not strictly required — every db.py call ensures the schema
    # exists on its own — but doing it once up front surfaces a
    # broken DB path/permissions problem on boot instead of on
    # whatever game happens to finish first.
    db.init_db()
    yield


app = FastAPI(
    title="Kenyan Poker API",
    version="0.1.0",
    lifespan=lifespan,
)


def _allowed_origins() -> list[str]:
    """
    Comma-separated list of origins allowed to call this API, e.g.
    "https://kadi-frontend.onrender.com" — read fresh from
    ALLOWED_ORIGINS at startup, not hardcoded.

    Defaults to "*" (wide open): for local/LAN/Hamachi/Tailscale play,
    the frontend is reached from a browser at whatever host it
    happened to load from (localhost, a LAN IP, a virtual-LAN IP), so
    there's no single fixed origin to allow-list ahead of time — see
    ../frontend/README.md's "Playing with others". Once this is
    deployed somewhere with a real, fixed frontend URL (see
    docs/deploy.md), set ALLOWED_ORIGINS to that URL to stop accepting
    requests from anywhere else.
    """

    raw = os.environ.get("ALLOWED_ORIGINS", "*").strip()

    if not raw or raw == "*":
        return ["*"]

    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(websocket_router)


@app.get("/")
def root():
    return {
        "name": "Kenyan Poker API",
        "status": "running",
    }