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

    def __init__(self, data: HomeAssistantSpotifyData, user_id: str, name: str, user_country: str):
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
        self.hass.services.async_register(DOMAIN, "spotify_extras", self.spotify_extras)

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Spotify Extras"

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._state is not None:
            return self._state
        return "No Current Song"

    @property
    def unique_id(self):
        """Unique ID for sensor"""
        return f"SpotifyExtras{self._id}"

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the sensor."""
        return self._extra_attributes

    async def spotify_extras(self, call):
        """Get Queue and Recent items"""
        # Apparently the queue needs a cooldown after a change?
        await asyncio.sleep(1)

        ## Fetch queue and 30 recent items
        try:
            spotify_queue, spotify_recent = await asyncio.gather(
                self.hass.async_add_executor_job(self.data.client.queue),
                self.hass.async_add_executor_job(self.data.client.current_user_recently_played, 30),
            )
        except Exception as err:
            _LOGGER.error("Spotify Queue and Recent Error: %s", err)
            spotify_queue = {'queue': []}
            spotify_recent = {'items': []}

        ## Build Queue Data
        queue_list = [{
            "trackname": track['name'],
            "trackartist": track['artists'][0]['name'],
            "trackuri": track['uri'],
            "trackid": track['id'],
            "image": track['album'].get('images', [{}])[0].get('url')
        } for track in spotify_queue.get('queue', [])]

        ## Bulk check if items are in library, merge with queue items
        uris = [track["trackuri"] for track in queue_list]
        check_follow = await self.hass.async_add_executor_job(
            self.data.client.current_user_saved_tracks_contains,
            uris
            )

        for track, value in zip(queue_list, check_follow):
            track["saved"] = value

        _LOGGER.debug("Queue Retrieved")

        ## Build Recent Items Data
        recent_list = [{
            "trackname": item['track']['name'],
            "trackartist": item['track']['artists'][0]['name'],
            "trackuri": item['track']['uri'],
            "image": item['track']['album'].get('images', [{}])[0].get('url'),
            "played": item['played_at'],
        } for item in spotify_recent.get('items', [])]

        ## Bulk check if items are in library, merge with recent items
        uris = [track["trackuri"] for track in recent_list]
        check_follow = await self.hass.async_add_executor_job(
            self.data.client.current_user_saved_tracks_contains,
            uris
            )

        for track, value in zip(recent_list, check_follow):
            track["saved"] = value

        _LOGGER.debug("Recent List Retrieved")

        self._state = "Queue and Recent"
        self._extra_attributes = {"queue": queue_list, "recent": recent_list}
        self.async_write_ha_state()
