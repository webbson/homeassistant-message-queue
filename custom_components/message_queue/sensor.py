"""Sensor platform for the Message Queue integration."""

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_QUEUES, DOMAIN, SIGNAL_QUEUE_UPDATED

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Message Queue sensors from a config entry."""
    manager = hass.data[DOMAIN][entry.entry_id]["manager"]
    queue_names = entry.options.get(CONF_QUEUES, [])

    entities = [
        MessageQueueSensor(manager, queue_name, entry.entry_id)
        for queue_name in queue_names
    ]

    async_add_entities(entities)


class MessageQueueSensor(SensorEntity):
    """Sensor entity representing a single message queue."""

    _attr_has_entity_name = True

    def __init__(self, manager, queue_name: str, entry_id: str) -> None:
        self._manager = manager
        self._queue_name = queue_name
        self._attr_unique_id = f"message_queue_{queue_name}"
        self._attr_name = queue_name.replace("_", " ").title()
        self._attr_icon = "mdi:message-text"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": "Message Queue",
            "manufacturer": "Message Queue",
            "model": "Queue Manager",
        }

    @property
    def native_value(self) -> str | None:
        """Return the current message text."""
        msg = self._manager.get_current_message(self._queue_name)
        if msg is None:
            return ""
        return msg["text"]

    @property
    def extra_state_attributes(self) -> dict:
        """Return queue attributes."""
        msg = self._manager.get_current_message(self._queue_name)
        length = self._manager.get_queue_length(self._queue_name)

        if msg is None:
            return {
                "expires_at": None,
                "message_id": None,
                "queue_position": 0,
                "queue_length": 0,
            }

        return {
            "expires_at": msg["expires_at"].isoformat(),
            "message_id": msg.get("message_id"),
            "queue_position": 1,
            "queue_length": length,
        }

    async def async_added_to_hass(self) -> None:
        """Register dispatcher listener when entity is added."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_QUEUE_UPDATED,
                self._handle_queue_update,
            )
        )

    @callback
    def _handle_queue_update(self, queue_name: str) -> None:
        """Handle a queue update signal."""
        if queue_name == self._queue_name:
            self.async_write_ha_state()
