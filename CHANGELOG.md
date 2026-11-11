# Changelog

## 0.3.0 - 2026-11-11

- **Siren** entity (Neolink app 0.3.0 or newer): on until switched off or for a duration (30 s by
  default, at most 15 minutes); the app switches it off by itself. The **Siren** button still
  sounds it once.
- Recordings on the SD card copied to Home Assistant (Neolink app 0.3.0 or newer): the **Sync
  recordings** button copies what the media folder lacks from the last 7 days, the
  `neolink.sync_recordings` action takes `hours` and `latest` (only the newest one, e.g. after a
  motion alert). The **Recordings sync** sensor shows idle / copying / failed with the counts and
  the last file. The files land next to the recorded live views, `neolink/<camera>/<YYYY-MM-DD>/`.
- For dashboards: the camera's `sd_recordings` attribute names the WebSocket commands
  `neolink/sd_recordings` (the card's list with signed cover thumbnails, `refresh` searches the card
  again) and `neolink/sd_download` (copies chosen recordings); thumbnails at
  `/api/neolink/sd_thumbnail/<camera>/<day>/<file>.jpg`. Nothing on the card is ever deleted.
- **Auto-copy recordings** switch per camera: the newest SD card recording is copied 5 minutes
  after each motion alert (off by default).
- Talking passes on the app's `{"state": "connecting"}` and `{"state": "connected"}` as they come;
  only the message with `ok` ends the talk (Neolink app 0.2.1 or newer sends the states).

## 0.2.0 - 2026-11-10

- **Record live** switch and **Recording live view** sensor (Neolink app 0.2.0 or newer): watched
  live views are written to Home Assistant's media folder, `neolink/<camera>/<YYYY-MM-DD>/`. The
  switch never wakes the camera; its `recordings_path` attribute tells a dashboard where the files
  are.
- Talking through the camera's speaker (Neolink app 0.2.0 or newer): `/api/neolink/talk/<camera>`
  takes a browser microphone (WebSocket of PCM 16-bit mono, `?rate=<Hz>`, the text `stop` ends it,
  the last message is `{"ok": true}` or `{"ok": false, "error": ...}`) and relays it to the app.
  The camera's `talk_path` attribute tells a dashboard where to talk.

## 0.1.1 - 2026-10-25

- Entity ids are English in every Home Assistant language (`sensor.<camera>_battery` instead of
  `sensor.<kamera>_bateria` in a Polish installation); displayed names stay translated.
- Dark-theme brand images (`dark_icon`, `dark_logo`); `logo@2x.png` is now exactly twice
  the size of `logo.png`.

## 0.1.0

First public release.

- Config flow with automatic discovery of the Neolink app through the Supervisor (host, ports,
  token and RTSP credentials are filled in for you) or manual setup with a bridge address.
- A reinstalled app (for example a local copy replaced by the store version) takes over the
  existing config entry, so devices and entity ids are kept.
- Push-based state over a single WebSocket connection (no polling), with automatic reconnect.
  Adding or removing a camera in the app reloads the entry.
- Camera entity with live view from the bridge RTSP server (works with go2rtc; a 60 s timeout
  gives a sleeping 4G camera time to wake up).
- Still images come only from the bridge cache, so thumbnails and the player poster never wake a
  battery camera. A **Take snapshot** button takes a fresh one on demand.
- **Last snapshot** and **Last event** image entities (the event image is taken after a motion
  notification).
- Sensors: battery level, battery temperature, battery voltage (disabled by default), SD card
  used / free / capacity, 4G signal level, 4G signal value (disabled by default), mobile operator,
  last motion, last detection type (person / vehicle / animal / motion / other), last snapshot time.
- Binary sensors: camera link, charging, motion (from Reolink push notifications, also while the
  camera sleeps).
- Switches: status LED, PIR sensor, reduce false alarms, recording, alarm sound on detection,
  push notifications.
- Selects: infrared mode (auto / on / off), post-detection recording time.
- Number: PIR sensitivity (1-100).
- Buttons: restart, siren, refresh state, take snapshot.
- English and Polish translations.
