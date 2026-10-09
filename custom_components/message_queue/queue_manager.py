"""Queue manager for the Message Queue integration."""

import logging
from collections import deque
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store

from .const import (
    SIGNAL_QUEUE_UPDATED,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


class QueueManager:
    """Manages message queues with expiration, rotation, and persistence."""

    def __init__(
        self,
        hass: HomeAssistant,
        rotation_interval: int,
        default_show_seconds: int,
    ) -> None:
        self.hass = hass
        self.queues: dict[str, deque] = {}
        self.rotation_interval = rotation_interval
        self.default_show_seconds = default_show_seconds
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._unsub_timer = None

    async def async_start(self) -> None:
        """Load persisted state and start the rotation timer."""
        await self._async_load_state()
        self._unsub_timer = async_track_time_interval(
            self.hass,
            self._async_rotate,
            timedelta(seconds=self.rotation_interval),
        )
        _LOGGER.info(
            "Message Queue Manager ready (rotation: %ds, default show: %ds)",
            self.rotation_interval,
            self.default_show_seconds,
        )

    async def async_stop(self) -> None:
        """Cancel the rotation timer."""
        if self._unsub_timer:
            self._unsub_timer()
            self._unsub_timer = None

    def ensure_queue(self, queue_name: str) -> None:
        """Initialize an empty deque for a queue if it doesn't exist."""
        if queue_name not in self.queues:
            self.queues[queue_name] = deque()

    def remove_queue(self, queue_name: str) -> None:
        """Remove a queue entirely."""
        self.queues.pop(queue_name, None)

    async def async_push_message(
        self,
        queue: str,
        message: str,
        show_seconds: int | None = None,
        show_until: str | None = None,
        message_id: str | None = None,
    ) -> None:
        """Push a message to a single queue."""
        if queue not in self.queues:
            _LOGGER.error("Queue '%s' does not exist", queue)
            return

        # Find and remove existing message with this id, if any exist.
        # Linear search is probably not great... but unless queue lengths are crazy
        # this should be fine.
        if message_id is not None:
            for i in range(len(self.queues[queue])):
                if self.queues[queue][i].get("message_id") == message_id:
                    del self.queues[queue][i]
                    _LOGGER.debug(
                        "Removed previous message with message id '%s' from '%s'", message_id, queue
                    )
                    break

        expires_at = self._calculate_expiration(show_seconds, show_until)
        if expires_at is None:
            return        

        self.queues[queue].append({"text": message, "expires_at": expires_at, "message_id": message_id,})
        _LOGGER.debug(
            "Pushed to '%s': '%s' (expires %s)", queue, message, expires_at.isoformat()
        )
        async_dispatcher_send(self.hass, SIGNAL_QUEUE_UPDATED, queue)
        await self._async_save_state()

    async def async_push_message_to_multiple(
        self,
        queues: list[str],
        message: str,
        show_seconds: int | None = None,
        show_until: str | None = None,
        message_id: str | None = None,
    ) -> None:
        """Push a message to multiple queues."""
        expires_at = self._calculate_expiration(show_seconds, show_until)
        if expires_at is None:
            return

        pushed = []
        for queue_name in queues:
            if queue_name not in self.queues:
                _LOGGER.error("Queue '%s' does not exist, skipping", queue_name)
                continue
            # Find and remove existing message with this id, if any exist.
            # Linear search is probably not great... but unless queue lengths are crazy
            # this should be fine.
            if message_id is not None:
                for i in range(len(self.queues[queue])):
                    if self.queues[queue][i].get("message_id") == message_id:
                        del self.queues[queue][i]
                        _LOGGER.debug(
                            "Removed previous message with message id '%s' from '%s'", message_id, queue
                        )
                        break
            self.queues[queue_name].append({"text": message, "expires_at": expires_at, "message_id": message_id,})
            async_dispatcher_send(self.hass, SIGNAL_QUEUE_UPDATED, queue_name)
            pushed.append(queue_name)

        if pushed:
            _LOGGER.debug("Pushed message to %d queues: %s", len(pushed), ", ".join(pushed))
            await self._async_save_state()

    async def async_push_message_to_all(
        self,
        message: str,
        show_seconds: int | None = None,
        show_until: str | None = None,
        message_id: str | None = None,
    ) -> None:
        """Push a message to all configured queues."""
        if not self.queues:
            _LOGGER.warning("No queues exist to push message to")
            return

        expires_at = self._calculate_expiration(show_seconds, show_until)
        if expires_at is None:
            return

        for queue_name, queue in self.queues.items():
            # Find and remove existing message with this id, if any exist.
            # Linear search is probably not great... but unless queue lengths are crazy
            # this should be fine.
            if message_id is not None:
                for i in range(len(self.queues[queue])):
                    if self.queues[queue][i].get("message_id") == message_id:
                        del self.queues[queue][i]
                        _LOGGER.debug(
                            "Removed previous message with message id '%s' from '%s'", message_id, queue
                        )
                        break
            queue.append({"text": message, "expires_at": expires_at, "message_id": message_id,})
            async_dispatcher_send(self.hass, SIGNAL_QUEUE_UPDATED, queue_name)

        _LOGGER.debug("Pushed message to all %d queues", len(self.queues))
        await self._async_save_state()

    async def async_remove_message(
        self,        
        message_id: str,
        queue: str | None = None,
    ) -> None:
        """Remove a message by ID from a single queue or all queues."""
        found = False
        if queue is not None:
            if queue not in self.queues:
                _LOGGER.error("Queue '%s' does not exist", queue)
                return
            for i in range(len(self.queues[queue])):
                if self.queues[queue][i].get("message_id") == message_id:
                    del self.queues[queue][i]
                    _LOGGER.debug(
                        "Removed previous message with message id '%s' from '%s'", message_id, queue
                    )
                    found = True
                    break
        else:
            for queue_name in self.queues.keys():
                # Find and remove existing message with this id, if any exist.
                # Linear search is probably not great... but unless queue lengths are crazy
                # this should be fine.            
                for i in range(len(self.queues[queue_name])):
                    if self.queues[queue_name][i].get("message_id") == message_id:
                        del self.queues[queue_name][i]
                        _LOGGER.debug(
                            "Removed previous message with message id '%s' from '%s'", message_id, queue
                        )
                        found = True
                        break                            
        if not found:
            _LOGGER.debug(
                "Could not find a message with message id '%s'", message_id
            )
        await self._async_save_state()       

    async def async_clear_queue(self, queue: str) -> None:
        """Clear all messages from a queue."""
        if queue not in self.queues:
            _LOGGER.error("Queue '%s' does not exist", queue)
            return

        self.queues[queue].clear()
        _LOGGER.debug("Cleared queue '%s'", queue)
        async_dispatcher_send(self.hass, SIGNAL_QUEUE_UPDATED, queue)
        await self._async_save_state()

    def get_queue_status(self, queue: str) -> dict | None:
        """Get status of a queue."""
        if queue not in self.queues:
            _LOGGER.error("Queue '%s' does not exist", queue)
            return None

        now = datetime.now()
        messages = []
        for i, msg in enumerate(self.queues[queue]):
            messages.append({
                "index": i,
                "text": msg["text"],
                "expires_at": msg["expires_at"].isoformat(),
                "expired": now > msg["expires_at"],
            })

        return {
            "queue_name": queue,
            "length": len(self.queues[queue]),
            "messages": messages,
        }

    def get_current_message(self, queue: str) -> dict | None:
        """Get the current (front) message for a queue, or None if empty."""
        if queue not in self.queues or not self.queues[queue]:
            return None
        return self.queues[queue][0]

    def get_queue_length(self, queue: str) -> int:
        """Get the number of messages in a queue."""
        if queue not in self.queues:
            return 0
        return len(self.queues[queue])

    def _calculate_expiration(
        self, show_seconds: int | None, show_until: str | None
    ) -> datetime | None:
        """Calculate expiration datetime from show_seconds or show_until."""
        if show_until:
            try:
                return datetime.fromisoformat(show_until)
            except ValueError:
                _LOGGER.error(
                    "Invalid show_until format: %s. Use ISO format (e.g., 2024-03-03T18:30:00)",
                    show_until,
                )
                return None
        if show_seconds is not None:
            return datetime.now() + timedelta(seconds=show_seconds)
        return datetime.now() + timedelta(seconds=self.default_show_seconds)

    async def _async_rotate(self, now: datetime) -> None:
        """Rotation callback: remove expired messages and rotate queues."""
        expired_any = False
        current_time = datetime.now()

        for queue_name in list(self.queues.keys()):
            queue = self.queues[queue_name]
            if not queue:
                continue

            # Remove all expired messages from the queue
            original_length = len(queue)
            self.queues[queue_name] = deque(
                msg for msg in queue if current_time <= msg["expires_at"]
            )
            queue = self.queues[queue_name]
            expired_count = original_length - len(queue)

            if expired_count:
                _LOGGER.debug(
                    "Removed %d expired message(s) from '%s'",
                    expired_count, queue_name,
                )
                expired_any = True

            # Rotate to show the next message
            if len(queue) > 1:
                queue.rotate(-1)
                async_dispatcher_send(self.hass, SIGNAL_QUEUE_UPDATED, queue_name)
            elif expired_count:
                # Queue content changed due to expiration, update sensor
                async_dispatcher_send(self.hass, SIGNAL_QUEUE_UPDATED, queue_name)

        if expired_any:
            await self._async_save_state()

    async def _async_load_state(self) -> None:
        """Load persisted queue data from storage."""
        data = await self._store.async_load()
        if not data:
            _LOGGER.debug("No persisted queue data found")
            return

        for queue_name, messages in data.items():
            if queue_name not in self.queues:
                # Only load queues that are currently configured
                continue
            for msg in messages:
                self.queues[queue_name].append({
                    "text": msg["text"],
                    "expires_at": datetime.fromisoformat(msg["expires_at"]),
                })

        _LOGGER.debug("Loaded persisted state for %d queues", len(data))

    async def _async_save_state(self) -> None:
        """Persist queue data to storage."""
        data = {}
        for queue_name, queue in self.queues.items():
            data[queue_name] = [
                {
                    "text": msg["text"],
                    "expires_at": msg["expires_at"].isoformat(),
                }
                for msg in queue
            ]
        await self._store.async_save(data)
