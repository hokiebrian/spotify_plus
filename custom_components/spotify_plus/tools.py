"""Spotify Music Machine."""

from typing import Any, Dict, Optional
import random
import asyncio
from datetime import datetime
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.entity import DeviceInfo
from . import HomeAssistantSpotifyData
from .const import (
    DOMAIN,
    _LOGGER,
    MUSIC_REC_TOLERANCE,
    MUSIC_REC_TRACK_COUNT,
    MUSIC_PLAYLIST_DESC,
)


class SpotifyMusicMachine(RestoreEntity):
    """Build a Custom Music Experience."""

    platform = "sensor"
    config_flow_class = None

    _attr_icon = "mdi:playlist-plus"

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
        self._track_count = MUSIC_REC_TRACK_COUNT
        self._tolerance = MUSIC_REC_TOLERANCE
        self._playlist_desc = MUSIC_PLAYLIST_DESC

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, user_id)},
        )

    async def async_added_to_hass(self):
        self.hass.services.async_register(
            DOMAIN, "spotify_music_machine", self.spotify_music_machine
        )
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._state = last_state.state
            self._extra_attributes = dict(last_state.attributes)

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Spotify Music Machine"

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._state is not None:
            return self._state
        return "No Recent Activity"

    @property
    def unique_id(self):
        """Unique ID for sensor"""
        return f"SpotifyMusicMachine_{self._id}"

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the sensor."""
        return self._extra_attributes

    async def spotify_music_machine(self, call):
        """Build New Set of Songs (Tracks)."""
        params = self._initialize_params(call)
        playlist_name = call.data.get("name", "Spotify Plus")
        artist_count = int(float(call.data.get("count", 100)))
        artist_focus = call.data.get("focus", False)
        time_range = call.data.get("time_range", "long_term")
        play_now = call.data.get("play_now", False)
        create_playlist = call.data.get("create_playlist", True)

        existing_pl_flag = False
        playlist_desc = self._playlist_desc
        context_playlist = "Queue Only"
        artists = []
        tracks = []
        now = datetime.now()
        random_artist_names = []
        random_track_names = []
        seed_details = []
        unique_genres = []
        formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")
        params = {
            "limit": 100,
            "country": self._user_country,
        }

        device_name = call.data.get("device_name", None)
        if device_name:
            await self._transfer_playback(device_name)

        playlists = await self.hass.async_add_executor_job(
            self.data.client.current_user_playlists
        )

        existing_pl_flag, existing_playlist_uri, existing_playlist_item_uris = (
            await self._check_existing_playlist(playlists, call)
        )

        if not (params.get("seed_artists") or params.get("seed_genres") or params.get("seed_tracks")):
            rec_tracks, seed_details = await self._get_recommendations_without_seeds(
                call, params, artist_count, artist_focus, time_range
            )
        else:
            rec_tracks, seed_details = await self._get_recommendations_with_seeds(
                call, params
            )

        rec_tracks = random.sample(rec_tracks, min(len(rec_tracks), 100))
        random.shuffle(rec_tracks)
        _LOGGER.debug("Spotify Recommended Tracks Selected")

        if create_playlist:
            context_playlist = await self._create_or_update_playlist(
                existing_pl_flag, existing_playlist_uri, rec_tracks, playlist_name, playlist_desc
            )

        if play_now:
            await self._start_playback(context_playlist, rec_tracks)

        self._update_state_and_attributes(
            playlist_name, context_playlist, formatted_time, seed_details, params, random_track_names, random_artist_names
        )

    def _initialize_params(self, call):
        """Initialize parameters for recommendations."""
        params = {
            "limit": self._track_count,
            "country": self._user_country,
        }
        tolerance = float(call.data.get("tolerance", self._tolerance)) / 100

        self._set_target_params(call, params, tolerance, "valence")
        self._set_target_params(call, params, tolerance, "energy")
        self._set_target_params(call, params, tolerance, "acousticness")
        self._set_target_params(call, params, tolerance, "danceability")
        self._set_target_params(call, params, tolerance, "instrumentalness")
        self._set_target_params(call, params, tolerance, "liveness")
        self._set_target_params(call, params, tolerance, "speechiness")
        self._set_target_params(call, params, tolerance, "popularity", is_int=True)

        return params

    def _set_target_params(self, call, params, tolerance, param, is_int=False):
        """Set target parameters with min and max values."""
        target_value = call.data.get(param)
        if target_value is not None:
            try:
                target_value = int(float(target_value)) if is_int else float(target_value) / 100
                min_value = max(target_value - tolerance, 0)
                max_value = min(target_value + tolerance, 1.0 if not is_int else 100)
                params[f"min_{param}"] = round(min_value, 2)
                params[f"max_{param}"] = round(max_value, 2)
            except ValueError as e:
                _LOGGER.error(f"Error setting target parameter {param}: {e}")

    async def _transfer_playback(self, device_name):
        """Transfer playback to a specified device."""
        for device in self.data.devices.data:
            if device["name"] == device_name:
                await self.hass.async_add_executor_job(
                    self.data.client.transfer_playback, device["id"]
                )

    async def _check_existing_playlist(self, playlists, call):
        """Check if the playlist already exists and remove its items if necessary."""
        existing_pl_flag = False
        existing_playlist_uri = None
        existing_playlist_item_uris = []

        playlist_name = call.data.get("name", "Spotify Plus")
        if call.data.get("create_playlist", True):
            for playlist in playlists["items"]:
                if playlist["name"] == playlist_name:
                    existing_pl_flag = True
                    existing_playlist_uri = playlist["uri"]
                    existing_playlist_items = await self.hass.async_add_executor_job(
                        self.data.client.playlist_items,
                        existing_playlist_uri,
                        "items(track(uri))",
                        100,
                    )
                    existing_playlist_item_uris = [
                        item["track"]["uri"]
                        for item in existing_playlist_items["items"]
                    ]
                    await self.hass.async_add_executor_job(
                        self.data.client.playlist_remove_all_occurrences_of_items,
                        existing_playlist_uri,
                        existing_playlist_item_uris,
                    )

        return existing_pl_flag, existing_playlist_uri, existing_playlist_item_uris

    async def _get_recommendations_without_seeds(self, call, params, artist_count, artist_focus, time_range):
        """Get recommendations without user-provided seeds."""
        rec_tracks = []
        seed_details = {}
        
        resultst1_task = self.hass.async_add_executor_job(
            self.data.client.current_user_top_tracks, 49, 0, time_range
        )
        resultst2_task = self.hass.async_add_executor_job(
            self.data.client.current_user_top_tracks, 50, 49, time_range
        )
        resultst1, resultst2 = await asyncio.gather(resultst1_task, resultst2_task)

        top_tracks = [
            (track["id"], track["name"])
            for result in (resultst1, resultst2)
            for track in result["items"]
        ]
        random_tracks = random.sample(top_tracks, k=5)
        random_track_ids, random_track_names = zip(*random_tracks)

        if artist_focus:
            results = await self.hass.async_add_executor_job(
                self.data.client.current_user_followed_artists, 50
            )
            artists = [
                (artist["id"], artist["name"], artist["genres"])
                for artist in results["artists"]["items"]
            ]
        else:
            results1_task = self.hass.async_add_executor_job(
                self.data.client.current_user_top_artists, 49, 0, time_range
            )
            results2_task = self.hass.async_add_executor_job(
                self.data.client.current_user_top_artists, 50, 49, time_range
            )
            results1, results2 = await asyncio.gather(results1_task, results2_task)

            artists = [
                (artist["id"], artist["name"], artist["genres"])
                for result in (results1, results2)
                for artist in result["items"]
            ]
            artists = artists[:artist_count]

        random_artists = random.sample(artists, k=10)
        random_artist_ids, random_artist_names, unique_genres = zip(*random_artists)
        unique_genres = list(
            set(genre for artist in random_artists for genre in artist[2])
        )
        unique_genres = sorted(unique_genres)

        params1, params2, params3 = params.copy(), params.copy(), params.copy()
        params1["seed_artists"] = list(random_artist_ids[:5])
        params2["seed_artists"] = list(random_artist_ids[-5:])
        params3["seed_tracks"] = list(random_track_ids[:5])

        recs1_task = self.hass.async_add_executor_job(
            lambda: self.data.client.recommendations(**params1)
        )
        recs2_task = self.hass.async_add_executor_job(
            lambda: self.data.client.recommendations(**params2)
        )
        recs3_task = self.hass.async_add_executor_job(
            lambda: self.data.client.recommendations(**params3)
        )
        _LOGGER.debug("Spotify Parameters %s", params)

        recs1, recs2, recs3 = await asyncio.gather(recs1_task, recs2_task, recs3_task)

        rec_tracks = list(
            set(
                [tracks["uri"] for tracks in recs1["tracks"]]
                + [tracks["uri"] for tracks in recs2["tracks"]]
            )
        )

        if len(rec_tracks) < int(self._track_count / 2):
            recs3_tracks = [track["uri"] for track in recs3["tracks"]]
            random.shuffle(recs3_tracks)
            rec_tracks = list(
                set(rec_tracks + recs3_tracks[: int(self._track_count / 4)])
            )

        seed_details = {
            "Recs1": {"artists": list(random_artist_names[:5])},
            "Recs2": {"artists": list(random_artist_names[-5:])},
            "Recs3": {"tracks": list(random_track_names[:5])},
        }

        return rec_tracks, seed_details

    async def _get_recommendations_with_seeds(self, call, params):
        """Get recommendations with user-provided seeds."""
        paramsx = params.copy()
        rec_tracks = []
        seed_details = {}
        random_artist_names = []
        unique_genres = []
        random_track_names = []

        seed_artists = call.data.get("seed_artists", "").replace(" ", "").split(",")
        seed_genres = call.data.get("seed_genres", "").replace(" ", "").split(",")
        seed_tracks = call.data.get("seed_tracks", "").replace(" ", "").split(",")

        if seed_artists:
            paramsx["seed_artists"] = seed_artists
            artists_info = await self.hass.async_add_executor_job(
                self.data.client.artists, seed_artists
            )
            random_artist_names = [artist["name"] for artist in artists_info["artists"]]

        if seed_genres:
            paramsx["seed_genres"] = seed_genres
            unique_genres = seed_genres

        if seed_tracks:
            paramsx["seed_tracks"] = seed_tracks
            tracks_info = await self.hass.async_add_executor_job(
                self.data.client.tracks, seed_tracks
            )
            random_track_names = [track["name"] for track in tracks_info["tracks"]]

        _LOGGER.debug("User Provided Seed Params: %s", paramsx)

        recsx = await self.hass.async_add_executor_job(
            lambda: self.data.client.recommendations(**paramsx)
        )

        seed_details = {
            "Recs": {
                "artists": random_artist_names,
                "tracks": random_track_names,
                "genres": unique_genres,
            },
        }

        rec_tracks = [tracks["uri"] for tracks in recsx["tracks"]]

        return rec_tracks, seed_details

    async def _create_or_update_playlist(
        self, existing_pl_flag, existing_playlist_uri, rec_tracks, playlist_name, playlist_desc
    ):
        """Create or update a playlist with the recommended tracks."""
        context_playlist = "Queue Only"

        try:
            if existing_pl_flag:
                await self.hass.async_add_executor_job(
                    self.data.client.user_playlist_add_tracks,
                    self._id,
                    existing_playlist_uri,
                    list(rec_tracks),
                )
                await self.hass.async_add_executor_job(
                    self.data.client.user_playlist_change_details,
                    self._id,
                    existing_playlist_uri,
                    playlist_name,
                    False,
                    False,
                    playlist_desc,
                )
                context_playlist = existing_playlist_uri
            else:
                create_playlist = await self.hass.async_add_executor_job(
                    self.data.client.user_playlist_create,
                    self._id,
                    playlist_name,
                    False,
                    False,
                    playlist_desc,
                )
                context_playlist = create_playlist["uri"]
                await self.hass.async_add_executor_job(
                    self.data.client.user_playlist_add_tracks,
                    self._id,
                    context_playlist,
                    list(rec_tracks),
                )
        except Exception as err:
            _LOGGER.error("Playlist Creation Failure: %s", err)

        _LOGGER.debug("Playlist URI %s", context_playlist)
        return context_playlist

    async def _start_playback(self, context_playlist, rec_tracks):
        """Start playback of the recommended tracks."""
        try:
            if context_playlist == "Queue Only":
                await self.hass.async_add_executor_job(
                    self.data.client.start_playback, None, None, rec_tracks
                )
                _LOGGER.debug("Queue Created")
            else:
                await self.hass.async_add_executor_job(
                    self.data.client.start_playback, None, context_playlist
                )
                _LOGGER.debug("Playlist %s Created", context_playlist)
        except Exception as e:
            _LOGGER.error(f"Error occurred during playback: {e}")

    def _update_state_and_attributes(
        self, playlist_name, context_playlist, formatted_time, seed_details, params, random_track_names, random_artist_names
    ):
        """Update the state and attributes of the sensor."""
        results_meta = {
            "Playlist Name": playlist_name,
            "Playlist ID": context_playlist,
            "Number of Tracks": len(random_track_names),
            "Artists": seed_details.get("Recs", {}).get("artists", []),
            "Tracks": seed_details.get("Recs", {}).get("tracks", []),
            "Genres": seed_details.get("Recs", {}).get("genres", []),
            "Stats": params,
            "Seed Details": seed_details,
        }

        self._state = formatted_time
        self._extra_attributes = results_meta
        self.async_write_ha_state()
