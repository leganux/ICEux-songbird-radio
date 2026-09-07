from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401
from app.db import Base
from app.models import MediaAsset
from app.services.queue import (
    create_cart_button,
    enqueue_asset,
    fire_cart,
    list_carts,
    list_history,
    list_queue,
    remove_queue_item,
)


def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_queue_orders_by_priority_before_created_at():
    db = session()
    song = MediaAsset(type="music", title="Song", local_cache_path="/radio/data/library/song.mp3")
    emergency = MediaAsset(type="station_id", title="ID", local_cache_path="/radio/data/library/id.mp3")
    db.add_all([song, emergency])
    db.commit()

    enqueue_asset(db, song.id, source="rotation")
    enqueue_asset(db, emergency.id, source="manual")

    queued = list_queue(db)
    assert [item.title for item in queued] == ["ID", "Song"]


def test_remove_queue_item_writes_history():
    db = session()
    item = models.PlayQueueItem(title="Manual", artist="ICEux", type="manual", source="manual")
    db.add(item)
    db.commit()

    remove_queue_item(db, item.id)

    assert list_queue(db) == []
    history = list_history(db)
    assert history[0].title == "Manual"
    assert history[0].result == "skipped"


def test_cart_fire_enqueues_asset():
    db = session()
    asset = MediaAsset(type="jingle", title="Jingle", local_cache_path="/radio/data/library/jingle.mp3")
    db.add(asset)
    db.commit()
    cart = create_cart_button(db, label="JINGLE 1", asset_id=asset.id, category="jingle", action="play_next", color="purple")

    fired = fire_cart(db, cart.id)

    assert len(list_carts(db)) == 1
    assert fired.title == "Jingle"
    assert list_queue(db)[0].title == "Jingle"
