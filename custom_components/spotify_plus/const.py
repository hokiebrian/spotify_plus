"""Constants for Spotify Plus integration."""

import logging

from homeassistant.components.media_player import MediaType

# Domain for the integration
DOMAIN = "spotify_plus"

# Constants for music recommendations
MUSIC_REC_TOLERANCE = 0.20
MUSIC_REC_TRACK_COUNT = 100
MUSIC_PLAYLIST_DESC = "Created by Spotify+ Tools for Home Assistant"

# API endpoint for Musixmatch
MM_API = "https://api.musixmatch.com/ws/1.1/track.get"

# Logger instance for the integration
_LOGGER = logging.getLogger(__name__)

# Spotify OAuth2 scopes
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

# Prefix for Spotify media player
MEDIA_PLAYER_PREFIX = "spotify://"

# Media type for shows
MEDIA_TYPE_SHOW = "show"

# List of playable media types
PLAYABLE_MEDIA_TYPES = [
    MediaType.PLAYLIST,
    MediaType.ALBUM,
    MediaType.ARTIST,
    MediaType.EPISODE,
    MEDIA_TYPE_SHOW,
    MediaType.TRACK,
]
