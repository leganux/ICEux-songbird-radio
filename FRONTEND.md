# Frontend Design

The UI is server-rendered HTML with Bootstrap 4.6, custom CSS, jQuery only where it reduces complexity, and a native WebSocket. It is a responsive operational console—not an SPA.

## Layout

The top bar shows ICEux Songbird Radio, on-air state, mount and listeners. The dashboard presents Deck A (now playing), Deck B (next), queue, history, health and Live Control. Navigation expands to Library, Cart Wall, Scheduler, AI Studio, Live Control and Settings.

Decks expose title, artist, type, progress and source. Queue/history update from `queue_changed`/`history_changed`; player fields update from `radio_state`, `now_playing`, and `next_track`. The client reconnects WebSocket with backoff and displays stale state without repeatedly polling.

## Interaction rules

Dangerous live actions ask for confirmation. Forms show field errors inline and never receive secret values. The library will organize media by typed tabs with upload, search, preview, metadata, play/next and scheduling actions. Cart buttons support now, overlay and next when their asset policy allows it.

Live Control will request microphone access only after the administrator presses Go Live. It will offer mic-only, current-music and custom-bed modes, approximate VU meters, gain, bed selection and ducking controls. A browser disconnect is visibly reported, but the audio plane—not the UI—returns to automation.

## Responsive behavior

Desktop uses the two-deck operational grid. Below tablet width, panels stack in priority order: on-air/current, next, live controls, queue, health/history. Controls remain touch-sized and status is always readable.
