"""Adding Tracks to Unique History Playlist."""

import datetime
from typing import Any, Dict, Optional

# from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity import DeviceInfo
from . import HomeAssistantSpotifyData
from .const import DOMAIN, _LOGGER


class SpotifyAddToHistory(Entity):
    """Spotify History Sensor."""

    platform = "sensor"
    config_flow_class = None

    _attr_icon = "mdi:file-document-edit"

    def __init__(
        self,
        data: HomeAssistantSpotifyData,
        user_id: str,
        name: str,
        user_country: str,
        spotify_history_playlist_id: str,
    ):
        """Initialize the sensor."""
        self.data = data
        self._id = user_id
        self._name = name
        self._user_country = user_country
        self._state = None
        self._extra_attributes: Dict[str, Any] = {}
        self._history_playlist_id = spotify_history_playlist_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, user_id)},
        )

    async def async_added_to_hass(self):
        self.hass.services.async_register(
            DOMAIN, "spotify_add_to_history", self.spotify_add_to_history
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Spotify Add To History Playlist"

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._state is not None:
            return self._state
        return "No Recent Additions"

    @property
    def unique_id(self):
        """Unique ID for sensor"""
        return f"SpotifyHistory_{self._id}"

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the sensor."""
        return self._extra_attributes

    async def spotify_add_to_history(self, call):
        """Add the current playing track to the specified history playlist."""

        current_track = await self.hass.async_add_executor_job(
            self.data.client.currently_playing, self._user_country
        )

        ## Timestamp addition
        ## Delete existing occurances, add new item to top
        now = datetime.datetime.now()
        added_time = now.strftime("%m-%d-%Y %H:%M:%S")
        try:
            await self.hass.async_add_executor_job(
                self.data.client.playlist_remove_all_occurrences_of_items,
                self._history_playlist_id,
                [current_track["item"]["uri"]],
            )
            await self.hass.async_add_executor_job(
                self.data.client.playlist_add_items,
                self._history_playlist_id,
                [current_track["item"]["uri"]],
                0,
            )
            self._state = f"Added {current_track['item']['name']}"
            _LOGGER.debug("Track added to History")
        except Exception as err:
            _LOGGER.error("Playlist History Add Error: %s", err)

        ## Get updated playlist metadata
        playlist_data = await self.hass.async_add_executor_job(
            self.data.client.playlist, self._history_playlist_id
        )

        playlist_track_total_count = playlist_data["tracks"]["total"]
        playlist_image = playlist_data["images"]

        self._extra_attributes = {
            "Added at": added_time,
            "Song Count": playlist_track_total_count,
            "Playlist Image": playlist_image,
        }
        self.async_write_ha_state()
