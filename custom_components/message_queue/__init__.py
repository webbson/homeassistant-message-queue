"""The Message Queue integration."""

import logging
from pathlib import Path

import voluptuous as vol

from homeassistant.components import panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_DEFAULT_SHOW_SECONDS,
    CONF_QUEUES,
    CONF_ROTATION_INTERVAL,
    DEFAULT_ROTATION_INTERVAL,
    DEFAULT_SHOW_SECONDS,
    DOMAIN,
)
from .queue_manager import QueueManager

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

PUSH_MESSAGE_SCHEMA = vol.Schema({
    vol.Required("queue"): cv.string,
    vol.Required("message"): cv.string,
    vol.Optional("show_seconds"): vol.All(int, vol.Range(min=1)),
    vol.Optional("show_until"): cv.string,
    vol.Optional("message_id"): cv.string,
})

PUSH_MESSAGE_MULTIPLE_SCHEMA = vol.Schema({
    vol.Required("queues"): vol.All(cv.ensure_list, [cv.string]),
    vol.Required("message"): cv.string,
    vol.Optional("show_seconds"): vol.All(int, vol.Range(min=1)),
    vol.Optional("show_until"): cv.string,
    vol.Optional("message_id"): cv.string,
})

PUSH_MESSAGE_ALL_SCHEMA = vol.Schema({
    vol.Required("message"): cv.string,
    vol.Optional("show_seconds"): vol.All(int, vol.Range(min=1)),
    vol.Optional("show_until"): cv.string,
    vol.Optional("message_id"): cv.string,
})

REMOVE_MESSAGE_SCHEMA = vol.Schema({
    vol.Required("message_id"): cv.string,
    vol.Optional("queue"): cv.string,
})

QUEUE_SCHEMA = vol.Schema({
    vol.Required("queue"): cv.string,
})


def _get_manager(hass: HomeAssistant) -> QueueManager | None:
    """Get the first available QueueManager instance."""
    domain_data = hass.data.get(DOMAIN, {})
    for entry_data in domain_data.values():
        if isinstance(entry_data, dict) and "manager" in entry_data:
            return entry_data["manager"]
    return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Message Queue from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    rotation_interval = entry.data.get(
        CONF_ROTATION_INTERVAL, DEFAULT_ROTATION_INTERVAL
    )
    default_show_seconds = entry.data.get(
        CONF_DEFAULT_SHOW_SECONDS, DEFAULT_SHOW_SECONDS
    )

    manager = QueueManager(hass, rotation_interval, default_show_seconds)

    # Initialize configured queues
    for queue_name in entry.options.get(CONF_QUEUES, []):
        manager.ensure_queue(queue_name)

    await manager.async_start()

    hass.data[DOMAIN][entry.entry_id] = {"manager": manager}

    # Register services (once across all entries)
    if not hass.data[DOMAIN].get("_services_registered"):
        _register_services(hass)
        hass.data[DOMAIN]["_services_registered"] = True

    # Register sidebar panel (once across all entries)
    if not hass.data[DOMAIN].get("_panel_registered"):
        await _async_register_panel(hass)
        hass.data[DOMAIN]["_panel_registered"] = True

    # Forward to sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload on options change
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        entry_data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if entry_data and "manager" in entry_data:
            await entry_data["manager"].async_stop()

    return unload_ok


async def _async_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Reload the integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_register_panel(hass: HomeAssistant) -> None:
    """Register the sidebar panel for sending messages."""
    frontend_path = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths([
        StaticPathConfig("/api/message_queue/panel", str(frontend_path), cache_headers=False),
    ])
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name="message-queue-panel",
        sidebar_title="Messages",
        sidebar_icon="mdi:message-text",
        frontend_url_path="message-queue",
        module_url="/api/message_queue/panel/message-queue-panel.js",
        require_admin=False,
    )


def _register_services(hass: HomeAssistant) -> None:
    """Register all message queue services."""

    async def handle_push_message(call: ServiceCall) -> None:
        manager = _get_manager(hass)
        if not manager:
            _LOGGER.error("Message Queue not initialized")
            return
        await manager.async_push_message(
            queue=call.data["queue"],
            message=call.data["message"],
            show_seconds=call.data.get("show_seconds"),
            show_until=call.data.get("show_until"),
            message_id=call.data.get("message_id"),
        )

    async def handle_push_message_to_multiple(call: ServiceCall) -> None:
        manager = _get_manager(hass)
        if not manager:
            _LOGGER.error("Message Queue not initialized")
            return
        await manager.async_push_message_to_multiple(
            queues=call.data["queues"],
            message=call.data["message"],
            show_seconds=call.data.get("show_seconds"),
            show_until=call.data.get("show_until"),
            message_id=call.data.get("message_id"),
        )

    async def handle_push_message_to_all(call: ServiceCall) -> None:
        manager = _get_manager(hass)
        if not manager:
            _LOGGER.error("Message Queue not initialized")
            return
        await manager.async_push_message_to_all(
            message=call.data["message"],
            show_seconds=call.data.get("show_seconds"),
            show_until=call.data.get("show_until"),
            message_id=call.data.get("message_id"),
        )

    async def handle_clear_queue(call: ServiceCall) -> None:
        manager = _get_manager(hass)
        if not manager:
            _LOGGER.error("Message Queue not initialized")
            return
        await manager.async_clear_queue(queue=call.data["queue"])

    async def handle_get_queue_status(call: ServiceCall) -> None:
        manager = _get_manager(hass)
        if not manager:
            _LOGGER.error("Message Queue not initialized")
            return
        status = manager.get_queue_status(queue=call.data["queue"])
        if status:
            hass.bus.async_fire("message_queue_status", status)
            _LOGGER.info("Queue status: %s", status)
    
    async def handle_remove_message(call: ServiceCall) -> none:
        manager = _get_manager(hass)
        if not manager:
            _LOGGER.error("Message Queue not initialized")
            return
        await manager.async_remove_message(
            message_id=call.data.get("message_id"),
            queue=call.data.get("queue"),
        )

    hass.services.async_register(
        DOMAIN, "push_message", handle_push_message, schema=PUSH_MESSAGE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        "push_message_to_multiple",
        handle_push_message_to_multiple,
        schema=PUSH_MESSAGE_MULTIPLE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "push_message_to_all",
        handle_push_message_to_all,
        schema=PUSH_MESSAGE_ALL_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, "clear_queue", handle_clear_queue, schema=QUEUE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "get_queue_status", handle_get_queue_status, schema=QUEUE_SCHEMA
    )

    hass.services.async_register(
        DOMAIN, "remove_message", handle_remove_message, schema=REMOVE_MESSAGE_SCHEMA
    )
