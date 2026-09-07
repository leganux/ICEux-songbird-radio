# ICEux Songbird Radio — Agent Guide

ICEux is a personal, web-based Icecast2 automation and live-broadcasting control plane. Its product rule is absolute: **Audio continuity has higher priority than every secondary feature.**

## Non-negotiable boundaries

- FastAPI is the control plane: auth, metadata, scheduling, queue arbitration, APIs and UI.
- Liquidsoap is the audio plane: playlists, fallback, transitions, mixing, ducking and Icecast output.
- Icecast2 is distribution only.
- **Never make the audio fallback dependent on FastAPI.** Liquidsoap must retain a local emergency playlist and continue if this application exits.
- Do not put DSP, direct AI calls, or Liquidsoap socket commands in API routers.
- No user system: one admin credential is read only from environment variables; never log or persist passwords.

## Stack and conventions

Python 3.11+, FastAPI, SQLAlchemy, SQLite (WAL + foreign keys), Jinja templates, Bootstrap 4.6, jQuery and native WebSockets. Use typed Python, UTC timestamps, explicit service boundaries and structured logging. Keep modules small and avoid premature microservices or Redis.

## Repository map

- `app/api`: thin HTTP and WebSocket routes.
- `app/services`: orchestration, including `LiquidsoapService`.
- `app/queue`: `QueueManager` and `EventArbitrator`; all playable events flow through them.
- `app/models`: persistence; `app/schemas`: request/response contracts.
- `app/templates` and `app/static`: server-rendered administration UI.
- `liquidsoap/radio.liq`: independently running resilient audio graph.
- `data/emergency`: local audio fallback, never served as a remote dependency.
- `tests`: unit tests first for arbitration, auth and service contracts.

## Safe changes

When changing Liquidsoap, preserve the `dynamic -> automation -> emergency` fallback chain, test its syntax with the installed Liquidsoap version, and do not reload a live script without an operational rollback plan. New scheduler sources must declare a missed policy. New queue sources require a priority and an insertion policy. New TTS/Script providers implement their provider interface and are invoked only through services.

## Testing strategy

Run unit tests before changes are handed off. Test queue ordering, live missed-event handling, n8n idempotency, auth and provider failures with fakes. The critical integration assertion is: stopping FastAPI does not stop Liquidsoap's music source.
