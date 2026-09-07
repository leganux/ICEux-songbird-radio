# Frontend Design

The UI is server-rendered HTML with Bootstrap 4.6, custom CSS, jQuery only where it reduces complexity, and a native WebSocket. It is a responsive operational console—not an SPA.

## Layout

The top bar shows ICEux Songbird Radio, on-air state, mount and listeners. The dashboard presents Deck A (now playing), Deck B (next), queue, history, health and Live Control. Navigation expands to Library, Cart Wall, Scheduler, AI Studio, Live Control and Settings.

The main dashboard is the canonical UI guide for upcoming phases. It keeps SAM Broadcaster's operational logic without copying its visual design: a left navigation rail, broadcast status bar, Deck A, Deck B, clock, library, play queue, cart wall, history, live/microphone, mixer, playlists, scheduler, AI Studio and external n8n activity. Unimplemented phase controls may render as visible placeholders, but they must not claim working audio behavior until their backend path exists.

Decks expose title, artist, type, progress and source. Queue/history update from `queue_changed`/`history_changed`; player fields update from `radio_state`, `now_playing`, and `next_track`. The client reconnects WebSocket with backoff and displays stale state without repeatedly polling.

## Interaction rules

Dangerous live actions ask for confirmation. Forms show field errors inline and never receive secret values. The library will organize media by typed tabs with upload, search, preview, metadata, play/next and scheduling actions. Cart buttons support now, overlay and next when their asset policy allows it.

Every new feature should land in its already-visible panel first, then wire the action progressively. Examples: n8n activity goes into External / n8n Events, TTS generation goes into AI Studio, browser microphone state goes into Live / Microphone and Mixer, and priority arbitration becomes visible in Play Queue and Deck B.

Live Control will request microphone access only after the administrator presses Go Live. It will offer mic-only, current-music and custom-bed modes, approximate VU meters, gain, bed selection and ducking controls. A browser disconnect is visibly reported, but the audio plane—not the UI—returns to automation.

## Responsive behavior

Desktop uses the two-deck operational grid. Below tablet width, panels stack in priority order: on-air/current, next, live controls, queue, health/history. Controls remain touch-sized and status is always readable.
