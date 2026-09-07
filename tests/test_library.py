from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app import models  # noqa: F401
from app.services.library import list_assets, seed_base_media


def test_base_tracks_are_seeded_once():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    seed_base_media(session)
    seed_base_media(session)
    assert len(list_assets(session)) == 2
