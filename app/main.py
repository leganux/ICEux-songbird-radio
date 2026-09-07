import asyncio
import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.db import Base, SessionLocal, engine
from app import models  # noqa: F401 - registers SQLAlchemy models
from app.services.library import list_assets, seed_base_media, serialize
from app.services.liquidsoap import LiquidsoapService
from app.services.radio import RadioState

settings = get_settings()
radio = RadioState()
clients: set[WebSocket] = set()
login_attempts: dict[str, deque[float]] = defaultdict(deque)


async def broadcast(event: str) -> None:
    stale = []
    payload = {"event": event, "data": radio.snapshot()}
    for client in clients:
        try:
            await client.send_json(payload)
        except Exception:
            stale.append(client)
    for client in stale:
        clients.discard(client)


def is_authenticated(request: Request) -> bool:
    return request.session.get("admin") == settings.admin_username


def require_admin(request: Request) -> None:
    if not is_authenticated(request):
        raise HTTPException(401, "Authentication required")


def require_csrf(request: Request) -> None:
    token = request.headers.get("X-CSRF-Token")
    if not token:
        token = request.query_params.get("csrf_token")
    if not token or not hmac.compare_digest(token, request.session.get("csrf", "")):
        raise HTTPException(403, "Invalid CSRF token")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Phase 1 creates the control-plane database; Alembic owns future migrations.
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        seed_base_media(session)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret, https_only=settings.production, same_site="lax")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/health")
async def health() -> dict:
    ls = await LiquidsoapService(
        settings.liquidsoap_host, settings.liquidsoap_port,
        settings.icecast_host, settings.icecast_port, settings.icecast_mount, settings.liquidsoap_socket,
    ).health()
    return {"status": "ok", "components": {"fastapi": "ok", "liquidsoap": "ok" if ls.connected else "degraded", "sqlite": "pending-phase-1"}, "detail": ls.detail}


@app.get("/ready")
async def ready() -> JSONResponse:
    configured = bool(settings.admin_password and settings.session_secret != "development-only-change-me")
    return JSONResponse({"ready": configured, "reason": "credentials configured" if configured else "configure ADMIN_PASSWORD and SESSION_SECRET"}, status_code=200 if configured else 503)


@app.get("/login")
async def login_form(request: Request):
    return templates.TemplateResponse(request, "login.html")


@app.post("/login")
async def login(request: Request, username: str = Form(), password: str = Form()):
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    attempts = login_attempts[ip]
    while attempts and now - attempts[0] > 300:
        attempts.popleft()
    if len(attempts) >= 5:
        raise HTTPException(429, "Too many login attempts")
    valid = hmac.compare_digest(username, settings.admin_username) and hmac.compare_digest(password, settings.admin_password)
    if not valid or not settings.admin_password:
        attempts.append(now)
        return templates.TemplateResponse(request, "login.html", {"error": "Invalid credentials"}, status_code=401)
    request.session.clear()
    request.session["admin"] = settings.admin_username
    request.session["csrf"] = secrets.token_urlsafe(32)
    return RedirectResponse("/admin", status_code=303)


@app.post("/logout")
async def logout(request: Request):
    require_admin(request)
    require_csrf(request)
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/")
async def root():
    return RedirectResponse("/admin")


@app.get("/admin")
async def dashboard(request: Request):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(request, "dashboard.html", {"state": radio.snapshot(), "mount": settings.icecast_mount, "csrf_token": request.session["csrf"]})


@app.get("/api/radio/state")
async def state(request: Request):
    require_admin(request)
    return radio.snapshot()


@app.get("/api/queue")
async def queue(request: Request):
    require_admin(request)
    return radio.snapshot()["queue"]


@app.get("/api/library")
async def library(request: Request, type: str | None = None):
    require_admin(request)
    with SessionLocal() as session:
        return [serialize(asset) for asset in list_assets(session, type)]


@app.post("/api/queue")
async def enqueue(request: Request):
    require_admin(request)
    require_csrf(request)
    body = await request.json()
    title = str(body.get("title", "")).strip()
    if not title:
        raise HTTPException(422, "title is required")
    item = radio.enqueue(title, str(body.get("artist", "")).strip())
    await broadcast("queue_changed")
    return item


@app.post("/api/player/skip")
async def skip(request: Request):
    require_admin(request)
    require_csrf(request)
    try:
        await LiquidsoapService(settings.liquidsoap_host, settings.liquidsoap_port, socket_path=settings.liquidsoap_socket).skip()
        return {"ok": True, "control": "liquidsoap"}
    except ConnectionError:
        return JSONResponse({"ok": False, "detail": "Liquidsoap control unavailable; audio fallback is unaffected"}, status_code=503)


@app.websocket("/ws/radio")
async def ws_radio(websocket: WebSocket):
    if websocket.scope.get("session", {}).get("admin") != settings.admin_username:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    clients.add(websocket)
    await websocket.send_json({"event": "radio_state", "data": radio.snapshot()})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        clients.discard(websocket)
