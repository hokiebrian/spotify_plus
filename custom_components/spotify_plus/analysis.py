"""Sensor for Spotify History Analysis."""

from typing import Any, Dict, Optional
from collections import defaultdict
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
from . import HomeAssistantSpotifyData
from .const import DOMAIN, _LOGGER

class SpotifyHistoryAnalysis(RestoreEntity):
    """Spotify History Analysis Sensor."""   

    platform = "sensor"
    config_flow_class = None

    _attr_icon = "mdi:poll"
    _attr_native_unit_of_measurement = "artists"

    def __init__(
        self,
        data: HomeAssistantSpotifyData,
        user_id: str,
        name: str,
        user_country: str,
        spotify_history_playlist_id: str,
    ) -> None:

        """Initialize."""
        self._id = user_id
        self._name = name
        self._user_country = user_country
        self.data = data
        self._state = None
        self._extra_attributes: Dict[str, Any] = {}
        self._history_playlist_id = spotify_history_playlist_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, user_id)},
        )

    async def async_added_to_hass(self):
        self.hass.services.async_register(DOMAIN, "spotify_analysis", self.spotify_history_analysis)
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._state = last_state.state
            self._extra_attributes = dict(last_state.attributes)

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Spotify Analysis"

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._state is not None:
            return self._state
        return "No Recent Analysis"

    @property
    def unique_id(self):
        """Unique ID for sensor"""
        return f"SpotifyAnalysis_{self._id}"

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the sensor."""
        return self._extra_attributes

    async def spotify_history_analysis(self, call):
        """Get Data to analyze"""

        if len(self._history_playlist_id) < 5:
            self._state = "Playlist not defined or invalid"
            self.async_write_ha_state()
            return

        playlist_items = []

        ## Fetch Playlist Metadata
        playlist_details = await self.hass.async_add_executor_job(
            self.data.client.playlist_items,
            self._history_playlist_id,
            'items(track(artists(name))), next',
            100,
            0,
            self._user_country
        )

        playlist_items = playlist_details['items']

        ## Return all playlist items
        while playlist_details['next']:
            playlist_details = await self.hass.async_add_executor_job(
                self.data.client.next, playlist_details
                )
            playlist_items += playlist_details['items']

        ## Count Artists
        artist_play_count = defaultdict(int)
        for item in playlist_items:
            for artist in item['track']['artists']:
                artist_play_count[artist['name']] += 1

        ## For brevity, the list trims artist count of 1
        ## But still counts them in total unique artists
        sorted_artists = {k: v for k, v in artist_play_count.items() if v > 1}
        sorted_artists = dict(sorted(sorted_artists.items(), key=lambda x: x[1], reverse=True))
        _LOGGER.debug("Artists Sorted")

        self._state = len(artist_play_count)
        self._extra_attributes = {"artists": sorted_artists}
        _LOGGER.debug("Spotify Playlist Details %s", self._extra_attributes)

        self.async_write_ha_state()
