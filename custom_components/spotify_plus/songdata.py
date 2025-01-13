from typing import Any, Dict, Optional
import asyncio
import aiohttp
import requests

from spotipy import SpotifyException
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
from . import HomeAssistantSpotifyData
from .const import DOMAIN, _LOGGER, SPOTIFY_SCOPES, MM_API

def spotify_exception_handler(func):
    """Decorate Spotify calls to handle Spotify exception."""

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
                raise HomeAssistantError("No active playback device found") from None
            _LOGGER.error("Spotify error: %s", exc)
            raise HomeAssistantError(f"Spotify error: {exc.reason}") from exc

    return wrapper


class SpotifySongData(RestoreEntity):
    """Representation of a Spotify controller."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:card-account-details-outline"

    def __init__(
        self,
        data: HomeAssistantSpotifyData,
        user_id: str,
        name: str,
        user_country: str,
        mm_api_token: str,
    ) -> None:
        """Initialize the sensor."""
        self.data = data
        self._id = user_id
        self._name = name
        self._user_country = user_country
        self._mm_api_token = mm_api_token or None
        self._state = "No Current Song"
        self._attr_unique_id = f"SpotifyData_{self._id}"
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

        self._initialize_attributes()

    def _initialize_attributes(self):
        """Initialize attributes to default values."""
        self._current_artist_name = None
        self._current_artist_id = None
        self._current_artist_uri = None
        self._current_album_id = None
        self._current_album_uri = None
        self._current_album_img = {}
        self._current_track_name = None
        self._current_track_id = None
        self._current_track_uri = None
        self._current_album_name = None
        self._current_track_isrc = None
        self._following_artist = None
        self._following_album = None
        self._following_track = None
        self._spotify_playlist_follow = None
        self._spotify_playlist = None
        self._play_source = None
        self._spotify_context_uri = None
        self._artist_img = None
        self._lyrics_link = None
        self._track_length = "00:00"
        self._album_tracks: Dict[str, Any] = {}
        self._track_details = None
        self._current_track_copyright = None
        self._current_genres = None
        self._current_track_label = None
        self._current_track_release_date = None

    async def async_added_to_hass(self):
        """Register services when the entity is added to hass."""
        service_options = {
            "get_song_data": self.get_song_data,
            "spotify_follow_artist": self.spotify_follow_artist,
            "spotify_follow_album": self.spotify_follow_album,
            "spotify_follow_track": self.spotify_follow_track,
            "spotify_follow_playlist": self.spotify_follow_playlist,
            "spotify_unfollow_artist": self.spotify_unfollow_artist,
            "spotify_unfollow_album": self.spotify_unfollow_album,
            "spotify_unfollow_track": self.spotify_unfollow_track,
            "spotify_unfollow_playlist": self.spotify_unfollow_playlist,
        }
        for service_name, service_func in service_options.items():
            self.hass.services.async_register(DOMAIN, service_name, service_func)

        last_state = await self.async_get_last_state()
        if last_state:
            self._state = last_state.state
            self._extra_attributes = dict(last_state.attributes)

    @property
    def state(self) -> Optional[str]:
        """Return the current track name as the state."""
        return self._current_track_name or "No Current Song"

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Spotify Song Details"

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the sensor."""
        return self._extra_attributes

    @spotify_exception_handler
    async def get_song_data(self, call):
        """Update the sensor with current song data."""
        retry = True
        retry_count = 0

        while retry and retry_count < 2:
            try:
                current_playback = await self.hass.async_add_executor_job(
                    self.data.client.currently_playing
                )
                retry = False
            except Exception as err:
                _LOGGER.error("Spotify Initialization Failure: %s", err)
                retry_count += 1
                await asyncio.sleep(1)

        if current_playback is None:
            self._state = None
        else:
            self._extract_playback_data(current_playback)
            await self._update_following_status()
            await self._update_additional_details(current_playback)

        self.async_write_ha_state()

    def _extract_playback_data(self, current_playback):
        """Extract playback data from the current playback information."""
        self._state = current_playback.get("item", {}).get("name")
        self._current_artist_name = (
            current_playback.get("item", {}).get("artists", [{}])[0].get("name")
        )
        self._current_artist_id = (
            current_playback.get("item", {}).get("artists", [{}])[0].get("id")
        )
        self._current_artist_uri = (
            current_playback.get("item", {}).get("artists", [{}])[0].get("uri")
        )
        self._current_album_id = (
            current_playback.get("item", {}).get("album", {}).get("id")
        )
        self._current_album_uri = (
            current_playback.get("item", {}).get("album", {}).get("uri")
        )
        self._current_album_img = (
            current_playback.get("item", {}).get("album", {}).get("images")
        )
        self._current_track_name = current_playback.get("item", {}).get("name")
        self._current_track_id = current_playback.get("item", {}).get("id")
        self._current_track_uri = current_playback.get("item", {}).get("uri")
        self._current_album_name = (
            current_playback.get("item", {}).get("album", {}).get("name")
        )
        self._current_track_isrc = (
            current_playback.get("item", {})
            .get("external_ids", {})
            .get("isrc", "")
            .upper()
        )

    async def _update_following_status(self):
        """Update the following status for artist, album, and track."""
        following_artist_task = self.hass.async_add_executor_job(
            self.data.client.current_user_following_artists, [self._current_artist_id]
        )
        following_album_task = self.hass.async_add_executor_job(
            self.data.client.current_user_saved_albums_contains,
            [self._current_album_id],
        )
        following_track_task = self.hass.async_add_executor_job(
            self.data.client.current_user_saved_tracks_contains,
            [self._current_track_uri],
        )
        track_details_task = self.hass.async_add_executor_job(
            self.data.client.track, self._current_track_uri
        )

        following_artist, following_album, following_track, track_details = (
            await asyncio.gather(
                following_artist_task,
                following_album_task,
                following_track_task,
                track_details_task,
            )
        )

        self._following_artist = following_artist[0]
        self._following_album = following_album[0]
        self._following_track = following_track[0]
        self._track_details = track_details

    async def _update_additional_details(self, current_playback):
        """Update additional details such as lyrics, audio features, and album tracks."""
        self._current_track_copyright = self._track_details["album"].get(
            "copyrights", ""
        )
        self._current_genres = self._track_details["album"].get("genres", [])
        self._current_track_label = self._track_details["album"].get("label", "")
        self._current_track_release_date = self._track_details["album"]["release_date"]

        current_context_uri = (
            current_playback.get("context", {}).get("uri")
            if "context" in current_playback and current_playback["context"] is not None
            else None
        )
        self._play_source = (
            current_playback.get("context", {}).get("type", "unknown")
            if current_context_uri
            else "queue"
        )

        if (
            current_context_uri
            and current_playback.get("context", {}).get("type", "") == "playlist"
        ):
            playlist_id = current_context_uri.replace("spotify:playlist:", "")
            self._spotify_playlist_follow = await self.hass.async_add_executor_job(
                self.data.client.playlist_is_following, playlist_id, [self._id]
            )

        if self._mm_api_token:
            await self._fetch_lyrics()

        duration_ms = current_playback["item"]["duration_ms"]
        self._track_length = (
            f"{duration_ms // 60000:02d}:{(duration_ms // 1000) % 60:02d}"
        )

        try:
