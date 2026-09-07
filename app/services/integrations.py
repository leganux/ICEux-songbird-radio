import hmac
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ExternalEvent
from app.services.queue import enqueue_asset, enqueue_manual_title


def verify_webhook_secret(provided: str | None, expected: str) -> bool:
    return bool(expected) and bool(provided) and hmac.compare_digest(provided, expected)


def ingest_n8n_event(session: Session, payload: dict) -> tuple[ExternalEvent, bool]:
    event_id = str(payload.get("event_id", "")).strip()
    if not event_id:
        raise ValueError("event_id is required")
    existing = session.scalar(select(ExternalEvent).where(ExternalEvent.event_id == event_id))
    if existing:
        return existing, False

    event_type = str(payload.get("type", "event")).strip() or "event"
    event = ExternalEvent(
        event_id=event_id,
        source=str(payload.get("source", "n8n")).strip() or "n8n",
        type=event_type,
        payload_json=json.dumps(payload),
        decision="stored",
        processed_at=datetime.now(timezone.utc),
    )
    session.add(event)

    if event_type in {"song_request", "queue_asset"} and payload.get("asset_id"):
        item = enqueue_asset(session, int(payload["asset_id"]), source="request", insertion_policy="play_next", payload={"external_event_id": event_id})
        event.decision = f"queued:{item.id}"
    elif event_type in {"greeting", "manual_message"} and payload.get("title"):
        item = enqueue_manual_title(session, str(payload["title"]), str(payload.get("artist", "")))
        event.decision = f"queued:{item.id}"

    session.commit()
    session.refresh(event)
    return event, True


def list_external_events(session: Session, limit: int = 20) -> list[ExternalEvent]:
    return list(session.scalars(select(ExternalEvent).order_by(ExternalEvent.created_at.desc()).limit(limit)))


def serialize_external_event(event: ExternalEvent) -> dict:
    return {
        "id": event.id,
        "event_id": event.event_id,
        "source": event.source,
        "type": event.type,
        "status": event.status,
        "decision": event.decision,
        "created_at": event.created_at.isoformat(),
    }
