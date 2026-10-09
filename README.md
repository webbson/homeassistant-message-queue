# Message Queue for Home Assistant

A HACS custom integration for Home Assistant that displays rotating messages on screens with configurable expiration times. Manage queues through the UI and send messages from a built-in sidebar panel.

## Features

- **Native HA services** - All services visible in Developer Tools > Services with field descriptions
- **Config flow UI** - Add/remove queues and configure settings through the HA interface
- **Sidebar panel** - Built-in "Messages" sidebar item for sending messages without YAML
- **Multiple independent queues** - One sensor entity per queue
- **Per-message expiration** - Control duration via `show_seconds` or absolute `show_until`
- **Message IDs** - Give a message an optional `message_id` to replace or remove it later
- **Batch messaging** - Push to a single queue, multiple queues, or all queues at once
- **Persistence** - Messages survive Home Assistant restarts
- **Strict queue validation** - Only configured queues accept messages (no accidental creation)

## Installation

### HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=webbson&repository=homeassistant-message-queue&category=Integration)

Or manually:

1. Open HACS in Home Assistant
2. Click the three dots menu > Custom repositories
3. Add this repository URL, category: Integration
4. Search for "Message Queue" and install
5. Restart Home Assistant

### Manual

1. Copy `custom_components/message_queue/` to your HA `config/custom_components/` directory
2. Restart Home Assistant

## Setup

1. Go to **Settings > Devices & Services > Add Integration**
2. Search for **Message Queue**
3. Configure defaults:
   - **Rotation interval** - How often to check for expired messages (default: 5 seconds)
   - **Default message duration** - How long messages display if no duration specified (default: 3600 seconds)
4. Click **Configure** on the integration to add queues

### Managing Queues

Click **Configure** on the Message Queue integration to:
- **Add queue** - Enter a queue name (lowercase, numbers, underscores)
- **Remove queue** - Select a queue to remove
- **Settings** - Change rotation interval or default duration

Each queue creates a sensor entity: `sensor.message_queue_{name}`

## Usage

### Sidebar Panel

Click **Messages** in the sidebar to open the built-in message sender. Select a queue, type a message, choose an expiration, and send.

### Service Calls

#### Push to a single queue

```yaml
service: message_queue.push_message
data:
  queue: living_room_screen
  message: "Welcome Home!"
  show_seconds: 300
```

#### Push to multiple queues

```yaml
service: message_queue.push_message_to_multiple
data:
  queues:
    - living_room_screen
    - kitchen_screen
  message: "Everyone home!"
  show_seconds: 300
```

#### Push to all queues

```yaml
service: message_queue.push_message_to_all
data:
  message: "System update in 5 minutes"
  show_seconds: 300
```

#### Absolute expiration time

```yaml
service: message_queue.push_message
data:
  queue: living_room_screen
  message: "Meeting at 3 PM"
  show_until: "2024-03-03T15:00:00"
```

#### Replace or remove a message by ID

Pushing a message with a `message_id` that is already in the queue replaces the old message.

```yaml
service: message_queue.push_message
data:
  queue: living_room_screen
  message: "Washing machine: 10 minutes left"
  message_id: washing_machine
```

Remove it again by ID. Leave out `queue` to remove it from all queues.

```yaml
service: message_queue.remove_message
data:
  message_id: washing_machine
  queue: living_room_screen
```

#### Clear a queue

```yaml
service: message_queue.clear_queue
data:
  queue: living_room_screen
```

#### Get queue status

```yaml
service: message_queue.get_queue_status
data:
  queue: living_room_screen
```

Status is logged and fired as a `message_queue_status` event.

## Sensor Entities

Each queue creates a sensor: `sensor.message_queue_{queue_name}`

**State:** Current message text (empty string when queue is empty)

**Attributes:**
| Attribute | Description |
|-----------|-------------|
| `expires_at` | ISO timestamp when current message expires |
| `message_id` | ID of the current message, if one was given |
| `queue_position` | Position of current message (always 1) |
| `queue_length` | Total messages in the queue |

## Service Reference

| Service | Required Params | Optional Params |
|---------|----------------|-----------------|
| `push_message` | `queue`, `message` | `show_seconds`, `show_until`, `message_id` |
| `push_message_to_multiple` | `queues`, `message` | `show_seconds`, `show_until`, `message_id` |
| `push_message_to_all` | `message` | `show_seconds`, `show_until`, `message_id` |
| `remove_message` | `message_id` | `queue` |
| `clear_queue` | `queue` | |
| `get_queue_status` | `queue` | |

## Automation Example

```yaml
automation:
  - alias: "Display arrival message"
    trigger:
      platform: state
      entity_id: binary_sensor.front_door
      to: "on"
    action:
      service: message_queue.push_message
      data:
        queue: living_room_screen
        message: "Someone arrived home"
        show_seconds: 30
```

## Persistence

Messages are stored in Home Assistant's `.storage/` directory and survive restarts. Expired messages are cleaned up automatically during the first rotation cycle after startup.

## Disabling History and Logging

Message queue sensors update frequently and produce a lot of state changes. To avoid bloating your database, exclude them from the recorder:

```yaml
# configuration.yaml
recorder:
  exclude:
    entity_globs:
      - sensor.message_queue_*
```

If you also want to hide them from the logbook:

```yaml
# configuration.yaml
logbook:
  exclude:
    entity_globs:
      - sensor.message_queue_*
```

After editing `configuration.yaml`, restart Home Assistant for the changes to take effect.

## Troubleshooting

### Services not appearing
- Ensure the integration is installed and configured (Settings > Devices & Services)
- Restart Home Assistant after installation

### Messages not showing on sensors
- Verify the queue exists (added via Configure on the integration)
- Pushing to a non-existent queue name is rejected with an error log

### Sidebar panel not appearing
- Reload the browser page (Ctrl+Shift+R)
- Verify the integration is loaded in Settings > Devices & Services

## License

MIT
