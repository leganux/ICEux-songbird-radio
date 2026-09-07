# ICEux Songbird Radio

> The first all-in-one AI-powered Icecast2 interface & automator

ICEux Songbird Radio is a personal web control plane for Icecast2 radio automation, live broadcasting, media management and future AI/n8n workflows. It is designed to progressively replace desktop broadcasting software while protecting the one thing that matters most: uninterrupted audio.

## Architecture

FastAPI controls metadata, UI and commands. Liquidsoap owns audio and keeps local automation/emergency music running independently. Icecast2 distributes the stream. See [ARCHITECTURE.md](ARCHITECTURE.md), [BACKEND.md](BACKEND.md), and [FRONTEND.md](FRONTEND.md) for the source-of-truth design.

## Phase 1

- One-admin login sourced only from `.env`
- Server-rendered Bootstrap control dashboard with current/next decks and queue
- WebSocket state updates and a guarded Liquidsoap skip command
- SQLite initialization with WAL and foreign keys
- Liquidsoap automation → local emergency fallback script
- Health/readiness endpoints

This release does not yet provision Icecast, MinIO, AI/TTS, n8n, or WebRTC. Those are the next documented phases; no UI claims they are live.

## Run locally

1. Copy `.env.example` to `.env`, set a strong `ADMIN_PASSWORD` and random `SESSION_SECRET`.
2. Create `.venv` and install dependencies: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.
3. Start the control plane: `.venv/bin/uvicorn app.main:app --reload`.
4. Open `http://127.0.0.1:8000/admin` and log in with `ADMIN_USERNAME` (defaults to `admin`).

Run checks with `.venv/bin/pytest -q`.

## One-command Docker environment

Docker Compose starts the complete local stack: FastAPI, Liquidsoap, Icecast, MinIO (including creation of the configured bucket), Redis, and persistent Docker volumes. SQLite is intentionally a file in the local `data/` directory—not a container—because it is embedded storage.

The Icecast image uses its currently published `latest` tag because its old `2.4.4` tag is not available in Docker Hub. Pin its digest in a production deployment after validating the image on the target platform.

1. Copy `.env.example` to `.env` and replace every `change-me` value.
2. Put at least one valid local audio file and M3U entry into `data/emergency` before broadcast testing. The emergency playlist is mandatory. The initial repository tracks are mounted as a local test source for the starter playlists.
3. Run `docker compose up --build`.

Open the admin app at `http://localhost:8000/admin`, Icecast status at `http://localhost:8001`, and MinIO Console at `http://localhost:9001`. The stream mount is `http://localhost:8001/radio` once valid audio exists.

Use `docker compose down` to stop services while preserving media/database volumes. `docker compose down -v` also deletes the radio state, MinIO objects and Redis data.

## Broadcast setup

Place a valid, local M3U playlist at `data/emergency/playlist.m3u`; this is the fallback that must remain available without FastAPI or MinIO. Configure your normal local automation playlist at `data/automation/playlist.m3u`. Set valid Icecast credentials in `.env`, then uncomment and adapt the `output.icecast` line in [liquidsoap/radio.liq](liquidsoap/radio.liq). Run Liquidsoap separately from FastAPI.

Do not expose the admin interface without HTTPS and a strong `.env` configuration. In production, set `APP_ENV=production` so session cookies are Secure.

## Planned integrations

MinIO/S3 provides durable media storage with local cache before Liquidsoap playback. AI scripts and TTS become reusable `MediaAsset` records. n8n sends signed, idempotent requests to ICEux—not Telegram directly. Browser live audio will use WebRTC through a small WHIP-compatible ingress and will automatically fall back to automation on disconnect.

## Troubleshooting

- `/ready` returns 503 until `ADMIN_PASSWORD` and a non-default `SESSION_SECRET` are configured.
- A degraded Liquidsoap health state means the control socket is unreachable; it does not prove the audio process is down.
- If audio stops, check the local M3U paths and Liquidsoap logs before inspecting FastAPI.
