import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import CartButton, MediaAsset, PlayHistory, PlayQueueItem


SOURCE_PRIORITIES = {
    "emergency": 0,
    "live": 5,
    "manual": 10,
    "scheduler": 30,
    "request": 40,
    "commercial": 45,
    "capsule": 50,
    "clock": 55,
    "rotation": 80,
}
VALID_CART_ACTIONS = {"overlay", "play_next", "play_now", "duck_play"}
VALID_QUEUE_STATUSES = {"queued", "playing", "completed", "failed", "skipped", "held"}


def priority_for(source: str, asset_type: str) -> int:
    if asset_type in {"commercial", "capsule", "clock", "station_id", "jingle"}:
        return SOURCE_PRIORITIES.get(asset_type, SOURCE_PRIORITIES.get(source, 50))
    return SOURCE_PRIORITIES.get(source, 50)


def enqueue_asset(
    session: Session,
    asset_id: int,
    *,
    source: str = "manual",
    insertion_policy: str = "append",
    missed_policy: str = "skip",
    scheduled_for: datetime | None = None,
    payload: dict | None = None,
) -> PlayQueueItem:
    asset = session.get(MediaAsset, asset_id)
    if not asset or not asset.enabled:
        raise ValueError("asset not found")
    item = PlayQueueItem(
        media_asset_id=asset.id,
        type=asset.type,
        source=source,
        priority=priority_for(source, asset.type),
        title=asset.title,
        artist=asset.artist,
        scheduled_for=scheduled_for,
        missed_policy=missed_policy,
        insertion_policy=insertion_policy,
        payload_json=json.dumps(payload or {}),
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def enqueue_manual_title(session: Session, title: str, artist: str = "") -> PlayQueueItem:
    item = PlayQueueItem(type="manual", source="manual", priority=SOURCE_PRIORITIES["manual"], title=title, artist=artist)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def list_queue(session: Session) -> list[PlayQueueItem]:
    statement = (
        select(PlayQueueItem)
        .options(selectinload(PlayQueueItem.media_asset))
        .where(PlayQueueItem.status == "queued")
        .order_by(PlayQueueItem.priority, PlayQueueItem.scheduled_for.is_(None), PlayQueueItem.scheduled_for, PlayQueueItem.created_at)
    )
    return list(session.scalars(statement))


def get_next_item(session: Session) -> PlayQueueItem | None:
    return next(iter(list_queue(session)), None)


def remove_queue_item(session: Session, item_id: int, result: str = "skipped", reason: str = "removed") -> PlayQueueItem:
    item = session.get(PlayQueueItem, item_id)
    if not item or item.status != "queued":
        raise ValueError("queue item not found")
    item.status = result
    item.updated_at = datetime.now(timezone.utc)
    history = PlayHistory(
        media_asset_id=item.media_asset_id,
        title=item.title,
        artist=item.artist,
        type=item.type,
        source=item.source,
        result=result,
        reason=reason,
        payload_json=item.payload_json,
    )
    session.add(history)
    session.commit()
    session.refresh(item)
    return item


def clear_manual_queue(session: Session) -> int:
    items = list(session.scalars(select(PlayQueueItem).where(PlayQueueItem.status == "queued", PlayQueueItem.source == "manual")))
    for item in items:
        remove_queue_item(session, item.id, "skipped", "clear manual queue")
    return len(items)


def list_history(session: Session, limit: int = 25) -> list[PlayHistory]:
    statement = select(PlayHistory).order_by(PlayHistory.played_at.desc()).limit(limit)
    return list(session.scalars(statement))


def create_cart_button(
    session: Session,
    *,
    label: str,
    asset_id: int | None,
    category: str = "fx",
    action: str = "play_next",
    color: str = "blue",
    hotkey: str = "",
) -> CartButton:
    if action not in VALID_CART_ACTIONS:
        raise ValueError("invalid cart action")
    if asset_id is not None and not session.get(MediaAsset, asset_id):
        raise ValueError("asset not found")
    max_position = session.scalar(select(CartButton.position).order_by(CartButton.position.desc()).limit(1)) or 0
    cart = CartButton(label=label, media_asset_id=asset_id, category=category, action=action, color=color, hotkey=hotkey, position=max_position + 1)
    session.add(cart)
    session.commit()
    session.refresh(cart)
    return cart


def list_carts(session: Session) -> list[CartButton]:
    statement = select(CartButton).options(selectinload(CartButton.media_asset)).where(CartButton.enabled.is_(True)).order_by(CartButton.position)
    return list(session.scalars(statement))


def fire_cart(session: Session, cart_id: int) -> PlayQueueItem | None:
    cart = session.get(CartButton, cart_id)
    if not cart or not cart.enabled:
        raise ValueError("cart not found")
    if not cart.media_asset_id:
        return None
    insertion_policy = "play_now" if cart.action in {"play_now", "duck_play", "overlay"} else "play_next"
    return enqueue_asset(session, cart.media_asset_id, source="manual", insertion_policy=insertion_policy, payload={"cart_id": cart.id, "cart_action": cart.action})


def serialize_queue_item(item: PlayQueueItem) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "artist": item.artist,
        "type": item.type,
        "source": item.source,
        "priority": item.priority,
        "status": item.status,
        "missed_policy": item.missed_policy,
        "insertion_policy": item.insertion_policy,
        "scheduled_for": item.scheduled_for.isoformat() if item.scheduled_for else None,
        "created_at": item.created_at.isoformat(),
    }


def serialize_history_item(item: PlayHistory) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "artist": item.artist,
        "type": item.type,
        "source": item.source,
        "result": item.result,
        "reason": item.reason,
        "played_at": item.played_at.isoformat(),
        "duration": item.duration,
    }


def serialize_cart(cart: CartButton) -> dict:
    return {
        "id": cart.id,
        "label": cart.label,
        "category": cart.category,
        "action": cart.action,
        "color": cart.color,
        "hotkey": cart.hotkey,
        "position": cart.position,
        "asset": {
            "id": cart.media_asset.id,
            "title": cart.media_asset.title,
            "artist": cart.media_asset.artist,
            "type": cart.media_asset.type,
        } if cart.media_asset else None,
    }
