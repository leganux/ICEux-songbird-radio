# ICEux autonomous audio plane. Configure actual tracks and Icecast credentials via environment.
# This script must run independently of FastAPI.
set("log.stdout",true)
# Private control channel shared only with the FastAPI container.
settings.server.socket := true
settings.server.socket.path := "/run/iceux/liquidsoap.sock"
settings.server.socket.permissions := 0o660
emergency = playlist(reload_mode="watch","/radio/data/emergency/playlist.m3u")
automation = playlist(reload_mode="watch","/radio/data/automation/playlist.m3u")
# Dynamic controls can be added as a request queue in Phase 2.
radio = fallback(track_sensitive=false,[automation, emergency, blank()])
output.icecast(%mp3(bitrate=128), host="icecast", port=8000,
  password=environment.get("ICECAST_SOURCE_PASSWORD"), mount="/radio", radio)

def skip_handler(_) =
  source.skip(automation)
  "OK"
end

server.register(namespace="radio", "skip", skip_handler)
