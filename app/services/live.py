import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LiveSession


LIVE_MODES = {"live_mic_only", "live_current_music", "live_custom_bed"}


def start_live_session(session: Session, *, mode: str, bed_asset_id: int | None = None) -> LiveSession:
    if mode not in LIVE_MODES:
        raise ValueError("invalid live mode")
    active = session.scalar(select(LiveSession).where(LiveSession.status == "active"))
    if active:
        return active
    live = LiveSession(mode=mode, bed_asset_id=bed_asset_id, metadata_json=json.dumps({"transport": "webrtc-planned"}))
    session.add(live)
    session.commit()
    session.refresh(live)
    return live


def heartbeat_live_session(session: Session, live_id: int) -> LiveSession:
    live = session.get(LiveSession, live_id)
    if not live or live.status != "active":
        raise ValueError("live session not active")
    live.last_heartbeat_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(live)
    return live


def end_live_session(session: Session, live_id: int | None = None, reason: str = "ended_by_admin") -> LiveSession:
    statement = select(LiveSession).where(LiveSession.status == "active")
    if live_id:
        statement = statement.where(LiveSession.id == live_id)
    live = session.scalar(statement)
    if not live:
        raise ValueError("live session not active")
    live.status = "ended"
    live.ended_at = datetime.now(timezone.utc)
    live.metadata_json = json.dumps({"reason": reason})
    session.commit()
    session.refresh(live)
    return live


def current_live_session(session: Session) -> LiveSession | None:
    return session.scalar(select(LiveSession).where(LiveSession.status == "active").order_by(LiveSession.started_at.desc()))


def serialize_live_session(live: LiveSession | None) -> dict:
    if not live:
        return {"active": False, "mode": "automation"}
    return {
        "active": live.status == "active",
        "id": live.id,
        "mode": live.mode,
        "status": live.status,
        "mic_gain_db": live.mic_gain_db,
        "music_gain_db": live.music_gain_db,
        "duck_gain_db": live.duck_gain_db,
        "bed_asset_id": live.bed_asset_id,
        "started_at": live.started_at.isoformat(),
        "last_heartbeat_at": live.last_heartbeat_at.isoformat(),
    }
