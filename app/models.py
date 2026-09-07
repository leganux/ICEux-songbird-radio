from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(32), index=True, default="music")
    title: Mapped[str] = mapped_column(String(255), index=True)
    artist: Mapped[str] = mapped_column(String(255), default="")
    album: Mapped[str] = mapped_column(String(255), default="")
    category: Mapped[str] = mapped_column(String(100), default="", index=True)
    duration: Mapped[float | None] = mapped_column(default=None)
    bucket: Mapped[str] = mapped_column(String(255), default="")
    object_key: Mapped[str] = mapped_column(String(1024), default="")
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


class Playlist(Base):
    __tablename__ = "playlists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    rotation_policy: Mapped[str] = mapped_column(String(50), default="sequential")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    items: Mapped[list["PlaylistItem"]] = relationship(back_populates="playlist", cascade="all, delete-orphan")


class PlaylistItem(Base):
    __tablename__ = "playlist_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    playlist_id: Mapped[int] = mapped_column(ForeignKey("playlists.id", ondelete="CASCADE"), index=True)
    media_asset_id: Mapped[int] = mapped_column(ForeignKey("media_assets.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0, index=True)
    weight: Mapped[int] = mapped_column(Integer, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    playlist: Mapped[Playlist] = relationship(back_populates="items")
    media_asset: Mapped[MediaAsset] = relationship()


class ScheduleRule(Base):
    __tablename__ = "schedule_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    playlist_id: Mapped[int | None] = mapped_column(ForeignKey("playlists.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(50), default="playlist")
    cron: Mapped[str] = mapped_column(String(120), default="")
    missed_policy: Mapped[str] = mapped_column(String(50), default="skip")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    playlist: Mapped[Playlist | None] = relationship()


class PlayQueueItem(Base):
    __tablename__ = "play_queue_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    media_asset_id: Mapped[int | None] = mapped_column(ForeignKey("media_assets.id", ondelete="SET NULL"), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(50), default="music", index=True)
    source: Mapped[str] = mapped_column(String(50), default="manual", index=True)
    priority: Mapped[int] = mapped_column(Integer, default=50, index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    artist: Mapped[str] = mapped_column(String(255), default="")
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="queued", index=True)
    missed_policy: Mapped[str] = mapped_column(String(50), default="skip")
    insertion_policy: Mapped[str] = mapped_column(String(50), default="append")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    media_asset: Mapped[MediaAsset | None] = relationship()


class PlayHistory(Base):
    __tablename__ = "play_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    media_asset_id: Mapped[int | None] = mapped_column(ForeignKey("media_assets.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    artist: Mapped[str] = mapped_column(String(255), default="")
    type: Mapped[str] = mapped_column(String(50), default="music", index=True)
    source: Mapped[str] = mapped_column(String(50), default="manual", index=True)
    result: Mapped[str] = mapped_column(String(50), default="completed", index=True)
    reason: Mapped[str] = mapped_column(String(255), default="")
    played_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    duration: Mapped[float | None] = mapped_column(default=None)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")

    media_asset: Mapped[MediaAsset | None] = relationship()


class CartButton(Base):
    __tablename__ = "cart_buttons"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(120), index=True)
    media_asset_id: Mapped[int | None] = mapped_column(ForeignKey("media_assets.id", ondelete="SET NULL"), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(60), default="fx", index=True)
    action: Mapped[str] = mapped_column(String(50), default="play_next")
    color: Mapped[str] = mapped_column(String(30), default="blue")
    hotkey: Mapped[str] = mapped_column(String(30), default="")
    position: Mapped[int] = mapped_column(Integer, default=0, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    media_asset: Mapped[MediaAsset | None] = relationship()


class ExternalEvent(Base):
    __tablename__ = "external_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(80), default="n8n", index=True)
    type: Mapped[str] = mapped_column(String(80), default="event", index=True)
    status: Mapped[str] = mapped_column(String(50), default="received", index=True)
    decision: Mapped[str] = mapped_column(String(120), default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AIJob(Base):
    __tablename__ = "ai_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_type: Mapped[str] = mapped_column(String(80), default="capsule", index=True)
    topic: Mapped[str] = mapped_column(String(255), default="")
    prompt: Mapped[str] = mapped_column(Text, default="")
    script: Mapped[str] = mapped_column(Text, default="")
    script_provider: Mapped[str] = mapped_column(String(80), default="stub")
    tts_provider: Mapped[str] = mapped_column(String(80), default="stub")
    voice: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(50), default="draft", index=True)
    audio_asset_id: Mapped[int | None] = mapped_column(ForeignKey("media_assets.id", ondelete="SET NULL"), nullable=True, index=True)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    audio_asset: Mapped[MediaAsset | None] = relationship()


class LiveSession(Base):
    __tablename__ = "live_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    mode: Mapped[str] = mapped_column(String(50), default="live_current_music", index=True)
    status: Mapped[str] = mapped_column(String(50), default="active", index=True)
    mic_gain_db: Mapped[int] = mapped_column(Integer, default=-3)
    music_gain_db: Mapped[int] = mapped_column(Integer, default=-4)
    duck_gain_db: Mapped[int] = mapped_column(Integer, default=-18)
    bed_asset_id: Mapped[int | None] = mapped_column(ForeignKey("media_assets.id", ondelete="SET NULL"), nullable=True, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_heartbeat_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")

    bed_asset: Mapped[MediaAsset | None] = relationship()
