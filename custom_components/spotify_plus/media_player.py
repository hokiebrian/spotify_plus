"""Support for interacting with Spotify Connect."""
from __future__ import annotations

from asyncio import run_coroutine_threadsafe
import datetime as dt
from datetime import timedelta
from typing import Any, Dict, Optional

import requests
from spotipy import SpotifyException
from yarl import URL

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utc_from_timestamp

from . import HomeAssistantSpotifyData
from .const import (
    DOMAIN,
    _LOGGER,
    MEDIA_PLAYER_PREFIX,
    PLAYABLE_MEDIA_TYPES,
    SPOTIFY_SCOPES,
)


SCAN_INTERVAL = timedelta(seconds=3)

SUPPORT_SPOTIFY = (
    MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.REPEAT_SET
    | MediaPlayerEntityFeature.SEEK
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.SHUFFLE_SET
    | MediaPlayerEntityFeature.VOLUME_SET
)

REPEAT_MODE_MAPPING_TO_HA = {
    "context": RepeatMode.ALL,
    "off": RepeatMode.OFF,
    "track": RepeatMode.ONE,
}

REPEAT_MODE_MAPPING_TO_SPOTIFY = {
    value: key for key, value in REPEAT_MODE_MAPPING_TO_HA.items()
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Spotify based on a config entry."""
    spotifyplus = SpotifyMediaPlayer(
        hass.data[DOMAIN][entry.entry_id],
        entry.data[CONF_ID],
        entry.title,
    )
    async_add_entities([spotifyplus], True)


def spotify_exception_handler(func):
    """Decorate Spotify calls to handle Spotify exception.

    A decorator that wraps the passed in function, catches Spotify errors,
    aiohttp exceptions and handles the availability of the media player.
    """

    def wrapper(self, *args, **kwargs):
        # pylint: disable=protected-access
        try:
            result = func(self, *args, **kwargs)
            self._attr_available = True
            return result
        except requests.RequestException:
            self._attr_available = False
        except SpotifyException as exc:
            self._attr_available = False
            if exc.reason == "NO_ACTIVE_DEVICE":
                raise HomeAssistantError("No active playback device found") from None
            raise HomeAssistantError("Spotify error") from None

    return wrapper


class SpotifyMediaPlayer(MediaPlayerEntity):
    """Representation of a Spotify controller."""

    _attr_icon = "mdi:spotify"
    _attr_media_image_remotely_accessible = False

    def __init__(
        self,
        data: HomeAssistantSpotifyData,
        user_id: str,
        name: str,
    ) -> None:
        """Initialize."""
        self._id = user_id
        self.data = data
        self._extra_attributes: Dict[str, Any] = {}

        self._attr_unique_id = user_id

        if self.data.current_user["product"] == "premium":
            self._attr_supported_features = SUPPORT_SPOTIFY

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, user_id)},
        )

        self._scope_ok = set(data.session.token["scope"].split(" ")).issuperset(
            SPOTIFY_SCOPES
        )
        self._currently_playing: dict | None = {}
        self._playlist: dict | None = None
        self._current_artist_id = None
        self._current_album_id = None
        self._current_album_name = None
        self._current_album_img = None
        self._spotify_album_img = None
        self._current_track_length_readable = None
        self._current_track_percent = None
        self._current_track_isrc = None
        self._current_device_id = None
        self._current_track_length = 1
        self._current_track_progress = 1
        _LOGGER.debug("Media Player Initialized")

    @property
    def state(self) -> MediaPlayerState:
        """Return the playback state."""
        if not self._currently_playing:
            return MediaPlayerState.IDLE
        if self._currently_playing["is_playing"]:
            return MediaPlayerState.PLAYING
        return MediaPlayerState.PAUSED

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"Spotify {self.data.current_user['display_name']}"

    @property
    def volume_level(self) -> float | None:
        """Return the device volume."""
        if not self._currently_playing:
            return None
        return self._currently_playing.get("device", {}).get("volume_percent", 0) / 100

    @property
    def media_content_id(self) -> str | None:
        """Return the media URL."""
        if not self._currently_playing:
            return None
        item = self._currently_playing.get("item") or {}
        return item.get("uri")

    @property
    def media_content_type(self) -> str | None:
        """Return the media type."""
        if not self._currently_playing:
            return None
        item = self._currently_playing.get("item") or {}
        is_episode = item.get("type") == MediaType.EPISODE
        return MediaType.PODCAST if is_episode else MediaType.MUSIC

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        if (
            self._currently_playing is None
            or self._currently_playing.get("item") is None
        ):
            return None
        return self._currently_playing["item"]["duration_ms"] / 1000

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        if (
            not self._currently_playing
            or self._currently_playing.get("progress_ms") is None
        ):
            return None
        return self._currently_playing["progress_ms"] / 1000

    @property
    def media_position_updated_at(self) -> dt.datetime | None:
        """When was the position of the current playing media valid."""
        if not self._currently_playing:
            return None
        return utc_from_timestamp(self._currently_playing["timestamp"] / 1000)

    @property
    def media_image_url(self) -> str | None:
        """Return the media image URL."""
        item = self._currently_playing.get("item") or {}
        if not self._currently_playing or self._currently_playing.get("item") is None:
            return None

        if not item["album"]["images"]:
            return None
        return self._current_album_img[0]["url"]

    @property
    def media_title(self) -> str | None:
        """Return the media title."""
        if not self._currently_playing:
            return None
        item = self._currently_playing.get("item") or {}
        return item.get("name")

    @property
    def media_artist(self) -> str | None:
        """Return the media artist."""
        if not self._currently_playing or self._currently_playing.get("item") is None:
            return None

        item = self._currently_playing["item"]
        if item["type"] == MediaType.EPISODE:
            return item["show"]["publisher"]

        return ", ".join(artist["name"] for artist in item["artists"])

    @property
    def media_album_name(self) -> str | None:
        """Return the media album."""
        if not self._currently_playing or self._currently_playing.get("item") is None:
            return None

        item = self._currently_playing["item"]
        if item["type"] == MediaType.EPISODE:
            return item["show"]["name"]

        return item["album"]["name"]

    @property
    def media_track(self) -> int | None:
        """Track number of current playing media, music track only."""
        if not self._currently_playing:
            return None
        item = self._currently_playing.get("item") or {}
        return item.get("track_number")

    @property
    def media_playlist(self):
        """Title of Playlist currently playing."""
        if self._playlist is None:
            return None
        return self._playlist["name"]

    @property
    def source(self) -> str | None:
        """Return the current playback device."""
        if not self._currently_playing:
            return None
        return self._currently_playing.get("device", {}).get("name")

    @property
    def source_list(self) -> list[str] | None:
        """Return a list of source devices."""
        return [device["name"] for device in self.data.devices.data]

    @property
    def shuffle(self) -> bool | None:
        """Shuffling state."""
        if not self._currently_playing:
            return None
        return self._currently_playing.get("shuffle_state")

    @property
    def repeat(self) -> RepeatMode | None:
        """Return current repeat mode."""
        if (
            not self._currently_playing
            or (repeat_state := self._currently_playing.get("repeat_state")) is None
        ):
            return None
        return REPEAT_MODE_MAPPING_TO_HA.get(repeat_state)

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the sensor."""
        return self._extra_attributes

    @spotify_exception_handler
    def set_volume_level(self, volume: float) -> None:
        """Set the volume level."""
        self.data.client.volume(int(volume * 100))

    @spotify_exception_handler
    def media_play(self) -> None:
        """Start or resume playback."""
        self.data.client.start_playback()

    @spotify_exception_handler
    def media_pause(self) -> None:
        """Pause playback."""
        self.data.client.pause_playback()

    @spotify_exception_handler
    def media_previous_track(self) -> None:
        """Skip to previous track."""
        self.data.client.previous_track()

    @spotify_exception_handler
    def media_next_track(self) -> None:
        """Skip to next track."""
        self.data.client.next_track()

    @spotify_exception_handler
    def media_seek(self, position: float) -> None:
        """Send seek command."""
        self.data.client.seek_track(int(position * 1000))

    @spotify_exception_handler
    def play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play media."""
        media_type = media_type.removeprefix(MEDIA_PLAYER_PREFIX)

        kwargs = {}

        # Spotify can't handle URI's with query strings or anchors
        # Yet, they do generate those types of URI in their official clients.
        media_id = str(URL(media_id).with_query(None).with_fragment(None))

        if media_type in {MediaType.TRACK, MediaType.EPISODE, MediaType.MUSIC}:
            kwargs["uris"] = [media_id]
        elif media_type in PLAYABLE_MEDIA_TYPES:
            kwargs["context_uri"] = media_id
        else:
            _LOGGER.error("Media type %s is not supported", media_type)
            return

        if (
            self._currently_playing
            and not self._currently_playing.get("device")
            and self.data.devices.data
        ):
            kwargs["device_id"] = self.data.devices.data[0].get("id")

        self.data.client.start_playback(**kwargs)
        _LOGGER.debug("Play Event %s", kwargs)

    @spotify_exception_handler
    def select_source(self, source: str) -> None:
        """Select playback device."""
        for device in self.data.devices.data:
            if device["name"] == source:
                self.data.client.transfer_playback(
                    device["id"], self.state == MediaPlayerState.PLAYING
                )
                return

    @spotify_exception_handler
    def set_shuffle(self, shuffle: bool) -> None:
        """Enable/Disable shuffle mode."""
        self.data.client.shuffle(shuffle)

    @spotify_exception_handler
    def set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        if repeat not in REPEAT_MODE_MAPPING_TO_SPOTIFY:
            raise ValueError(f"Unsupported repeat mode: {repeat}")
        self.data.client.repeat(REPEAT_MODE_MAPPING_TO_SPOTIFY[repeat])

    @spotify_exception_handler
    def update(self) -> None:
        """Update state and attributes."""
        if not self.enabled:
            return

        if not self.data.session.valid_token or self.data.client is None:
            run_coroutine_threadsafe(
                self.data.session.async_ensure_token_valid(), self.hass.loop
            ).result()
            self.data.client.set_auth(auth=self.data.session.token["access_token"])

        current = self.data.client.current_playback()
        self._currently_playing = current or {}

        context = self._currently_playing.get("context")
        if context is not None and (
            self._playlist is None or self._playlist["uri"] != context["uri"]
        ):
            self._playlist = None
            if context["type"] == MediaType.PLAYLIST:
                self._playlist = self.data.client.playlist(current["context"]["uri"])

        current_playback = current

        ## Add additional attributes to media_player entity. This requires no additional API calls.
        if current_playback is not None:
            if "item" in current_playback and "duration_ms" in current_playback["item"]:
                duration_ms = current_playback["item"]["duration_ms"]
                duration_sec = duration_ms // 1000
                minutes, seconds = divmod(duration_sec, 60)
                duration_str = f"{minutes:02d}:{seconds:02d}"
            else:
                duration_ms = 1
                duration_str = "00:00"

            self._current_track_length_readable = duration_str
            self._current_track_length = duration_ms
            self._current_track_progress = current_playback.get("progress_ms", {})

            self._current_track_percent = int(
                (self._current_track_progress / self._current_track_length) * 100
            )

            self._current_artist_id = (
                current_playback.get("item", {}).get("artists", [{}])[0].get("id")
            )

            self._current_album_id = (
                current_playback.get("item", {}).get("album", {}).get("id")
            )

            self._current_album_img = (
                current_playback.get("item", {}).get("album", {}).get("images")
            )

            self._current_album_name = (
                current_playback.get("item", {}).get("album", {}).get("name")
            )

            self._current_track_isrc = (
                current_playback.get("item", {})
                .get("external_ids", {})
                .get("isrc", "")
                .upper()
            )

            self._current_device_id = current_playback.get("device", {}).get("id")

        if self._current_album_img is None:
            self._spotify_album_img = None
        else:
            self._spotify_album_img = self._current_album_img[0].get("url", "")

        self._extra_attributes = {
            "media_artist_id": self._current_artist_id,
            "media_album_id": self._current_album_id,
            "media_album_img": self._spotify_album_img,
            "media_track_length": self._current_track_length_readable,
            "media_track_percent": self._current_track_percent,
            "media_track_isrc": self._current_track_isrc,
            "media_current_device_id": self._current_device_id,
        }

    @callback
    def _handle_devices_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.enabled:
            return
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.data.devices.async_add_listener(self._handle_devices_update)
        )
