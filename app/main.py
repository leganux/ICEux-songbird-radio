import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.db import Base, SessionLocal, engine, ensure_lightweight_migrations
from app import models  # noqa: F401 - registers SQLAlchemy models
from app.services.ai import create_ai_job, list_ai_jobs, mark_ai_job_ready_without_audio, serialize_ai_job
from app.services.automation import (
    add_asset_to_playlist,
    create_playlist,
    create_schedule_rule,
    list_playlists,
    list_schedule_rules,
    materialize_playlist,
    serialize_playlist,
    serialize_schedule_rule,
)
from app.services.library import add_to_automation_playlist, get_asset, import_upload, list_assets, seed_base_media, seed_soundfx_media, serialize
from app.services.liquidsoap import LiquidsoapService
from app.services.integrations import ingest_n8n_event, list_external_events, serialize_external_event, verify_webhook_secret
from app.services.live import current_live_session, end_live_session, heartbeat_live_session, serialize_live_session, start_live_session
from app.services.queue import (
    clear_manual_queue,
    create_cart_button,
    enqueue_asset,
    enqueue_manual_title,
    fire_cart,
    list_carts,
    list_history,
    list_queue,
    remove_queue_item,
    serialize_cart,
    serialize_history_item,
    serialize_queue_item,
    seed_default_carts,
)
from app.services.storage import ObjectStorage

settings = get_settings()
clients: set[WebSocket] = set()
login_attempts: dict[str, deque[float]] = defaultdict(deque)


def radio_snapshot() -> dict:
    with SessionLocal() as session:
        queue_items = list_queue(session)
        history = list_history(session, 8)
        live = current_live_session(session)
        next_track = serialize_queue_item(queue_items[0]) if queue_items else None
        return {
            "on_air": True,
            "now_playing": {"title": "Emergency playlist ready", "artist": "ICEux", "type": "music", "source": "fallback"},
            "next_track": next_track,
            "queue": [serialize_queue_item(item) for item in queue_items],
            "history": [serialize_history_item(item) for item in history],
            "live": serialize_live_session(live),
        }


async def broadcast(event: str) -> None:
    stale = []
    payload = {"event": event, "data": radio_snapshot()}
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
    ensure_lightweight_migrations(engine)
    with SessionLocal() as session:
        seed_base_media(session)
        seed_default_carts(session, seed_soundfx_media(session))
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
    return {
        "status": "ok",
        "components": {
            "fastapi": "ok",
            "liquidsoap": "ok" if ls.connected else "degraded",
            "sqlite": "ok",
            "n8n": "configured" if settings.n8n_webhook_secret else "not-configured",
            "ai": "stub",
            "tts": "stub",
            "live": "control-ready",
        },
        "detail": ls.detail,
    }


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
    return templates.TemplateResponse(request, "dashboard.html", {"state": radio_snapshot(), "mount": settings.icecast_mount, "csrf_token": request.session["csrf"]})


@app.get("/api/radio/state")
async def state(request: Request):
    require_admin(request)
    return radio_snapshot()


@app.get("/api/queue")
async def queue(request: Request):
    require_admin(request)
    return radio_snapshot()["queue"]


@app.delete("/api/queue/{item_id}")
async def remove_from_queue(item_id: int, request: Request):
    require_admin(request)
    require_csrf(request)
    with SessionLocal() as session:
        try:
            remove_queue_item(session, item_id)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
    await broadcast("queue_changed")
    return {"ok": True}


@app.post("/api/queue/clear-manual")
async def clear_manual_queue_endpoint(request: Request):
    require_admin(request)
    require_csrf(request)
    with SessionLocal() as session:
        count = clear_manual_queue(session)
    await broadcast("queue_changed")
    return {"ok": True, "items": count}


@app.get("/api/library")
async def library(request: Request, type: str | None = None):
    require_admin(request)
    with SessionLocal() as session:
        return [serialize(asset) for asset in list_assets(session, type)]


