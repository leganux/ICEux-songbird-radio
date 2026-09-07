from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401
from app.db import Base
from app.models import MediaAsset
from app.services.ai import create_ai_job, mark_ai_job_ready_without_audio
from app.services.integrations import ingest_n8n_event, verify_webhook_secret
from app.services.live import current_live_session, end_live_session, start_live_session
from app.services.queue import list_queue


def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_n8n_event_is_idempotent_and_can_queue_asset():
    db = session()
    asset = MediaAsset(type="music", title="Request", local_cache_path="/radio/data/library/request.mp3")
    db.add(asset)
    db.commit()

    payload = {"event_id": "evt-1", "type": "song_request", "asset_id": asset.id}
    event, created = ingest_n8n_event(db, payload)
    duplicate, duplicate_created = ingest_n8n_event(db, payload)

    assert verify_webhook_secret("secret", "secret")
    assert created is True
    assert duplicate_created is False
    assert duplicate.id == event.id
    assert list_queue(db)[0].title == "Request"


def test_ai_job_creates_non_playable_pending_asset():
    db = session()
    job = create_ai_job(db, job_type="capsule", topic="weather")

    prepared = mark_ai_job_ready_without_audio(db, job.id)

    assert prepared.status == "tts_pending"
    assert prepared.audio_asset_id is not None
    assert db.get(MediaAsset, prepared.audio_asset_id).enabled is False


def test_live_session_lifecycle():
    db = session()
    live = start_live_session(db, mode="live_current_music")

    assert current_live_session(db).id == live.id
    ended = end_live_session(db, live.id)

    assert ended.status == "ended"
    assert current_live_session(db) is None
