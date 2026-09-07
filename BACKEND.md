# Backend Design

## Package design

`app.main` composes configuration, database and routes. `api` is thin. `auth` owns signed sessions and CSRF protection. `services/liquidsoap.py` is the only gateway to Liquidsoap's telnet control socket. Future repositories isolate SQLAlchemy queries; services orchestrate repositories, storage, providers and queue behavior.

## Persistence roadmap

Core entities are `MediaAsset`, `Playlist`, `PlaylistItem`, `PlayQueueItem`, `PlayHistory`, `ScheduleRule`, `ExternalEvent`, `AIJob`, `TTSGeneration`, `LiveSession`, `SettingMetadata`, and `AuditLog`. SQLite is configured with WAL and foreign keys; migrations use Alembic. Secret values are environment-only.

`PlayQueueItem` has `type`, `source`, `priority`, `scheduled_for`, JSON `payload`, `status`, and `missed_policy`. States: pending, queued, playing, completed, failed, skipped, rescheduled. The EventArbitrator handles emergency, live, manual, scheduled, request and music priority plus insertion policy.

Redis is present in the local Docker stack as a future-compatible cache/job coordination option. Phase 1 deliberately does not depend on it; the API and audio fallback remain valid with Redis unavailable.

## Library and storage

The Library phase registers audio in SQLite and keeps playable files in `data/library` so Liquidsoap can consume stable local paths under `/radio/data/library`. MinIO is used as a durable object-store mirror with object keys like `library/<hash>-<filename>`; upload success is metadata, not a condition for radio playback. If object storage is unavailable, imports remain valid as local-cache assets and report degraded storage metadata.

## Phase 1 endpoints

| Area | Endpoint | Purpose |
|---|---|---|
| Health | `GET /health`, `GET /ready` | liveness/readiness status |
| Auth | `GET/POST /login`, `POST /logout` | one-admin secure session |
| Radio | `GET /api/radio/state`, `POST /api/player/skip` | state and skip command |
| Queue | `GET /api/queue`, `POST /api/queue` | inspect/append local queue |
| Library | `GET /api/library`, `POST /api/library/upload`, `POST /api/library/{id}/automation` | inspect/import audio and add assets to automation |
| Playlists | `GET/POST /api/playlists`, `POST /api/playlists/{id}/items`, `POST /api/playlists/{id}/materialize` | build rotations and write the active local M3U |
| Scheduler | `GET/POST /api/schedules` | persist cron rules with explicit missed-event policy |
| Events | `GET /ws/radio` | state changes |

Later tags: Library, Schedules, AI, Live, Integrations. `POST /api/integrations/n8n/events` validates `X-ICEux-Webhook-Secret` with constant-time comparison and deduplicates `event_id`.

## Integration contracts

Script and TTS providers expose interfaces and return typed results; router code never invokes vendors. Storage writes originals and optional processed versions, then cache makes them locally available before Liquidsoap uses them. `LiquidsoapService` exposes `health`, `get_state`, `enqueue`, `play_now`, `skip`, live/bed methods, and `reload`; graceful unavailability returns degraded control-plane state rather than throwing audio-affecting failures.

## Testing

Use pytest with fake providers and a fake Liquidsoap client. Cover sessions/rate limiting, queue and arbitrator decisions, missed policies, n8n idempotency and live timeout fallback. An integration environment must prove that Liquidsoap stays on local music after FastAPI stops.
