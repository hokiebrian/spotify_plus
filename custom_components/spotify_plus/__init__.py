"""Spotify Tools Custom Component."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict

import aiohttp
import requests
from spotipy import Spotify, SpotifyException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, _LOGGER, SPOTIFY_SCOPES

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)
PLATFORMS = [Platform.SENSOR, Platform.MEDIA_PLAYER]
UPDATE_INTERVAL = timedelta(seconds=150)


@dataclass
class HomeAssistantSpotifyData:
    """Spotify data stored in the Home Assistant data object."""

    client: Spotify
    current_user: Dict[str, Any]
    devices: DataUpdateCoordinator[Dict[str, Any]]
    session: OAuth2Session


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Spotify integration."""
    _LOGGER.info("Setting up Spotify integration")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Spotify from a config entry."""
    _LOGGER.info(f"Setting up Spotify entry: {entry.title}")

    try:
        implementation = await async_get_config_entry_implementation(hass, entry)
        session = OAuth2Session(hass, entry, implementation)
        await session.async_ensure_token_valid()
    except aiohttp.ClientError as err:
        _LOGGER.error(f"Failed to ensure token is valid: {err}")
        raise ConfigEntryNotReady from err

    spotify = Spotify(auth=session.token["access_token"])

    try:
        current_user = await hass.async_add_executor_job(spotify.me)
    except SpotifyException as err:
        _LOGGER.error(f"Failed to fetch current user: {err}")
        raise ConfigEntryNotReady from err

    if not current_user:
        _LOGGER.error("No current user found")
        raise ConfigEntryNotReady

    async def _update_devices() -> Dict[str, Any]:
        if not session.valid_token:
            await session.async_ensure_token_valid()
            await hass.async_add_executor_job(
                spotify.set_auth, session.token["access_token"]
            )

        try:
            devices: Dict[str, Any] | None = await hass.async_add_executor_job(
                spotify.devices
            )
        except (requests.RequestException, SpotifyException) as err:
            _LOGGER.error(f"Failed to fetch devices: {err}")
            raise UpdateFailed from err

        if devices is None:
            _LOGGER.warning("No devices found")
            return {}

        return devices.get("devices", [])

    device_coordinator: DataUpdateCoordinator[Dict[str, Any]] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{entry.title} Devices",
        update_interval=UPDATE_INTERVAL,
        update_method=_update_devices,
    )
    await device_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = HomeAssistantSpotifyData(
        client=spotify,
        current_user=current_user,
        devices=device_coordinator,
        session=session,
    )

    if not set(session.token["scope"].split(" ")).issuperset(SPOTIFY_SCOPES):
        _LOGGER.error("Insufficient scopes for the token")
        raise ConfigEntryAuthFailed

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info(f"Spotify entry setup complete: {entry.title}")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Spotify config entry."""
    _LOGGER.info(f"Unloading Spotify entry: {entry.title}")
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        del hass.data[DOMAIN][entry.entry_id]
    _LOGGER.info(f"Spotify entry unloaded: {entry.title}")
    return unload_ok
