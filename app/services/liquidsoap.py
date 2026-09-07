import asyncio
import json
from urllib.request import urlopen
from dataclasses import dataclass


@dataclass(frozen=True)
class LiquidsoapStatus:
    connected: bool
    detail: str


class LiquidsoapService:
    """Small control-plane client; Liquidsoap remains autonomous if this is down."""

    def __init__(self, host: str, port: int, icecast_host: str | None = None, icecast_port: int = 8000, mount: str = "/radio", socket_path: str = "") -> None:
        self.host, self.port = host, port
        self.icecast_host, self.icecast_port, self.mount = icecast_host, icecast_port, mount
        self.socket_path = socket_path

    async def command(self, value: str) -> str:
        try:
            connection = asyncio.open_unix_connection(self.socket_path) if self.socket_path else asyncio.open_connection(self.host, self.port)
            reader, writer = await asyncio.wait_for(connection, timeout=1.5)
            writer.write(f"{value}\n".encode())
            await writer.drain()
            reply = (await asyncio.wait_for(reader.readline(), timeout=1.5)).decode().strip()
            writer.close()
            await writer.wait_closed()
            return reply
        except (OSError, asyncio.TimeoutError) as exc:
            raise ConnectionError("Liquidsoap control socket unavailable") from exc

    async def health(self) -> LiquidsoapStatus:
        # The Telnet server remains loopback-only because it has no authentication.
        # Icecast mount presence is the safe, externally observable audio-plane health.
        if self.icecast_host:
            try:
                state = await asyncio.to_thread(self._icecast_mount_active)
                if state:
                    return LiquidsoapStatus(True, "Icecast mount is receiving the Liquidsoap stream")
                return LiquidsoapStatus(False, "Icecast is reachable but the configured mount has no active source")
            except Exception:
                pass
        try:
            await self.command("help")
            return LiquidsoapStatus(True, "control socket connected")
        except ConnectionError:
            return LiquidsoapStatus(False, "control socket unavailable; autonomous fallback may still be on air")

    def _icecast_mount_active(self) -> bool:
        url = f"http://{self.icecast_host}:{self.icecast_port}/status-json.xsl"
        with urlopen(url, timeout=1.5) as response:  # nosec B310: host is deployment configuration
            payload = json.load(response)
        source = payload.get("icestats", {}).get("source", [])
        sources = source if isinstance(source, list) else [source]
        return any(item.get("listenurl", "").endswith(self.mount) for item in sources if isinstance(item, dict))

    async def skip(self) -> None:
        await self.command("radio.skip")
