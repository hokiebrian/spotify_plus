"""Spotify Playlist Tools."""

from typing import Any, Dict, Optional
import asyncio
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.entity import DeviceInfo
from . import HomeAssistantSpotifyData
from .const import DOMAIN, _LOGGER

class SpotifyPlaylists(RestoreEntity):
    """Spotify Playlist Tools."""  

    platform = "sensor"
    config_flow_class = None

    _attr_icon = "mdi:format-list-bulleted"

    def __init__(self, data: HomeAssistantSpotifyData, user_id: str, name: str, user_country: str):
        """Initialize the sensor."""
        self.data = data
        self._id = user_id
        self._name = name
        self._user_country = user_country
        self._state = None
        self._extra_attributes: Dict[str, Any] = {}
        self._track_count = 100
        self._tolerance = .25

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, user_id)},
        )

    async def async_added_to_hass(self):
        self.hass.services.async_register(DOMAIN, "spotify_playlists", self.spotify_playlists)
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._state = last_state.state
            self._extra_attributes = dict(last_state.attributes)

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Spotify Playlist Info"

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._state is not None:
            return self._state
        return "No Data"

    @property
    def unique_id(self):
        """Unique ID for sensor"""
        return f"SpotifyPlaylistTools_{self._id}"

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the sensor."""
        return self._extra_attributes

    async def spotify_playlists(self, call):
        """ Build Playlist Details """
        ## Limit of 10 concurrent connections to Spotify API, reduced here to 8 to prevent pile up.
        CONNECTION_LIMIT = 8
        semaphore = asyncio.Semaphore(CONNECTION_LIMIT)

        playlists = []
        offset = 0
        limit = 20

        while True:
            user_playlists = await self.hass.async_add_executor_job(
                self.data.client.current_user_playlists, limit, offset
                )

            ## Check for playlists with no items
            valid_playlists = [playlist for playlist in user_playlists['items'] if playlist['tracks']['total'] != 0]
            playlists.extend(valid_playlists)

            offset += limit
            if not user_playlists['next']:
                _LOGGER.debug("Playlist Cycles complete %s", offset)
                break

        async def analyze_playlist_async(playlist_id):
            """ Goes Deep on each playlist track - LIMIT OF 100 TRACKS!!! """
            playlist_tracks = await self.hass.async_add_executor_job(
                self.data.client.playlist_items, playlist_id,
                'items(track(name,uri,popularity))',
                100,
                0,
                self._user_country
                )
    
            track_uris = [item['track']['uri'] for item in playlist_tracks['items']]
            track_popularity = [item['track']['popularity'] for item in playlist_tracks['items']]
            track_analysis = await self.hass.async_add_executor_job(
                self.data.client.audio_features, track_uris
                )

            num_tracks = len(track_analysis)
            analysis_attributes = ['energy',
            'valence',
            'acousticness',
            'instrumentalness',
            'liveness',
            'speechiness',
            'danceability'
            ]
            analysis_totals = {attr: 0 for attr in analysis_attributes}
            popularity_total = sum(track_popularity)

            for track in track_analysis:
                for attr in analysis_attributes:
                    analysis_totals[attr] += track[attr]

            avg_analysis = {
                f'avg{attr.capitalize()}': int(total / num_tracks * 100)
                for attr, total in analysis_totals.items()
            }

            avg_analysis['avgPopularity'] = int(popularity_total / num_tracks)
            avg_analysis['tracks'] = num_tracks

            return avg_analysis

        async def process_playlist_async(playlist):
            """ Get Full Details, limit to provided connection limit """
            async with semaphore:
                playlist_id = playlist.get('uri', '')
                analysis = await analyze_playlist_async(playlist_id)

                base_info = {
                    'name': playlist.get('name', ''),
                    'uri': playlist.get('uri', ''),
                    'image': (
                        playlist['images'][0]['url']
                        if 'images' in playlist and len(playlist['images']) > 0
                        else ''
                    ),
                    'owner': (
                        playlist['owner']['display_name']
                        if 'owner' in playlist and 'display_name' in playlist['owner']
                        else ''
                    ),
                    'description': playlist.get('description', ''),
                }

                return {**base_info, **analysis}

        ## Perform massive playlist data gathering, keeping below connection threshold
        coroutines = [process_playlist_async(playlist) for playlist in playlists]
        results = await asyncio.gather(*coroutines)
        _LOGGER.debug("All Playlists analyzed")

        ## Sort properly with Daily Mix playlists at top
        daily_mix = [result for result in results if "Daily Mix" in result['name']]
        playlist_items = [result for result in results if "Daily Mix" not in result['name']]

        sorted_playlists = sorted(
            daily_mix,
            key=lambda x: (x['owner'], x['name'])) + sorted(
                playlist_items,
                key=lambda x: (x['owner'], x['name']
                )
            )

        self._state = f"{len(sorted_playlists)} Playlists"
        self._extra_attributes = {"playlists": sorted_playlists}

        self.async_write_ha_state()
