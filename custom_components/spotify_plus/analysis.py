"""Sensor for Spotify History Analysis."""

from typing import Any, Dict, Optional, Callable
from collections import defaultdict
import requests
from spotipy import SpotifyException
from homeassistant.exceptions import HomeAssistantError, NoEntitySpecifiedError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.core import HomeAssistant
from . import HomeAssistantSpotifyData
from .const import DOMAIN, _LOGGER


def spotify_exception_handler(func: Callable) -> Callable:
    """Decorate Spotify calls to handle Spotify exceptions."""

    async def wrapper(self, *args, **kwargs):
        try:
            result = await func(self, *args, **kwargs)
            self._attr_available = True
            return result
        except requests.RequestException:
            self._attr_available = False
            _LOGGER.error("RequestException encountered.")
        except SpotifyException as exc:
            self._attr_available = False
            if exc.reason == "NO_ACTIVE_DEVICE":
                _LOGGER.error("No active playback device found.")
                raise HomeAssistantError("No active playback device found") from None
            _LOGGER.error("Spotify error: %s", exc)
            raise HomeAssistantError("Spotify error") from None

    return wrapper


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
        self.entity_id = f"sensor.spotify_analysis_{self._id}"

    async def async_added_to_hass(self) -> None:
        """Register the service and restore the last state."""
        self.hass.services.async_register(
            DOMAIN, "spotify_analysis", self.spotify_history_analysis
        )
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._state = last_state.state
            self._extra_attributes = dict(last_state.attributes)

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Spotify Analysis"

    @property
    def state(self) -> Optional[str]:
        """Return the state of the sensor."""
        if self._state is not None:
            return self._state
        return "No Recent Analysis"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return f"SpotifyAnalysis_{self._id}"

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the sensor."""
        return self._extra_attributes

    @spotify_exception_handler
    async def spotify_history_analysis(self, call) -> None:
        """Analyze Spotify history."""
        if len(self._history_playlist_id) < 5:
            self._state = "Playlist not defined or invalid"
            self.async_write_ha_state()
            return

        playlist_items = await self._fetch_playlist_items()
        if not playlist_items:
            self._state = "Failed to fetch playlist items"
            self.async_write_ha_state()
            return

        artist_play_count = self._count_artists(playlist_items)
        sorted_artists = {k: v for k, v in artist_play_count.items() if v > 1}
        sorted_artists = dict(
            sorted(sorted_artists.items(), key=lambda x: x[1], reverse=True)
        )

        _LOGGER.debug("Artists sorted")

        self._state = len(artist_play_count)
        self._extra_attributes = {"artists": sorted_artists}
        _LOGGER.debug("Spotify playlist details: %s", self._extra_attributes)

        self.async_write_ha_state()

    async def _fetch_playlist_items(self) -> Optional[list]:
        """Fetch all items from the specified playlist."""
        try:
            playlist_details = await self.hass.async_add_executor_job(
                self.data.client.playlist_items,
                self._history_playlist_id,
                "items(track(artists(name))), next",
                100,
                0,
                self._user_country,
            )
            playlist_items = playlist_details["items"]

            while playlist_details["next"]:
                playlist_details = await self.hass.async_add_executor_job(
                    self.data.client.next, playlist_details
                )
                playlist_items += playlist_details["items"]

            return playlist_items
        except (requests.RequestException, SpotifyException) as err:
            _LOGGER.error("Error fetching playlist items: %s", err)
            return None

    def _count_artists(self, playlist_items: list) -> Dict[str, int]:
        """Count the occurrences of each artist in the playlist items."""
        artist_play_count = defaultdict(int)
        for item in playlist_items:
            try:
                track_artists = item["track"]["artists"]
            except KeyError:
                _LOGGER.error("Artists not found in track data: %s", item)
                continue

            for artist in track_artists:
                artist_play_count[artist["name"]] += 1

        return artist_play_count


#    async def async_update(self) -> None:
#        """Update the sensor state."""
#        await self.spotify_history_analysis(None)
