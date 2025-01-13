"""Sensor for Spotify Sensor Extras."""

from typing import Any, Dict, Optional
import asyncio
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity import DeviceInfo
from . import HomeAssistantSpotifyData
from .const import DOMAIN, _LOGGER


class SpotifyExtras(Entity):
    """Spotify Extras Sensor."""

    platform = "sensor"
    config_flow_class = None

    _attr_icon = "mdi:newspaper-variant"

    def __init__(
        self, data: HomeAssistantSpotifyData, user_id: str, name: str, user_country: str
    ):
        """Initialize the sensor."""
        self._id = user_id
        self._name = name
        self.data = data
        self._user_country = user_country
        self._state = None
        self._extra_attributes: Dict[str, Any] = {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, user_id)},
        )

    async def async_added_to_hass(self):
        """Register the service when the entity is added to hass."""
        self.hass.services.async_register(DOMAIN, "spotify_extras", self.spotify_extras)

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Spotify Extras"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state or "No Current Song"

    @property
    def unique_id(self):
        """Return the unique ID for the sensor."""
        return f"SpotifyExtras{self._id}"

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the sensor."""
        return self._extra_attributes

    async def spotify_extras(self, call):
        """Get Queue and Recent items."""
        # Cooldown period before fetching queue
        await asyncio.sleep(1)

        try:
            # Fetch queue and 30 recent items concurrently
            spotify_queue, spotify_recent = await asyncio.gather(
                self.hass.async_add_executor_job(self.data.client.queue),
                self.hass.async_add_executor_job(
                    self.data.client.current_user_recently_played, 30
                ),
            )
        except Exception as err:
            _LOGGER.error("Spotify Queue and Recent Error: %s", err)
            spotify_queue = {"queue": []}
            spotify_recent = {"items": []}

        queue_list = self._build_queue_list(spotify_queue)
        recent_list = self._build_recent_list(spotify_recent)

        # Bulk check if queue items are in the user's library
        if queue_list:
            await self._check_if_saved(queue_list)

        # Bulk check if recent items are in the user's library
        if recent_list:
            await self._check_if_saved(recent_list)

        _LOGGER.debug("Queue and Recent List Retrieved")

        self._state = "Queue and Recent"
        self._extra_attributes = {"queue": queue_list, "recent": recent_list}
        self.async_write_ha_state()

    def _build_queue_list(self, spotify_queue: Dict[str, Any]) -> list[Dict[str, Any]]:
        """Build the queue list from the Spotify queue data."""
        queue_list = []
        for track in spotify_queue.get("queue", []):
            try:
                track_dict = {
                    "trackname": track["name"],
                    "trackartist": track["artists"][0]["name"],
                    "trackuri": track["uri"],
                    "trackid": track["id"],
                    "image": track["album"].get("images", [{}])[0].get("url"),
                }
                queue_list.append(track_dict)
            except Exception as e:
                _LOGGER.debug(f"Error processing track in queue: {e}")
        return queue_list

    def _build_recent_list(
        self, spotify_recent: Dict[str, Any]
    ) -> list[Dict[str, Any]]:
        """Build the recent list from the Spotify recent data."""
        recent_list = []
        for item in spotify_recent.get("items", []):
            try:
                track_dict = {
                    "trackname": item["track"]["name"],
                    "trackartist": item["track"]["artists"][0]["name"],
                    "trackuri": item["track"]["uri"],
                    "image": item["track"]["album"].get("images", [{}])[0].get("url"),
                    "played": item["played_at"],
                }
                recent_list.append(track_dict)
            except Exception as e:
                _LOGGER.debug(f"Error processing recent track: {e}")
        return recent_list

    async def _check_if_saved(self, tracks: list[Dict[str, Any]]):
        """Check if tracks are saved in the user's library."""
        uris = [track["trackuri"] for track in tracks]
        if not uris:
            _LOGGER.warning("No track URIs to check for saved status.")
            return

        try:
            check_follow = await self.hass.async_add_executor_job(
                self.data.client.current_user_saved_tracks_contains, uris
            )
            for track, value in zip(tracks, check_follow):
                track["saved"] = value
        except Exception as e:
            _LOGGER.error(f"Error checking if tracks are saved: {e}")
