# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HACS custom integration for Home Assistant. Displays rotating messages on screen queues with configurable expiration, persistence across restarts, batch messaging, and a built-in sidebar panel for sending messages. Distributed via HACS.

## Development

No build system, package manager, or test framework. The integration is pure Python (plus one vanilla JS file for the sidebar panel) with no external dependencies beyond Home Assistant core.

### Installation & Testing

1. Copy `custom_components/message_queue/` to a HA instance's `config/custom_components/`
2. Restart Home Assistant
3. Add integration: Settings > Devices & Services > Add Integration > "Message Queue"
4. Add queues via Configure on the integration
5. Test via Developer Tools > Services or the "Messages" sidebar panel

### Verifying Changes

- Check HA logs for: `Message Queue Manager ready (rotation: Xs, default show: Xs)`
- Developer Tools > Services should list all 6 `message_queue.*` services
- Developer Tools > States should show `sensor.message_queue_{name}` entities
- "Messages" sidebar item should load the send message form

## Architecture

### File Structure (`custom_components/message_queue/`)

| File | Purpose |
|------|---------|
| `__init__.py` | Integration setup, service registration, sidebar panel registration |
| `const.py` | Constants (DOMAIN, storage keys, signals, config keys) |
| `config_flow.py` | Config flow (initial setup) + options flow (add/remove queues, settings) |
| `queue_manager.py` | Core queue logic: push, clear, rotate, persist, expiration |
| `sensor.py` | Sensor entities (one per queue), updated via dispatcher signals |
| `services.yaml` | Service field descriptions for the HA UI |
| `manifest.json` | Integration metadata, version, HA compatibility |
| `strings.json` | Config flow UI strings |
| `translations/en.json` | English translations (mirrors strings.json) |
| `frontend/message-queue-panel.js` | Sidebar panel web component |

### Data Flow

```
Config flow → stores queue names + settings in config entry
async_setup_entry → creates QueueManager, registers services + panel, forwards to sensor platform
Service call → QueueManager validates queue → updates deque → dispatches signal → persists to .storage/
Timer (async_track_time_interval) → removes expired from all queues → rotates deques → dispatches updates → persists
Sensor → listens for SIGNAL_QUEUE_UPDATED → reads from QueueManager → writes HA state
Panel → reads hass.states for queue sensors → calls hass.callService() for actions
```

### Key Classes

**`QueueManager`** (`queue_manager.py`) — manages all queue state:
- `self.queues: dict[str, deque]` mapping queue names to message deques
- Each message: `{"text": str, "expires_at": datetime, "message_id": str | None}`
- Persistence via `homeassistant.helpers.storage.Store`
- Rotation via `homeassistant.helpers.event.async_track_time_interval`
- Sensor updates via `homeassistant.helpers.dispatcher.async_dispatcher_send`

**`MessageQueueSensor`** (`sensor.py`) — one per queue:
- `unique_id`: `message_queue_{queue_name}`
- State: current message text
- Attributes: `expires_at`, `message_id`, `queue_position`, `queue_length`

### Services

| Service | Key params |
|---------|-----------|
| `message_queue.push_message` | `queue`, `message`, `show_seconds` or `show_until`, optional `message_id` |
| `message_queue.push_message_to_multiple` | `queues` (list), `message`, `show_seconds` or `show_until`, optional `message_id` |
| `message_queue.push_message_to_all` | `message`, `show_seconds` or `show_until`, optional `message_id` |
| `message_queue.remove_message` | `message_id`, optional `queue` (blank = all queues) |
| `message_queue.clear_queue` | `queue` |
| `message_queue.get_queue_status` | `queue` (fires `message_queue_status` event) |

### Expiration

Messages expire via relative time (`show_seconds`) or absolute time (`show_until` as ISO datetime string). If neither is provided, `default_show_seconds` from config is used.

### Queue Management

Queues are **strictly configured** — only queues added through the config flow options UI are valid. Pushing to a non-existent queue logs an error and is rejected. Queues are not auto-created.

## HACS Distribution

- `hacs.json` in repo root defines HACS metadata
- `manifest.json` defines HA integration metadata with `version` field
- Repository must have at least one GitHub release tag matching `manifest.json` version
