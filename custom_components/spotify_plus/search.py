"""Sensor for Spotify Search."""
import asyncio
from typing import Any, Dict, Optional
import requests
from spotipy import SpotifyException
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.exceptions import HomeAssistantError
from . import HomeAssistantSpotifyData
from .const import DOMAIN, _LOGGER


def spotify_exception_handler(func):
    """Decorate Spotify calls to handle Spotify exception.

    A decorator that wraps the passed in function, catches Spotify errors,
    aiohttp exceptions and handles the availability of the media player.
    """

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


class SpotifySearch(RestoreEntity):
    """Spotify Search Sensor."""

    platform = "sensor"
    config_flow_class = None
    restore_state = True

    _attr_icon = "mdi:cloud-search"

    def __init__(
        self, data: HomeAssistantSpotifyData, user_id: str, name: str, user_country: str
    ) -> None:
        """Initialize the sensor."""
        self.data = data
        self._id = user_id
        self._name = name
        self._user_country = user_country
        self._state = None
        self._extra_attributes: Dict[str, Any] = {}
        self._general_search = False
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, user_id)},
        )

    async def async_added_to_hass(self):
        self.hass.services.async_register(DOMAIN, "spotify_search", self.spotify_search)
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._state = last_state.state
            self._extra_attributes = dict(last_state.attributes)

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Spotify Search"

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._state is not None:
            return self._state
        return "No Search"

    @property
    def unique_id(self):
        """Unique ID for sensor"""
        return f"SpotifySearch_{self._id}"

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the sensor."""
        return self._extra_attributes

    @spotify_exception_handler
    async def spotify_search(self, call):
        """Perform search and divide up search results."""

        self._state = call.data["search_term"]
        search_param = call.data["search_term"]
        search_type = call.data["search_type"]
        search_general = "General Search"
        search_artist = "Artist Profile"

        if search_type is None:
            search_type = search_general

        search_results = {
            "playlists": [],
            "albums": [],
            "related_artists": [],
            "tracks": [],
            "profile": [],
        }
        search_items = {}
        _LOGGER.debug("Search initiated - %s ", search_param)

        ## Quick search to get top artist in search to tag as main artist
        if search_type == search_artist:
            search_items = await self.hass.async_add_executor_job(
                self.data.client.search,
                search_param,
                5,
                0,
                "artist",
                self._user_country,
            )

            main_artist_id = search_items["artists"]["items"][0]["id"]
            main_artist_name = search_items["artists"]["items"][0]["name"]

            ## Build concurrent queries to get all of the data
            artist_playlists_task = self.hass.async_add_executor_job(
                self.data.client.search,
                main_artist_name,
                30,
                0,
                "playlist",
                self._user_country,
            )
            artist_albums_task = self.hass.async_add_executor_job(
                self.data.client.artist_albums,
                main_artist_id,
                "album",
                self._user_country,
                50,
            )
            related_artists_task = self.hass.async_add_executor_job(
                self.data.client.artist_related_artists, main_artist_id
            )
            top_tracks_task = self.hass.async_add_executor_job(
                self.data.client.artist_top_tracks, main_artist_id, self._user_country
            )
            artist_profile_task = self.hass.async_add_executor_job(
                self.data.client.artist, main_artist_id
            )
            artist_follow_task = self.hass.async_add_executor_job(
                self.data.client.current_user_following_artists, [main_artist_id]
            )
            _LOGGER.debug("Artist %s Profile retrieved", search_param)

            (
                related_artists,
                top_tracks,
                artist_albums,
                artist_playlists,
                artist_profile,
                artist_follow,
            ) = await asyncio.gather(
                related_artists_task,
                top_tracks_task,
                artist_albums_task,
                artist_playlists_task,
                artist_profile_task,
                artist_follow_task,
            )

            if "tracks" in top_tracks:
                search_results["tracks"] = [
                    {
                        "name": item["name"],
                        "artists": item["artists"][0]["name"],
                        "image": item["album"]["images"][0]["url"],
                        "uri": item["uri"],
                        "id": item["id"],
                        "info": item["name"],
                        "popularity": item.get("popularity", 0),
                        "release": item["album"]["release_date"][0:4],
                    }
                    for item in top_tracks["tracks"]
                ]

                uris = [track["uri"] for track in search_results["tracks"]]
                check_follow = await self.hass.async_add_executor_job(
                    self.data.client.current_user_saved_tracks_contains, uris
                )

                for track, value in zip(search_results["tracks"], check_follow):
                    track["saved"] = value

            if artist_albums["total"] > 0:
                search_results["albums"] = [
                    {
                        "name": item["name"],
                        "artists": item["artists"][0]["name"],
                        "image": item["images"][0]["url"],
                        "uri": item["uri"],
                        "id": item["id"],
                        "info": item["name"],
                        "release": item["release_date"][0:4],
                    }
                    for item in artist_albums["items"]
                ]

                uris = [album["uri"] for album in search_results["albums"]]
                check_follow = await self.hass.async_add_executor_job(
                    self.data.client.current_user_saved_albums_contains, uris
                )

                for album, value in zip(search_results["albums"], check_follow):
                    album["saved"] = value

                search_results["albums"].sort(key=lambda x: x["release"], reverse=True)

            search_results["related_artists"] = [
                {
                    "name": item["name"],
                    "artists": item["name"],
                    "image": item["images"][0]["url"],
                    "uri": item["uri"],
                    "id": item["id"],
                    "info": item["name"],
                    "popularity": item.get("popularity", 0),
                }
                for item in related_artists["artists"]
            ]

            uris = [artist["uri"] for artist in search_results["related_artists"]]
            check_follow = await self.hass.async_add_executor_job(
                self.data.client.current_user_following_artists, uris
            )

            for artist, value in zip(search_results["related_artists"], check_follow):
                artist["saved"] = value

            if artist_playlists["playlists"]["total"] > 0:
                search_results["playlists"] = [
                    {
                        "name": item["name"],
                        "artists": None,
                        "image": item["images"][0]["url"]
                        if len(item["images"]) > 0
                        else None,
                        "uri": item["uri"],
                        "id": item["id"],
                        "info": item["description"],
                        "owner": item["owner"]["display_name"],
                        "tracks": item["tracks"]["total"],
                    }
                    for item in artist_playlists["playlists"]["items"]
                    ## Try this search enhancement
                    if search_param.lower() in item["name"].lower()
                    or search_param.lower() in item["description"].lower()
                ]

                search_results["playlists"].sort(
                    key=lambda x: x["owner"].lower() == "spotify", reverse=True
                )

            followers = artist_profile["followers"]["total"]
            formatted_followers = (
                f"{followers / 1000000:.1f}M"
                if followers >= 1000000
                else f"{followers / 1000:.1f}k"
                if followers >= 1000
                else str(followers)
            )

            search_results["profile"] = {
                "name": artist_profile["name"],
                "followers": formatted_followers,
                "genres": artist_profile["genres"],
                "id": artist_profile["id"],
                "image": artist_profile["images"][0]["url"],
                "popularity": artist_profile["popularity"],
                "following": artist_follow[0],
            }

            self._state = "Artist Profile"

        else:
            search_items = await self.hass.async_add_executor_job(
                self.data.client.search,
                search_param,
                25,
                0,
                "track,album,playlist",
                self._user_country,
            )
            _LOGGER.debug("General Search executed %s", search_param)

            if search_items["tracks"]["total"] > 0:
                search_results["tracks"] = [
                    {
                        "name": item["name"],
                        "artists": item["artists"][0]["name"],
                        "image": item["album"]["images"][0]["url"],
                        "uri": item["uri"],
                        "id": item["id"],
                        "info": item["name"],
                        "popularity": item.get("popularity", 0),
                        "release": item["album"]["release_date"][0:4],
                    }
                    for item in search_items["tracks"]["items"]
                ]

                uris = [track["uri"] for track in search_results["tracks"]]
                check_follow = await self.hass.async_add_executor_job(
                    self.data.client.current_user_saved_tracks_contains, uris
                )

                for track, value in zip(search_results["tracks"], check_follow):
                    track["saved"] = value

            if search_items["albums"]["total"] > 0:
                search_results["albums"] = [
                    {
                        "name": item["name"],
                        "artists": item["artists"][0]["name"],
                        "image": item["images"][0]["url"]
                        if len(item["images"]) > 0
                        else None,
                        "uri": item["uri"],
                        "id": item["id"],
                        "info": item["name"],
                        "release": item["release_date"][0:4],
                    }
                    for item in search_items["albums"]["items"]
                ]

                uris = [album["uri"] for album in search_results["albums"]]
                check_follow = await self.hass.async_add_executor_job(
                    self.data.client.current_user_saved_albums_contains, uris
                )

                for album, value in zip(search_results["albums"], check_follow):
                    album["saved"] = value

            if search_items["playlists"]["total"] > 0:
                search_results["playlists"] = [
                    {
                        "name": item["name"],
                        "artists": None,
                        "image": item["images"][0]["url"]
                        if len(item["images"]) > 0
                        else None,
                        "uri": item["uri"],
                        "id": item["id"],
                        "info": item["description"],
                        "owner": item["owner"]["display_name"],
                        "tracks": item["tracks"]["total"],
                    }
                    for item in search_items["playlists"]["items"]
                ]

                search_results["playlists"].sort(
                    key=lambda x: x["owner"].lower() == "spotify", reverse=True
                )

            self._state = "General Search"

        self._extra_attributes = {"search_results": search_results}
        self.async_write_ha_state()


class SpotifyCategoryPlaylists(RestoreEntity):
    """Spotify Playlist Tools."""

    platform = "sensor"
    config_flow_class = None

    _attr_icon = "mdi:format-list-bulleted"

    def __init__(
        self, data: HomeAssistantSpotifyData, user_id: str, name: str, user_country: str
    ):
        """Initialize the sensor."""
        self.data = data
        self._id = user_id
        self._name = name
        self._user_country = user_country
        self._state = None
        self._extra_attributes: Dict[str, Any] = {}
        self._track_count = 100
        self._tolerance = 0.25
        self._logger = _LOGGER

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, user_id)},
        )

    async def async_added_to_hass(self):
        self.hass.services.async_register(
            DOMAIN, "spotify_category_playlists", self.spotify_category_playlists
        )
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._state = last_state.state
            self._extra_attributes = dict(last_state.attributes)

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Spotify Category Playlists"

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._state is not None:
            return self._state
        return "No Data"

    @property
    def unique_id(self):
        """Unique ID for sensor"""
        return f"SpotifyCategoryPlaylists_{self._id}"

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the sensor."""
        return self._extra_attributes

    @spotify_exception_handler
    async def spotify_category_playlists(self, call):
        """Get Category Playlists"""

        category_id = call.data["category_id"]

        playlists = []

        category_playlists = await self.hass.async_add_executor_job(
            self.data.client.category_playlists, category_id, self._user_country, 50
        )
        valid_playlists = [
            playlist
            for playlist in category_playlists["playlists"]["items"]
            if playlist["tracks"]["total"] != 0
        ]
        playlists.extend(valid_playlists)

        self._state = f"{len(playlists)} Playlists"
        self._extra_attributes = {"playlists": playlists}

        self.async_write_ha_state()
