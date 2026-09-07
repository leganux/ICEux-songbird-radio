import asyncio

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.datastructures import UploadFile

from app.db import Base
from app import models  # noqa: F401
from app.services import library
from app.services.library import add_to_automation_playlist, import_upload, list_assets, seed_base_media, seed_soundfx_media
from app.services.queue import list_carts, seed_default_carts


def test_base_tracks_are_seeded_once():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    seed_base_media(session)
    seed_base_media(session)
    assert len(list_assets(session)) == 2


async def _upload_from_path(path):
    return UploadFile(path.open("rb"), filename=path.name)


def test_import_upload_creates_cached_asset(tmp_path, monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    monkeypatch.setattr(library, "HOST_LIBRARY_DIR", tmp_path)
    source = library.Path("app/static/basemusic/Leganux 2026-1.mp3")

    upload = asyncio.run(_upload_from_path(source))
    asset = asyncio.run(import_upload(session, upload, title="Imported", artist="Leganux"))

    assert asset.title == "Imported"
    assert asset.local_cache_path.startswith("/radio/data/library/")
    assert (tmp_path / asset.local_cache_path.rsplit("/", 1)[1]).exists()
    assert asset.metadata_json


def test_add_to_automation_playlist_is_idempotent(tmp_path):
    asset = models.MediaAsset(title="Track", local_cache_path="/radio/data/library/track.mp3")
    playlist = tmp_path / "playlist.m3u"

    add_to_automation_playlist(asset, playlist)
    add_to_automation_playlist(asset, playlist)

    assert playlist.read_text().splitlines() == ["/radio/data/library/track.mp3"]


def test_seed_soundfx_media_and_carts(tmp_path, monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    sound = tmp_path / "laser-hit.mp3"
    sound.write_bytes(b"not-a-real-mp3")
    monkeypatch.setattr(library, "HOST_SOUNDFX_DIR", tmp_path)

    assets = seed_soundfx_media(session)
    seed_default_carts(session, assets)
    seed_default_carts(session, assets)

    assert len(assets) == 1
    assert assets[0].type == "effect"
    assert assets[0].local_cache_path == "/radio/data/soundfx/laser-hit.mp3"
    assert len(list_carts(session)) == 1
