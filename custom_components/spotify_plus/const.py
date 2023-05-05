""" Constants for Spotify Plus."""
import logging

from homeassistant.components.media_player import MediaType

DOMAIN = "spotify_plus"
MUSIC_REC_TOLERANCE = .20
MUSIC_REC_TRACK_COUNT = 100
MUSIC_PLAYLIST_DESC = "Created by Spotify+ Tools for Home Assistant"

MM_API = "https://api.musixmatch.com/ws/1.1/track.get"

_LOGGER = logging.getLogger(__name__)

SPOTIFY_SCOPES = [
    "user-modify-playback-state",
    "user-read-playback-state",
    "user-read-private",
    "playlist-read-private",
    "playlist-read-collaborative",
    "user-library-read",
    "user-top-read",
    "user-read-playback-position",
    "user-read-recently-played",
    "user-follow-read",
    "user-follow-modify",
    "user-read-currently-playing",
    "playlist-modify-private",
    "playlist-modify-public",
    "user-library-modify",
]

MEDIA_PLAYER_PREFIX = "spotify://"
MEDIA_TYPE_SHOW = "show"

PLAYABLE_MEDIA_TYPES = [
    MediaType.PLAYLIST,
    MediaType.ALBUM,
    MediaType.ARTIST,
    MediaType.EPISODE,
    MEDIA_TYPE_SHOW,
    MediaType.TRACK,
]