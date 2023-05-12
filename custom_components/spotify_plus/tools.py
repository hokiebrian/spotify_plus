"""Spotify Music Machine."""

from typing import Any, Dict, Optional
import random
import asyncio
from datetime import datetime
from homeassistant.exceptions import HomeAssistantError
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
        """Build New Set of Songs(Tracks)"""
        try:
            MIN_MAX_TOLERANCE = float(call.data["tolerance"]) / 100
        except KeyError:
            MIN_MAX_TOLERANCE = self._tolerance
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
        formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")
        params = {
            "limit": 100,
            "country": self._user_country,
        }

        device_name = call.data.get("device_name", None)
        if device_name:
            for device in self.data.devices.data:
                if device["name"] == device_name:
                    self.hass.async_add_executor_job(
                        self.data.client.transfer_playback, device["id"]
                    )
        try:
            SEED_ARTISTS = call.data["seed_artists"].replace(" ", "").split(",")
        except (TypeError, ValueError, KeyError):
            SEED_ARTISTS = []

        try:
            SEED_GENRES = call.data["seed_genres"].replace(" ", "").split(",")
        except (TypeError, ValueError, KeyError):
            SEED_GENRES = []

        try:
            SEED_TRACKS = call.data["seed_tracks"].replace(" ", "").split(",")
        except (TypeError, ValueError, KeyError):
            SEED_TRACKS = []

        TARGET_VALENCE = call.data.get("valence", None)
        if TARGET_VALENCE is not None:
            TARGET_VALENCE = float(TARGET_VALENCE) / 100
            TARGET_VALENCE_MIN = round(max(TARGET_VALENCE - MIN_MAX_TOLERANCE, 0), 2)
            TARGET_VALENCE_MAX = round(min(TARGET_VALENCE + MIN_MAX_TOLERANCE, 1.0), 2)
            params["min_valence"] = TARGET_VALENCE_MIN
            params["max_valence"] = TARGET_VALENCE_MAX

        TARGET_ENERGY = call.data.get("energy", None)
        if TARGET_ENERGY is not None:
            TARGET_ENERGY = float(TARGET_ENERGY) / 100
            TARGET_ENERGY_MIN = round(max(TARGET_ENERGY - MIN_MAX_TOLERANCE, 0), 2)
            TARGET_ENERGY_MAX = round(min(TARGET_ENERGY + MIN_MAX_TOLERANCE, 1.0), 2)
            if TARGET_ENERGY == 1:
                TARGET_ENERGY_MIN = 0.90
            params["min_energy"] = TARGET_ENERGY_MIN
            params["max_energy"] = TARGET_ENERGY_MAX

        TARGET_ACOUSTIC = call.data.get("acousticness", None)
        if TARGET_ACOUSTIC is not None:
            TARGET_ACOUSTIC = float(TARGET_ACOUSTIC) / 100
            TARGET_ACOUSTIC_MIN = round(max(TARGET_ACOUSTIC - MIN_MAX_TOLERANCE, 0), 2)
            TARGET_ACOUSTIC_MAX = round(
                min(TARGET_ACOUSTIC + MIN_MAX_TOLERANCE, 1.0), 2
            )
            ## Clamping to get more accurate results
            if TARGET_ACOUSTIC == 0:
                TARGET_ACOUSTIC_MAX = 0.10
            if 0.10 <= TARGET_ACOUSTIC <= 0.20:
                TARGET_ACOUSTIC_MIN = 0.01
            params["min_acousticness"] = TARGET_ACOUSTIC_MIN
            params["max_acousticness"] = TARGET_ACOUSTIC_MAX

        TARGET_DANCE = call.data.get("danceability", None)
        if TARGET_DANCE is not None:
            TARGET_DANCE = float(TARGET_DANCE) / 100
            TARGET_DANCE_MIN = round(max(TARGET_DANCE - MIN_MAX_TOLERANCE, 0), 2)
            TARGET_DANCE_MAX = round(min(TARGET_DANCE + MIN_MAX_TOLERANCE, 1.0), 2)
            params["min_danceability"] = TARGET_DANCE_MIN
            params["max_danceability"] = TARGET_DANCE_MAX

        TARGET_INSTRUMENTAL = call.data.get("instrumentalness", None)
        if TARGET_INSTRUMENTAL is not None:
            TARGET_INSTRUMENTAL = float(TARGET_INSTRUMENTAL) / 100
            TARGET_INSTRUMENTAL_MIN = round(
                max(TARGET_INSTRUMENTAL - MIN_MAX_TOLERANCE, 0), 2
            )
            TARGET_INSTRUMENTAL_MAX = round(
                min(TARGET_INSTRUMENTAL + MIN_MAX_TOLERANCE, 1.0), 2
            )
            params["min_instrumentalness"] = TARGET_INSTRUMENTAL_MIN
            params["max_instrumentalness"] = TARGET_INSTRUMENTAL_MAX

        TARGET_LIVENESS = call.data.get("liveness", None)
        if TARGET_LIVENESS is not None:
            TARGET_LIVENESS = float(TARGET_LIVENESS) / 100
            TARGET_LIVENESS_MIN = round(max(TARGET_LIVENESS - MIN_MAX_TOLERANCE, 0), 2)
            TARGET_LIVENESS_MAX = round(
                min(TARGET_LIVENESS + MIN_MAX_TOLERANCE, 1.0), 2
            )
            params["min_liveness"] = TARGET_LIVENESS_MIN
            params["max_liveness"] = TARGET_LIVENESS_MAX

        TARGET_SPEECHINESS = call.data.get("speechiness", None)
        if TARGET_SPEECHINESS is not None:
            TARGET_SPEECHINESS = float(TARGET_SPEECHINESS) / 100
            TARGET_SPEECHINESS_MIN = round(
                max(TARGET_SPEECHINESS - MIN_MAX_TOLERANCE, 0), 2
            )
            TARGET_SPEECHINESS_MAX = round(
                min(TARGET_SPEECHINESS + MIN_MAX_TOLERANCE, 1.0), 2
            )
            params["min_speechinness"] = TARGET_SPEECHINESS_MIN
            params["max_speechiness"] = TARGET_SPEECHINESS_MAX

        TARGET_POP = call.data.get("popularity", None)
        if TARGET_POP is not None:
            TARGET_POP = int(float(TARGET_POP))
            TARGET_POP_MIN = int(max(TARGET_POP - (MIN_MAX_TOLERANCE * 100), 0))
            TARGET_POP_MAX = int(min(TARGET_POP + (MIN_MAX_TOLERANCE * 100), 100))
            params["min_popularity"] = TARGET_POP_MIN
            params["max_popularity"] = TARGET_POP_MAX

        playlists = await self.hass.async_add_executor_job(
            self.data.client.current_user_playlists
        )

        if create_playlist:
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

        if not (SEED_ARTISTS or SEED_GENRES or SEED_TRACKS):
            ## This is a hack to get beyond 50 Top Tracks to 99
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
            tracks.extend(top_tracks)

            random_tracks = random.sample(tracks, k=5)
            random_track_ids, random_track_names = zip(*random_tracks)

            if artist_focus:
                ## Option for playlist from my followed artists or my top artists. If my artists, no time_range applies
                results = await self.hass.async_add_executor_job(
                    self.data.client.current_user_followed_artists, 50
                )

                while results:
                    artists.extend(
                        (artist["id"], artist["name"], artist["genres"])
                        for artist in results["artists"]["items"]
                    )
                    if results["artists"]["next"]:
                        results = await self.hass.async_add_executor_job(
                            self.data.client.next, (results["artists"])
                        )
                    else:
                        break

            else:
                ## Spotify is only supposed to allow 50 Top Artists. Calling the max with an offset of 49 can get a total of 99
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

            _LOGGER.debug("Spotify Artist List Retrieved")

            random_artists = random.sample(artists, k=10)
            random_artist_ids, random_artist_names, unique_genres = zip(*random_artists)
            unique_genres = list(
                set(genre for artist in random_artists for genre in artist[2])
            )
            unique_genres = sorted(unique_genres)

            params1 = params.copy()
            params1["seed_artists"] = list(random_artist_ids[:5])

            params2 = params.copy()
            params2["seed_artists"] = list(random_artist_ids[-5:])

            params3 = params.copy()
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

            recs1, recs2, recs3 = await asyncio.gather(
                recs1_task, recs2_task, recs3_task
            )

            rec_tracks = list(
                set(
                    [tracks["uri"] for tracks in recs1["tracks"]]
                    + [tracks["uri"] for tracks in recs2["tracks"]]
                )
            )

            ## Checks if song list is less than 50% of the intended size. If so, add in 25% from Top Tracks seed.
            if len(rec_tracks) < int(self._track_count / 2):
                recs3_tracks = [track["uri"] for track in recs3["tracks"]]
                random.shuffle(recs3_tracks)  # Shuffle the tracks in place
                rec_tracks = list(
                    set(
                        [track["uri"] for track in recs1["tracks"]]
                        + [track["uri"] for track in recs2["tracks"]]
                        + recs3_tracks[: int(self._track_count / 4)]
                    )
                )

            seed_details = {
                "Recs1": recs1["seeds"],
                "Recs2": recs2["seeds"],
                "Recs3": recs3["seeds"],
            }

        else:
            paramsx = params.copy()

            if len(SEED_ARTISTS) > 0:
                paramsx["seed_artists"] = SEED_ARTISTS
                artists_info = await self.hass.async_add_executor_job(
                    self.data.client.artists, SEED_ARTISTS
                )
                random_artist_names = [
                    artist["name"] for artist in artists_info["artists"]
                ]

            if len(SEED_GENRES) > 0:
                paramsx["seed_genres"] = SEED_GENRES
                unique_genres = SEED_GENRES

            if len(SEED_TRACKS) > 0:
                paramsx["seed_tracks"] = SEED_TRACKS
                tracks_info = await self.hass.async_add_executor_job(
                    self.data.client.tracks, SEED_TRACKS
                )
                random_track_names = [track["name"] for track in tracks_info["tracks"]]

            _LOGGER.debug(f"User Provided Seed Params: {paramsx}")

            recsx = await self.hass.async_add_executor_job(
                lambda: self.data.client.recommendations(**paramsx)
            )

            seed_details = {
                "Recs": recsx["seeds"],
            }

            rec_tracks = list([tracks["uri"] for tracks in recsx["tracks"]])

        ## Shuffle it up a few times
        rec_tracks = random.sample(rec_tracks, min(len(rec_tracks), 100))
        random.shuffle(rec_tracks)

        _LOGGER.debug("Spotify Recommended Tracks Selected")

        if create_playlist:
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

        if play_now and not create_playlist:
            await self.hass.async_add_executor_job(
                self.data.client.start_playback, None, None, rec_tracks
            )
            playlist_name = "Queue Only"
            _LOGGER.debug("Queue Created")

        if play_now and create_playlist:
            await self.hass.async_add_executor_job(
                self.data.client.start_playback, None, context_playlist
            )
            _LOGGER.debug("Playlist %s Created", context_playlist)

        results_meta = {
            "Playlist Name": playlist_name,
            "Playlist ID": context_playlist,
            "Number of Tracks": len(rec_tracks),
            "Artists": random_artist_names,
            "Tracks": list(random_track_names),
            "Genres": unique_genres,
            "Stats": params,
            "Seed Details": seed_details,
        }

        self._state = formatted_time
        self._extra_attributes = results_meta
        self.async_write_ha_state()
