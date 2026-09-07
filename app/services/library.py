import hashlib
import json
import mimetypes
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import UploadFile
from mutagen import File as MutagenFile

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MediaAsset
from app.services.storage import ObjectStorage


BASE_MEDIA = (
    ("Leganux 2026-1.mp3", "Leganux 2026", "music"),
    ("Leganux Jingle 2025-1.mp3", "Leganux Jingle 2025", "jingle"),
)
ALLOWED_EXTENSIONS = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac"}
HOST_LIBRARY_DIR = Path("data/library")
CONTAINER_LIBRARY_DIR = "/radio/data/library"


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


def get_asset(session: Session, asset_id: int) -> MediaAsset | None:
    return session.get(MediaAsset, asset_id)


def _safe_filename(filename: str) -> str:
    candidate = Path(filename).name.replace("/", "-").replace("\\", "-").strip()
    return candidate or "upload.bin"


def _metadata_for(path: Path) -> dict:
    try:
        audio = MutagenFile(path)
    except Exception:
        return {}
    if not audio:
        return {}
    info = audio.info
    return {
        "duration": getattr(info, "length", None),
        "bitrate": getattr(info, "bitrate", None),
        "sample_rate": getattr(info, "sample_rate", None),
    }


async def import_upload(
    session: Session,
    upload: UploadFile,
    *,
    title: str,
    artist: str = "",
    asset_type: str = "music",
    tags: str = "",
    storage: ObjectStorage | None = None,
) -> MediaAsset:
    original_name = _safe_filename(upload.filename or "upload")
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported audio extension: {extension or 'none'}")

    HOST_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(delete=False, dir=HOST_LIBRARY_DIR) as tmp:
        temp_path = Path(tmp.name)
        while chunk := await upload.read(1024 * 1024):
            tmp.write(chunk)

    digest = hashlib.sha256()
    with temp_path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    checksum = digest.hexdigest()
    final_name = f"{checksum[:16]}-{original_name}"
    final_path = HOST_LIBRARY_DIR / final_name
    shutil.move(str(temp_path), final_path)

    media = _metadata_for(final_path)
    mime_type = upload.content_type or mimetypes.guess_type(original_name)[0] or "application/octet-stream"
    object_key = f"library/{final_name}"
    storage_status = "not-configured"
    if storage:
        try:
            storage.upload_file(object_key, final_path, mime_type)
            storage_status = "uploaded"
        except Exception as exc:
            storage_status = f"degraded:{exc.__class__.__name__}"

    asset = MediaAsset(
        type=asset_type,
        title=title or Path(original_name).stem,
        artist=artist,
        bucket=storage.settings.s3_bucket if storage else "",
        object_key=object_key,
        duration=media.get("duration"),
        local_cache_path=f"{CONTAINER_LIBRARY_DIR}/{final_name}",
        mime_type=mime_type,
        codec=extension.lstrip("."),
        bitrate=media.get("bitrate"),
        sample_rate=media.get("sample_rate"),
        metadata_json=json.dumps({"original_filename": original_name, "sha256": checksum, "object_key": object_key, "storage": storage_status}),
        tags=tags,
    )
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset


def add_to_automation_playlist(asset: MediaAsset, playlist_path: Path = Path("data/automation/playlist.m3u")) -> None:
    playlist_path.parent.mkdir(parents=True, exist_ok=True)
    existing = playlist_path.read_text().splitlines() if playlist_path.exists() else []
    if asset.local_cache_path not in existing:
        with playlist_path.open("a") as playlist:
            if existing and existing[-1].strip():
                playlist.write("\n")
            playlist.write(f"{asset.local_cache_path}\n")


def serialize(asset: MediaAsset) -> dict:
    return {
        "id": asset.id, "type": asset.type, "title": asset.title, "artist": asset.artist,
        "duration": asset.duration, "codec": asset.codec, "bitrate": asset.bitrate,
        "sample_rate": asset.sample_rate, "enabled": asset.enabled, "tags": asset.tags,
        "local_cache_path": asset.local_cache_path,
        "metadata": json.loads(asset.metadata_json or "{}"),
    }
