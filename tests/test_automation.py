from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401
from app.db import Base
from app.models import MediaAsset
from app.services.automation import (
    add_asset_to_playlist,
    create_playlist,
    create_schedule_rule,
    materialize_playlist,
)


def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_playlist_materializes_ordered_local_paths(tmp_path):
    db = session()
    first = MediaAsset(title="One", local_cache_path="/radio/data/library/one.mp3")
    second = MediaAsset(title="Two", local_cache_path="/radio/data/library/two.mp3")
    db.add_all([first, second])
    db.commit()
    playlist = create_playlist(db, "Morning")

    add_asset_to_playlist(db, playlist.id, first.id)
    add_asset_to_playlist(db, playlist.id, second.id)
    count = materialize_playlist(db, playlist.id, tmp_path / "playlist.m3u")

    assert count == 2
    assert (tmp_path / "playlist.m3u").read_text().splitlines() == [
        "/radio/data/library/one.mp3",
        "/radio/data/library/two.mp3",
    ]


def test_schedule_rule_requires_valid_missed_policy():
    db = session()
    playlist = create_playlist(db, "Fallback")

    rule = create_schedule_rule(db, name="Top of hour", playlist_id=playlist.id, cron="0 * * * *", missed_policy="skip")

    assert rule.name == "Top of hour"
    try:
        create_schedule_rule(db, name="Bad", playlist_id=playlist.id, cron="* * * * *", missed_policy="later-ish")
    except ValueError as exc:
        assert "missed policy" in str(exc)
    else:
        raise AssertionError("invalid missed policy should fail")
