# Changelog

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
