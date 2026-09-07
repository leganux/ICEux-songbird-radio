from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class QueueItem:
    id: str
    title: str
    artist: str
    source: str
    created_at: str


class RadioState:
    """Phase-1 in-memory view. Liquidsoap is authoritative once control is connected."""
    def __init__(self) -> None:
        self.now_playing = {"title": "Emergency playlist ready", "artist": "ICEux", "type": "music", "source": "fallback"}
        self.queue: list[QueueItem] = []

    def snapshot(self) -> dict:
        return {"on_air": False, "now_playing": self.now_playing, "next_track": asdict(self.queue[0]) if self.queue else None, "queue": [asdict(x) for x in self.queue]}

    def enqueue(self, title: str, artist: str = "") -> QueueItem:
        item = QueueItem(str(uuid4()), title, artist, "manual", datetime.now(timezone.utc).isoformat())
        self.queue.append(item)
        return item
