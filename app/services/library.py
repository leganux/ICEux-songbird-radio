from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MediaAsset


BASE_MEDIA = (
    ("Leganux 2026-1.mp3", "Leganux 2026", "music"),
    ("Leganux Jingle 2025-1.mp3", "Leganux Jingle 2025", "jingle"),
)


def seed_base_media(session: Session) -> None:
    """Register bundled local tracks once; files stay independent from object storage."""
    for filename, title, asset_type in BASE_MEDIA:
        container_path = f"/radio/data/basemusic/{filename}"
        exists = session.scalar(select(MediaAsset.id).where(MediaAsset.local_cache_path == container_path))
        if not exists:
            session.add(MediaAsset(type=asset_type, title=title, local_cache_path=container_path, tags="starter,local"))
    session.commit()


def list_assets(session: Session, asset_type: str | None = None) -> list[MediaAsset]:
    statement = select(MediaAsset).order_by(MediaAsset.created_at.desc())
    if asset_type:
        statement = statement.where(MediaAsset.type == asset_type)
    return list(session.scalars(statement))


def serialize(asset: MediaAsset) -> dict:
    return {
        "id": asset.id, "type": asset.type, "title": asset.title, "artist": asset.artist,
        "duration": asset.duration, "codec": asset.codec, "bitrate": asset.bitrate,
        "sample_rate": asset.sample_rate, "enabled": asset.enabled, "tags": asset.tags,
        "local_cache_path": asset.local_cache_path,
    }
