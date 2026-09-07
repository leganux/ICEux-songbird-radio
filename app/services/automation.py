import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import MediaAsset, Playlist, PlaylistItem, ScheduleRule


AUTOMATION_PLAYLIST = Path("data/automation/playlist.m3u")
VALID_MISSED_POLICIES = {"skip", "reschedule", "play_after_live"}


def create_playlist(session: Session, name: str, description: str = "", rotation_policy: str = "sequential") -> Playlist:
    playlist = Playlist(name=name, description=description, rotation_policy=rotation_policy or "sequential")
    session.add(playlist)
    session.commit()
    session.refresh(playlist)
    return playlist


def list_playlists(session: Session) -> list[Playlist]:
    statement = select(Playlist).options(selectinload(Playlist.items).selectinload(PlaylistItem.media_asset)).order_by(Playlist.name)
    return list(session.scalars(statement))


def add_asset_to_playlist(session: Session, playlist_id: int, asset_id: int) -> PlaylistItem:
    playlist = session.get(Playlist, playlist_id)
    asset = session.get(MediaAsset, asset_id)
    if not playlist:
        raise ValueError("playlist not found")
    if not asset:
        raise ValueError("asset not found")
    max_position = session.scalar(select(func.max(PlaylistItem.position)).where(PlaylistItem.playlist_id == playlist_id)) or 0
    item = PlaylistItem(playlist_id=playlist_id, media_asset_id=asset_id, position=max_position + 1)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def materialize_playlist(session: Session, playlist_id: int, output_path: Path = AUTOMATION_PLAYLIST) -> int:
    playlist = session.get(Playlist, playlist_id)
    if not playlist:
        raise ValueError("playlist not found")
    statement = (
        select(PlaylistItem)
        .options(selectinload(PlaylistItem.media_asset))
        .where(PlaylistItem.playlist_id == playlist_id, PlaylistItem.enabled.is_(True))
        .order_by(PlaylistItem.position)
    )
    items = [item for item in session.scalars(statement) if item.media_asset.enabled]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(item.media_asset.local_cache_path for item in items) + ("\n" if items else ""))
    return len(items)


def create_schedule_rule(
    session: Session,
    *,
    name: str,
    playlist_id: int | None,
    cron: str,
    missed_policy: str,
    event_type: str = "playlist",
) -> ScheduleRule:
    if missed_policy not in VALID_MISSED_POLICIES:
        raise ValueError("invalid missed policy")
    if playlist_id is not None and not session.get(Playlist, playlist_id):
        raise ValueError("playlist not found")
    rule = ScheduleRule(
        name=name,
        playlist_id=playlist_id,
        event_type=event_type,
        cron=cron,
        missed_policy=missed_policy,
        metadata_json=json.dumps({"source": "admin"}),
    )
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


def list_schedule_rules(session: Session) -> list[ScheduleRule]:
    statement = select(ScheduleRule).options(selectinload(ScheduleRule.playlist)).order_by(ScheduleRule.created_at.desc())
    return list(session.scalars(statement))


def serialize_playlist(playlist: Playlist) -> dict:
    ordered = sorted(playlist.items, key=lambda item: item.position)
    return {
        "id": playlist.id,
        "name": playlist.name,
        "description": playlist.description,
        "rotation_policy": playlist.rotation_policy,
        "enabled": playlist.enabled,
        "items": [
            {
                "id": item.id,
                "position": item.position,
                "enabled": item.enabled,
                "asset": {
                    "id": item.media_asset.id,
                    "title": item.media_asset.title,
                    "artist": item.media_asset.artist,
                    "type": item.media_asset.type,
                },
            }
            for item in ordered
        ],
    }


def serialize_schedule_rule(rule: ScheduleRule) -> dict:
    return {
        "id": rule.id,
        "name": rule.name,
        "event_type": rule.event_type,
        "cron": rule.cron,
        "missed_policy": rule.missed_policy,
        "enabled": rule.enabled,
        "playlist": {"id": rule.playlist.id, "name": rule.playlist.name} if rule.playlist else None,
    }
