"""Spotify Artist Tools."""

from typing import Any, Dict, Optional
import asyncio
import requests
from spotipy import SpotifyException
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.exceptions import HomeAssistantError
from . import HomeAssistantSpotifyData
from .const import DOMAIN, _LOGGER


def spotify_exception_handler(func):
    """Decorate Spotify calls to handle Spotify exception."""

    async def wrapper(self, *args, **kwargs):
        # pylint: disable=protected-access
        try:
            result = await func(self, *args, **kwargs)
            self._attr_available = True
            return result
        except requests.RequestException:
            self._attr_available = False
        except SpotifyException as exc:
            self._attr_available = False
            if exc.reason == "NO_ACTIVE_DEVICE":
                raise HomeAssistantError("No active playback device found") from None
            raise HomeAssistantError(f"Spotify error: {exc.reason}") from exc

    return wrapper


class SpotifyMyArtists(RestoreEntity):
    """Spotify My Artist Tools."""

    platform = "sensor"
    config_flow_class = None

    _attr_icon = "mdi:account-music"

    def __init__(
        self, data: HomeAssistantSpotifyData, user_id: str, name: str, user_country: str
    ):
        """Initialize the sensor."""
        self._id = user_id
        self._name = name
        self._user_country = user_country
        self.data = data
        self._state = None
        self._extra_attributes: Dict[str, Any] = {}

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, user_id)},
        )

    async def async_added_to_hass(self):
        self.hass.services.async_register(
            DOMAIN, "spotify_my_artists", self.spotify_my_artists
        )
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._state = last_state.state
            self._extra_attributes = dict(last_state.attributes)

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Spotify My Artists"

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._state is not None:
            return self._state
        return "No Data"

    @property
    def unique_id(self):
        """Unique ID for sensor"""
        return f"SpotifyMyArtists_{self._id}"

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the sensor."""
        return self._extra_attributes

    async def search_playlists_async(self, semaphore, artist):
        """Search for Artist Playlists."""
        async with semaphore:
            artist_playlist_uri_1 = "spotify:"
            artist_playlist_uri_2 = "spotify:"
            artist_playlist_name_1 = "N/A"
            artist_playlist_name_2 = "N/A"

            artist_name = artist.get("name", "")
            if not artist_name:
                _LOGGER.error("Artist name missing")
                return

            search_param = artist_name.lower()
            pl1 = f"This Is {artist_name}"
            pl2 = f"{artist_name} Radio"

            srch = await self.hass.async_add_executor_job(
                self.data.client.search,
                search_param,
                20,
                0,
                "playlist",
                self._user_country,
            )
            
            playlists = srch.get("playlists", {}).get("items")
            if playlists is None or not isinstance(playlists, list):
                _LOGGER.error("Playlists are missing or not a list")
                return

            for p_list in playlists:
                owner = p_list.get("owner")
                if owner is not None and isinstance(owner, dict) and owner.get("id") == "spotify":
                    p_list_name = p_list.get("name")
                    if p_list_name == pl1:
                        artist_playlist_uri_1 = p_list.get("uri")
                        artist_playlist_name_1 = p_list_name
                    elif p_list_name == pl2:
                        artist_playlist_uri_2 = p_list.get("uri")
                        artist_playlist_name_2 = p_list_name

            return {
                "name": artist.get("name"),
                "uri": artist.get("uri"),
                "image": artist.get("images", [{}])[0].get("url"),
                "artist_playlist_name": artist_playlist_name_1,
                "artist_playlist": artist_playlist_uri_1,
                "artist_radio_name": artist_playlist_name_2,
                "artist_radio": artist_playlist_uri_2,
            }

    @spotify_exception_handler
    async def spotify_my_artists(self, call):
        """Gather 'My Artists' and get details."""
        artist_items = []
        artists = []

        my_artists = await self.hass.async_add_executor_job(
            self.data.client.current_user_followed_artists, 50
        )
        artist_items = my_artists["artists"]["items"]

        while my_artists["artists"]["next"]:
            cur = my_artists["artists"]["cursors"]["after"]
            my_artists = await self.hass.async_add_executor_job(
                self.data.client.current_user_followed_artists, 50, cur
            )
            artist_items += my_artists["artists"]["items"]

        semaphore = asyncio.Semaphore(8)
        tasks = []
        for artist in artist_items:
            tasks.append(self.search_playlists_async(semaphore, artist))
        artist_results = await asyncio.gather(*tasks)

        artists = sorted(
            filter(lambda x: "name" in x, artist_results),
            key=lambda x: x["name"].replace("The ", ""),
        )

        _LOGGER.debug("My Artists retrieved and sorted")

        self._state = f"{len(artists)} Artists"
        self._extra_attributes = {"my_artists": artists}
        self.async_write_ha_state()


class SpotifyTopArtists(RestoreEntity):
    """Spotify Top Artist Tools."""

    platform = "sensor"
    config_flow_class = None

    _attr_icon = "mdi:account-music"

    def __init__(
        self, data: HomeAssistantSpotifyData, user_id: str, name: str, user_country: str
    ):
        """Initialize the sensor."""
        self._id = user_id
        self._name = name
        self._user_country = user_country
        self.data = data
        self._state = None
        self._extra_attributes: Dict[str, Any] = {}

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, user_id)},
        )

    async def async_added_to_hass(self):
        self.hass.services.async_register(
            DOMAIN, "spotify_top_artists", self.spotify_top_artists
        )
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._state = last_state.state
            self._extra_attributes = dict(last_state.attributes)

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Spotify Top Artists"

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._state is not None:
            return self._state
        return "No Data"

    @property
    def unique_id(self):
        """Unique ID for sensor"""
        return f"SpotifyTopArtists_{self._id}"

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the sensor."""
        return self._extra_attributes

    @spotify_exception_handler
    async def search_playlists_async(self, semaphore, artist):
        """Search for Artist Playlists."""
        async with semaphore:
            artist_playlist_uri_1 = "spotify:"
            artist_playlist_uri_2 = "spotify:"
            artist_playlist_name_1 = "N/A"
            artist_playlist_name_2 = "N/A"

            artist_name = artist.get("name", "")
            if not artist_name:
                _LOGGER.error("Artist name missing")
                return

            search_param = artist_name.lower()
            pl1 = f"This Is {artist_name}"
            pl2 = f"{artist_name} Radio"

            srch = await self.hass.async_add_executor_job(
                self.data.client.search,
                search_param,
                20,
                0,
                "playlist",
                self._user_country,
            )
            
            playlists = srch.get("playlists", {}).get("items")
            if playlists is None or not isinstance(playlists, list):
                _LOGGER.error("Playlists are missing or not a list")
                return

            for p_list in playlists:
                owner = p_list.get("owner")
                if owner is not None and isinstance(owner, dict) and owner.get("id") == "spotify":
                    p_list_name = p_list.get("name")
                    if p_list_name == pl1:
                        artist_playlist_uri_1 = p_list.get("uri")
                        artist_playlist_name_1 = p_list_name
                    elif p_list_name == pl2:
                        artist_playlist_uri_2 = p_list.get("uri")
                        artist_playlist_name_2 = p_list_name

            return {
                "name": artist.get("name"),
                "uri": artist.get("uri"),
                "image": artist.get("images", [{}])[0].get("url"),
                "artist_playlist_name": artist_playlist_name_1,
                "artist_playlist": artist_playlist_uri_1,
                "artist_radio_name": artist_playlist_name_2,
                "artist_radio": artist_playlist_uri_2,
            }

    @spotify_exception_handler
    async def spotify_top_artists(self, call):
        """Gather 'Top Artists' and get details."""
        artist_items = []
        artists = []

        ## This is a bit of a hack. The endpoint is only supposed
        ## to return 50 artists, but if you set the offset to 49
        ## and request the max limit of 50, you can get 99 artists
        my_artists = await self.hass.async_add_executor_job(
            self.data.client.current_user_top_artists, 49, 0
        )
        my_artists2 = await self.hass.async_add_executor_job(
            self.data.client.current_user_top_artists, 50, 49
        )
        artist_items = my_artists["items"] + my_artists2["items"]

        semaphore = asyncio.Semaphore(8)
        tasks = []
        for artist in artist_items:
            tasks.append(self.search_playlists_async(semaphore, artist))
        artist_results = await asyncio.gather(*tasks)

        artists = sorted(
            filter(lambda x: "name" in x, artist_results),
            key=lambda x: x["name"].replace("The ", ""),
        )

        _LOGGER.debug("Top Artists retrieved and sorted")

        self._state = f"{len(artists)} Artists"
        self._extra_attributes = {"top_artists": artists}
        self.async_write_ha_state()
