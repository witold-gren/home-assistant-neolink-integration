# Neolink for Home Assistant

🇵🇱 [Polska wersja](README.pl.md)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)

A Home Assistant integration for **Reolink battery and 4G cameras that have no local API**, such
as the Reolink Go Plus or Go G330. These cameras cannot be added with the built-in Reolink
integration. This integration talks to them through
[Neolink](https://github.com/QuantumEntangledAndy/neolink), using a fork with a WebSocket API that
runs as the **Neolink** app (add-on):
[home-assistant-neolink-addon](https://github.com/witold-gren/home-assistant-neolink-addon).

No MQTT is needed. State is pushed over a single WebSocket connection, and the integration is built
so that a battery camera is woken only when you actually ask for something.

```
Reolink camera ──Baichuan (LAN / P2P / 4G)──► Neolink app ──WebSocket──► neolink integration ──► entities
                                               │  └─ RTSP ──► go2rtc / stream ──► live view
                                               └─ Supervisor discovery ──► "Discovered: Neolink"
```

## Requirements

- Home Assistant 2026.2 or newer.
- The **Neolink** app from
  [home-assistant-neolink-addon](https://github.com/witold-gren/home-assistant-neolink-addon),
  installed, configured with your cameras and running. Without the Supervisor (for example Home
  Assistant Container) you can run the same Neolink fork yourself and add it manually.
- For live view: the `stream` integration or go2rtc (both are part of the default configuration).

## Installation

### HACS (recommended)

1. In HACS open the menu (three dots) → **Custom repositories**.
2. Add `https://github.com/witold-gren/home-assistant-neolink-integration` with the category
   **Integration**.
3. Search for **Neolink**, download it and restart Home Assistant.

### Manual

Copy `custom_components/neolink` from this repository to `custom_components/neolink` in your Home
Assistant configuration directory and restart Home Assistant.

## Configuration

### Automatic discovery

When the Neolink app is running, the Supervisor announces it to Home Assistant. Go to
**Settings → Devices & services**; a discovered **Neolink** shows up there. Confirm it and you are
done: the address, ports, token and RTSP credentials come from the app.

If the app restarts with a new address or token, the existing entry is updated automatically. If
you reinstall the app (for example replace a local copy with the store version), the new
installation takes over the existing entry, so your devices and entity ids stay the same.

### Manual setup

**Settings → Devices & services → Add integration → Neolink**, then fill in:

| Field | Description |
|---|---|
| Host | Address of the Neolink bridge. |
| WebSocket port | Port of the WebSocket API (default `3002`). |
| Token | API token configured in the bridge; leave empty if none. |
| RTSP port | Port of the bridge RTSP server (default `8554`). |
| RTSP username / password | RTSP credentials, if the bridge requires them. |

## Entities

Entity IDs are English in every Home Assistant language (e.g. `sensor.<camera>_battery` also in
a Polish installation, not `sensor.<kamera>_bateria`); the displayed names are translated.

Each camera configured in the app becomes a device. Entities are created only for features the
camera and the bridge report.

| Entity | Type | Notes |
|---|---|---|
| Camera | camera | Live view from the bridge RTSP server; the still image comes from the bridge cache only. |
| Last snapshot, Last event | image | From the bridge cache. *Last event* is the picture taken after a motion notification. |
| Battery | sensor | Battery level in %. |
| Battery temperature, Battery voltage | sensor | Diagnostic; voltage is disabled by default. |
| Last motion | sensor | Time of the last motion push notification. |
| Last detection | sensor | What triggered the last notification: person, vehicle, animal, motion or other. |
| Last snapshot | sensor | Time of the cached snapshot (diagnostic). |
| SD card used, SD card free, SD card capacity | sensor | Read when the camera connects; unknown when no card is mounted. |
| 4G signal, 4G signal value, Mobile operator | sensor | 4G cameras only; signal value is disabled by default. |
| Motion | binary sensor | From Reolink push notifications, also while the camera sleeps. |
| Camera link, Charging | binary sensor | Diagnostic. |
| Status LED, PIR sensor, Reduce false alarms, Recording, Alarm sound on detection, Push notifications | switch | Camera settings. |
| Infrared | select | Night vision: auto, on or off. |
| Post-detection recording | select | How long the camera keeps recording after a detection (for example 8 / 15 / 30 s). |
| PIR sensitivity | number | 1-100, as in the Reolink app. |
| Restart, Siren, Refresh state, Take snapshot | button | One-shot commands. |

## Battery cameras

Battery cameras spend most of their time asleep, and every wake-up costs battery. The integration
is designed around that:

- **Reading never wakes the camera.** Sensors show the last values the bridge received; the camera
  entity, dashboard thumbnails and the *Last snapshot* / *Last event* images are served from the
  bridge cache. If there is no cached picture yet, no image is shown rather than waking the camera.
- **Only explicit actions wake it:** opening the live view, pressing a button, or changing a
  switch, select or number. The bridge disconnects the camera again when it is idle.
- **Fresh stills on demand:** press **Take snapshot**. The bridge also refreshes the cached
  picture whenever the camera is awake anyway (live view, commands, motion).
- **Motion without waking:** motion comes from Reolink push notifications, so it works while the
  camera sleeps. Push notifications must be enabled on the camera (*Push notifications* switch)
  and in the Neolink app.
- Waking a 4G camera through the Reolink servers can take 10-20 seconds, so the live view and
  commands may need a moment.

Entities stay available while the camera sleeps; they become unavailable only when the bridge
itself is unreachable.

## Limitations

- Requires the Neolink fork with the WebSocket API; the original Neolink (MQTT) is not supported.
- Live view uses the sub stream.
- The mobile operator name is known only for a few operators; others are shown as the numeric
  MCC+MNC code.
- No playback of recordings from the SD card.
- Not affiliated with or endorsed by Reolink. Reolink is a trademark of its owner; the integration
  icon is based on the Reolink mark from
  [home-assistant/brands](https://github.com/home-assistant/brands) with an "N" in place of the "R".

## Development

```bash
python3.13 -m venv .venv && .venv/bin/pip install -r requirements_test.txt
.venv/bin/ruff format . && .venv/bin/ruff check .
.venv/bin/python -m pytest
```

The tests start a fake bridge (a real WebSocket server on localhost) that speaks the same protocol
as the Neolink fork. `deploy.sh` copies the integration to a Home Assistant config directory
mounted over Samba (`CONFIG=/path/to/config ./deploy.sh`).

## License

MIT, see [LICENSE](LICENSE).
