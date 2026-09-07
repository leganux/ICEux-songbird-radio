from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(32), index=True, default="music")
    title: Mapped[str] = mapped_column(String(255), index=True)
    artist: Mapped[str] = mapped_column(String(255), default="")
    album: Mapped[str] = mapped_column(String(255), default="")
    duration: Mapped[float | None] = mapped_column(default=None)
    local_cache_path: Mapped[str] = mapped_column(String(1024), unique=True)
    mime_type: Mapped[str] = mapped_column(String(100), default="audio/mpeg")
    codec: Mapped[str] = mapped_column(String(32), default="mp3")
    bitrate: Mapped[int | None] = mapped_column(Integer, default=None)
    sample_rate: Mapped[int | None] = mapped_column(Integer, default=None)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    tags: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_played_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    play_count: Mapped[int] = mapped_column(Integer, default=0)
