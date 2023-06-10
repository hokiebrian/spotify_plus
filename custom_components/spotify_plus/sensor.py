"""Support for interacting with Spotify Connect."""
from datetime import timedelta
import asyncio
from typing import Any, Dict, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.sensor import SensorEntity
from . import HomeAssistantSpotifyData
from .songdata import SpotifySongData
from .search import SpotifySearch
from .search import SpotifyCategoryPlaylists
from .extras import SpotifyExtras
from .history import SpotifyAddToHistory
from .analysis import SpotifyHistoryAnalysis
from .tools import SpotifyMusicMachine
from .playlists import SpotifyPlaylists
from .artists import SpotifyMyArtists
from .artists import SpotifyTopArtists
from .const import DOMAIN, SPOTIFY_SCOPES, _LOGGER

SCAN_INTERVAL = timedelta(minutes=30)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup Sensors"""
    spotifyplus = SpotifyPlus(
        hass.data[DOMAIN][entry.entry_id],
        entry.data[CONF_ID],
        entry.title,
        entry.data["country"],
    )

    songdata = SpotifySongData(
        hass.data[DOMAIN][entry.entry_id],
        entry.data[CONF_ID],
        entry.title,
        entry.data.get("country"),
        entry.options.get("mm_api_token"),
    )
    analysis = SpotifyHistoryAnalysis(
        hass.data[DOMAIN][entry.entry_id],
        entry.data[CONF_ID],
        entry.title,
        entry.data["country"],
        entry.options.get("spotify_history_playlist_id"),
    )

    search = SpotifySearch(
        hass.data[DOMAIN][entry.entry_id],
        entry.data[CONF_ID],
        entry.title,
        entry.data["country"],
    )

    category_playlists = SpotifyCategoryPlaylists(
        hass.data[DOMAIN][entry.entry_id],
        entry.data[CONF_ID],
        entry.title,
        entry.data["country"],
    )

    extras = SpotifyExtras(
        hass.data[DOMAIN][entry.entry_id],
        entry.data[CONF_ID],
        entry.title,
        entry.data["country"],
    )

    top_artists = SpotifyTopArtists(
        hass.data[DOMAIN][entry.entry_id],
        entry.data[CONF_ID],
        entry.title,
        entry.data["country"],
    )

    my_artists = SpotifyMyArtists(
        hass.data[DOMAIN][entry.entry_id],
        entry.data[CONF_ID],
        entry.title,
        entry.data["country"],
    )

    add_to_history = SpotifyAddToHistory(
        hass.data[DOMAIN][entry.entry_id],
        entry.data[CONF_ID],
        entry.title,
        entry.data["country"],
        entry.options.get("spotify_history_playlist_id"),
    )
    playlists = SpotifyPlaylists(
        hass.data[DOMAIN][entry.entry_id],
        entry.data[CONF_ID],
        entry.title,
        entry.data["country"],
    )

    tools = SpotifyMusicMachine(
        hass.data[DOMAIN][entry.entry_id],
        entry.data[CONF_ID],
        entry.title,
        entry.data["country"],
    )

    sensors = [
        spotifyplus,
        songdata,
        analysis,
        search,
        category_playlists,
        extras,
        top_artists,
        my_artists,
        add_to_history,
        playlists,
        tools,
    ]

    for sensor in sensors:
        async_add_entities([sensor], True)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the sensors created by this integration."""
    unload_ok = await asyncio.gather(
        *[
            sensor.async_remove()
            for sensor in hass.data[DOMAIN][entry.entry_id]["sensors"]
        ]
    )
    if all(unload_ok):
        hass.data[DOMAIN].pop(entry.entry_id)
    return all(unload_ok)


class SpotifyPlus(SensorEntity):
    """Representation of a Spotify controller."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:spotify"

    def __init__(
        self,
        data: HomeAssistantSpotifyData,
        user_id: str,
        name: str,
        user_country: str,
    ) -> None:
        """Initialize."""
        self._id = user_id
        self._name = name
        self.data = data
        self._user_country = user_country
        self._product = None
        self._profile_image = None

        self._attr_unique_id = f"SpotifyPlayer_{self._id}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, user_id)},
            manufacturer="Spotify Plus Tools",
            model=f"Spotify {(data.current_user['product']).capitalize()}",
            name="",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://open.spotify.com",
        )

        self._scope_ok = set(data.session.token["scope"].split(" ")).issuperset(
            SPOTIFY_SCOPES
        )
        self._currently_playing: dict | None = {}
        self._playlist: dict | None = None
        self._extra_attributes: Dict[str, Any] = {}

    @property
    def state(self) -> str:
        """Return the playback state."""
        return self._product

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Spotify Plus"

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the sensor."""
        return self._extra_attributes

    async def async_update(self) -> None:
        """Update state and attributes."""
        if not self.enabled:
            return

        ## Get user profile highlights
        spotify_me_task = self.hass.async_add_executor_job(self.data.client.me)
        spotify_artist_number_task = self.hass.async_add_executor_job(
            self.data.client.current_user_followed_artists, 1
        )
        spotify_track_number_task = self.hass.async_add_executor_job(
            self.data.client.current_user_saved_tracks, 1
        )
        spotify_album_number_task = self.hass.async_add_executor_job(
            self.data.client.current_user_saved_albums, 1
        )
        spotify_playlist_number_task = self.hass.async_add_executor_job(
            self.data.client.current_user_playlists, 1
        )
        spotify_seed_genres_task = self.hass.async_add_executor_job(
            self.data.client.recommendation_genre_seeds
        )
        (
            spotify_me,
            spotify_artist_number,
            spotify_track_number,
            spotify_album_number,
            spotify_playlist_number,
            spotify_seed_genres,
        ) = await asyncio.gather(
            spotify_me_task,
            spotify_artist_number_task,
            spotify_track_number_task,
            spotify_album_number_task,
            spotify_playlist_number_task,
            spotify_seed_genres_task,
        )

        category_data = []
        offset = 0
        limit = 50

        while True:
            all_categories = await self.hass.async_add_executor_job(
                self.data.client.categories, self._user_country, None, limit, offset
            )

            valid_categories = list(all_categories["categories"]["items"])

            category_data.extend(valid_categories)

            offset += limit
            if not all_categories["categories"]["next"]:
                _LOGGER.debug("Categories Cycles complete")
                break

        category_data.sort(key=lambda item: item["name"])

        category_info = [item["name"] for item in category_data]

        _LOGGER.debug("Spotify Calls Completed")

        self._product = spotify_me["product"]
        devices = self.data.devices.data

        _LOGGER.debug("Spotify Devices Fetched")

        if len(spotify_me["images"]) > 0:
            self._profile_image = spotify_me["images"][0].get("url")

        self._extra_attributes = {
            "display_name": spotify_me.get("display_name"),
            "country": spotify_me.get("country"),
            "artists_followed": spotify_artist_number["artists"].get("total"),
            "albums_saved": spotify_album_number.get("total"),
            "tracks_saved": spotify_track_number.get("total"),
            "playlists": spotify_playlist_number.get("total"),
            "followers": spotify_me["followers"].get("total"),
            "profile_image": self._profile_image,
            "product": self._product,
            "devices": devices,
            "seed_genres": list(spotify_seed_genres["genres"]),
            "categories": category_info,
        }