#            audio_features_task = self.hass.async_add_executor_job(
#                self.data.client.audio_features, [self._current_track_uri]
#            )
            album_tracks_task = self.hass.async_add_executor_job(
                self.data.client.album_tracks, current_playback["item"]["album"]["id"]
            )

#            audio_features, album_tracks = await asyncio.gather(
#                audio_features_task, album_tracks_task
#            )

            self._album_tracks = [
                {
                    "trackNumber": track["track_number"],
                    "name": track["name"],
                    "artist": track["artists"][0]["name"],
                    "uri": track["uri"],
                }
                for track in album_tracks["items"]
            ]
        except Exception as err:
            _LOGGER.error("Failed to fetch additional details: %s", err)

        self._update_extra_attributes(current_playback)

    async def _fetch_lyrics(self):
        """Fetch lyrics URL using MusixMatch API."""
        url_lyrics = f"{MM_API}?format=json&apikey={self._mm_api_token}&track_isrc={self._current_track_isrc}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url_lyrics) as response:
                response_json = await response.json(content_type="text/plain")

        if (
            "message" in response_json
            and "body" in response_json["message"]
            and "track" in response_json["message"]["body"]
        ):
            self._lyrics_link = response_json["message"]["body"]["track"][
                "track_share_url"
            ]
        else:
            self._lyrics_link = None

    def _update_extra_attributes(self, current_playback):
        """Update the extra attributes with detailed song information."""
        self._extra_attributes = {
            "spotify": {
                "spotify_track_id": self._current_track_id,
                "spotify_track_uri": self._current_track_uri,
                "spotify_artist_name": self._current_artist_name,
                "spotify_artist_id": self._current_artist_id,
                "spotify_artist_uri": self._current_artist_uri,
                "spotify_album_id": self._current_album_id,
                "spotify_album_uri": self._current_album_uri,
                "spotify_album_img": self._current_album_img,
                "spotify_track_name": self._current_track_name,
                "spotify_track_length": self._track_length,
                "spotify_album_name": self._current_album_name,
                "spotify_track_isrc": self._current_track_isrc,
                "spotify_album_tracks": self._album_tracks,
                "spotify_follow_artist": self._following_artist,
                "spotify_follow_album": self._following_album,
                "spotify_follow_track": self._following_track,
                "lyrics_link": self._lyrics_link,
                "spotify_playlist_follow": self._spotify_playlist_follow,
                "spotify_context_URI": self._spotify_context_uri,
                "spotify_copyright": self._current_track_copyright,
                "spotify_play_source": self._play_source,
                "spotify_genres": self._current_genres,
                "spotify_track_release_date": self._current_track_release_date,
                "spotify_track_label": self._current_track_label,
            },
        }

    @spotify_exception_handler
    async def spotify_follow_artist(self, call):
        """Follow the current or specified artist on Spotify."""
        artist_id = call.data.get("artist_id", self._current_artist_id)
        if artist_id:
            await self.hass.async_add_executor_job(
                self.data.client.user_follow_artists, [artist_id]
            )
            _LOGGER.debug("Spotify Artist %s Added", artist_id)

    @spotify_exception_handler
    async def spotify_follow_album(self, call):
        """Follow the current or specified album on Spotify."""
        album_id = call.data.get("album_id", self._current_album_id)
        if album_id:
            await self.hass.async_add_executor_job(
                self.data.client.current_user_saved_albums_add, [album_id]
            )
            _LOGGER.debug("Spotify Album %s Added", album_id)

    @spotify_exception_handler
    async def spotify_follow_track(self, call):
        """Follow the current or specified track on Spotify."""
        track_id = call.data.get("track_id", self._current_track_uri)
        if track_id:
            await self.hass.async_add_executor_job(
                self.data.client.current_user_saved_tracks_add, [track_id]
            )
            _LOGGER.debug("Spotify Track %s Added", track_id)

    @spotify_exception_handler
    async def spotify_follow_playlist(self, call):
        """Follow the current or specified playlist on Spotify."""
        playlist_id = call.data.get("playlist_id", self._spotify_context_uri)
        if playlist_id:
            await self.hass.async_add_executor_job(
                self.data.client.current_user_follow_playlist, playlist_id
            )
            _LOGGER.debug("Spotify Playlist %s Added", playlist_id)

    @spotify_exception_handler
    async def spotify_unfollow_artist(self, call):
        """Unfollow the current or specified artist on Spotify."""
        artist_id = call.data.get("artist_id", self._current_artist_id)
        if artist_id:
            await self.hass.async_add_executor_job(
                self.data.client.user_unfollow_artists, [artist_id]
            )
            _LOGGER.debug("Spotify Artist %s Deleted", artist_id)

    @spotify_exception_handler
    async def spotify_unfollow_album(self, call):
        """Unfollow the current or specified album on Spotify."""
        album_id = call.data.get("album_id", self._current_album_id)
        if album_id:
            await self.hass.async_add_executor_job(
                self.data.client.current_user_saved_albums_delete, [album_id]
            )
            _LOGGER.debug("Spotify Album %s Deleted", album_id)

    @spotify_exception_handler
    async def spotify_unfollow_track(self, call):
        """Unfollow the current or specified track on Spotify."""
        track_id = call.data.get("track_id", self._current_track_uri)
        if track_id:
            await self.hass.async_add_executor_job(
                self.data.client.current_user_saved_tracks_delete, [track_id]
            )
            _LOGGER.debug("Spotify Track %s Deleted", track_id)

    @spotify_exception_handler
    async def spotify_unfollow_playlist(self, call):
        """Unfollow the current or specified playlist on Spotify."""
        playlist_id = call.data.get("playlist_id", self._spotify_context_uri)
        if playlist_id:
            await self.hass.async_add_executor_job(
                self.data.client.current_user_unfollow_playlist, playlist_id
            )
            _LOGGER.debug("Spotify Playlist %s Deleted", playlist_id)