@app.post("/api/library/upload")
async def upload_library_asset(
    request: Request,
    title: str = Form(""),
    artist: str = Form(""),
    type: str = Form("music"),
    tags: str = Form(""),
    file: UploadFile = File(),
):
    require_admin(request)
    require_csrf(request)
    with SessionLocal() as session:
        try:
            asset = await import_upload(
                session,
                file,
                title=title.strip(),
                artist=artist.strip(),
                asset_type=type.strip() or "music",
                tags=tags.strip(),
                storage=ObjectStorage(settings),
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return serialize(asset)


@app.post("/api/library/{asset_id}/automation")
async def add_library_asset_to_automation(asset_id: int, request: Request):
    require_admin(request)
    require_csrf(request)
    with SessionLocal() as session:
        asset = get_asset(session, asset_id)
        if not asset:
            raise HTTPException(404, "asset not found")
        add_to_automation_playlist(asset)
        return {"ok": True, "asset": serialize(asset)}


@app.get("/api/playlists")
async def playlists(request: Request):
    require_admin(request)
    with SessionLocal() as session:
        return [serialize_playlist(playlist) for playlist in list_playlists(session)]


@app.post("/api/playlists")
async def create_playlist_endpoint(request: Request):
    require_admin(request)
    require_csrf(request)
    body = await request.json()
    name = str(body.get("name", "")).strip()
    if not name:
        raise HTTPException(422, "name is required")
    with SessionLocal() as session:
        try:
            playlist = create_playlist(session, name, str(body.get("description", "")).strip(), str(body.get("rotation_policy", "sequential")).strip())
        except Exception as exc:
            raise HTTPException(422, "playlist could not be created") from exc
        return serialize_playlist(playlist)


@app.post("/api/playlists/{playlist_id}/items")
async def add_playlist_item_endpoint(playlist_id: int, request: Request):
    require_admin(request)
    require_csrf(request)
    body = await request.json()
    try:
        asset_id = int(body.get("asset_id"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, "asset_id is required") from exc
    with SessionLocal() as session:
        try:
            add_asset_to_playlist(session, playlist_id, asset_id)
            playlist = session.get(models.Playlist, playlist_id)
            return serialize_playlist(playlist)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc


@app.post("/api/playlists/{playlist_id}/materialize")
async def materialize_playlist_endpoint(playlist_id: int, request: Request):
    require_admin(request)
    require_csrf(request)
    with SessionLocal() as session:
        try:
            count = materialize_playlist(session, playlist_id)
            return {"ok": True, "items": count}
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc


@app.get("/api/schedules")
async def schedules(request: Request):
    require_admin(request)
    with SessionLocal() as session:
        return [serialize_schedule_rule(rule) for rule in list_schedule_rules(session)]


@app.post("/api/schedules")
async def create_schedule_endpoint(request: Request):
    require_admin(request)
    require_csrf(request)
    body = await request.json()
    name = str(body.get("name", "")).strip()
    cron = str(body.get("cron", "")).strip()
    missed_policy = str(body.get("missed_policy", "skip")).strip()
    playlist_id = body.get("playlist_id")
    if not name or not cron:
        raise HTTPException(422, "name and cron are required")
    with SessionLocal() as session:
        try:
            rule = create_schedule_rule(
                session,
                name=name,
                playlist_id=int(playlist_id) if playlist_id else None,
                cron=cron,
                missed_policy=missed_policy,
            )
            return serialize_schedule_rule(rule)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc


@app.post("/api/queue")
async def enqueue(request: Request):
    require_admin(request)
    require_csrf(request)
    body = await request.json()
    title = str(body.get("title", "")).strip()
    asset_id = body.get("asset_id")
    if not title and not asset_id:
        raise HTTPException(422, "title is required")
    with SessionLocal() as session:
        if asset_id:
            item = enqueue_asset(
                session,
                int(asset_id),
                source=str(body.get("source", "manual")).strip() or "manual",
                insertion_policy=str(body.get("insertion_policy", "append")).strip() or "append",
                missed_policy=str(body.get("missed_policy", "skip")).strip() or "skip",
            )
        else:
            item = enqueue_manual_title(session, title, str(body.get("artist", "")).strip())
    await broadcast("queue_changed")
    return serialize_queue_item(item)


@app.get("/api/history")
async def history(request: Request):
    require_admin(request)
    with SessionLocal() as session:
        return [serialize_history_item(item) for item in list_history(session)]


@app.get("/api/carts")
async def carts(request: Request):
    require_admin(request)
    with SessionLocal() as session:
        return [serialize_cart(cart) for cart in list_carts(session)]


@app.post("/api/carts")
async def create_cart(request: Request):
    require_admin(request)
    require_csrf(request)
    body = await request.json()
    label = str(body.get("label", "")).strip()
    if not label:
        raise HTTPException(422, "label is required")
    asset_id = body.get("asset_id")
    with SessionLocal() as session:
        try:
            cart = create_cart_button(
                session,
                label=label,
                asset_id=int(asset_id) if asset_id else None,
                category=str(body.get("category", "fx")).strip() or "fx",
                action=str(body.get("action", "play_next")).strip() or "play_next",
                color=str(body.get("color", "blue")).strip() or "blue",
                hotkey=str(body.get("hotkey", "")).strip(),
            )
            return serialize_cart(cart)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc


@app.post("/api/carts/{cart_id}/fire")
async def fire_cart_endpoint(cart_id: int, request: Request):
    require_admin(request)
    require_csrf(request)
    with SessionLocal() as session:
        try:
            item = fire_cart(session, cart_id)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
    await broadcast("queue_changed")
    return {"ok": True, "queue_item": serialize_queue_item(item) if item else None}


@app.get("/api/integrations/n8n/events")
async def n8n_events(request: Request):
    require_admin(request)
    with SessionLocal() as session:
        return [serialize_external_event(event) for event in list_external_events(session)]


@app.post("/api/integrations/n8n/events")
async def receive_n8n_event(request: Request):
    if not verify_webhook_secret(request.headers.get("X-ICEux-Webhook-Secret"), settings.n8n_webhook_secret):
        raise HTTPException(401, "invalid webhook secret")
    payload = await request.json()
    with SessionLocal() as session:
        try:
            event, created = ingest_n8n_event(session, payload)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    await broadcast("external_event")
    return {"ok": True, "created": created, "event": serialize_external_event(event)}


@app.get("/api/ai/jobs")
async def ai_jobs(request: Request):
    require_admin(request)
    with SessionLocal() as session:
        return [serialize_ai_job(job) for job in list_ai_jobs(session)]


@app.post("/api/ai/jobs")
async def create_ai_job_endpoint(request: Request):
    require_admin(request)
    require_csrf(request)
    body = await request.json()
    topic = str(body.get("topic", "")).strip()
    if not topic:
        raise HTTPException(422, "topic is required")
    with SessionLocal() as session:
        job = create_ai_job(
            session,
            job_type=str(body.get("job_type", "capsule")).strip() or "capsule",
            topic=topic,
            prompt=str(body.get("prompt", "")).strip(),
            voice=str(body.get("voice", "")).strip(),
        )
    return serialize_ai_job(job)


@app.post("/api/ai/jobs/{job_id}/prepare-asset")
async def prepare_ai_asset(job_id: int, request: Request):
    require_admin(request)
    require_csrf(request)
    with SessionLocal() as session:
        try:
            job = mark_ai_job_ready_without_audio(session, job_id)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
    return serialize_ai_job(job)


@app.get("/api/live")
async def live_state(request: Request):
    require_admin(request)
    with SessionLocal() as session:
        return serialize_live_session(current_live_session(session))


@app.post("/api/live/start")
async def start_live(request: Request):
    require_admin(request)
    require_csrf(request)
    body = await request.json()
    with SessionLocal() as session:
        try:
            live = start_live_session(
                session,
                mode=str(body.get("mode", "live_current_music")).strip() or "live_current_music",
                bed_asset_id=int(body["bed_asset_id"]) if body.get("bed_asset_id") else None,
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    await broadcast("live_changed")
    return serialize_live_session(live)


@app.post("/api/live/{live_id}/heartbeat")
async def live_heartbeat(live_id: int, request: Request):
    require_admin(request)
    require_csrf(request)
    with SessionLocal() as session:
        try:
            live = heartbeat_live_session(session, live_id)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
    return serialize_live_session(live)


@app.post("/api/live/end")
async def end_live(request: Request):
    require_admin(request)
    require_csrf(request)
    with SessionLocal() as session:
        try:
            live = end_live_session(session)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
    await broadcast("live_changed")
    return serialize_live_session(live)


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
