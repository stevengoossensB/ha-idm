"""The IDM integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import IDMClient
from .const import COORDINATOR_UPDATE_INTERVAL, DOMAIN, PLATFORMS, STARTUP
from .exceptions import BadCredentialsException, IDMServiceException
from .models import IDMItem

_LOGGER = logging.getLogger(__name__)

type IDMConfigEntry = ConfigEntry[IDMDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: IDMConfigEntry) -> bool:
    """Set up IDM from a config entry."""
    _LOGGER.info(STARTUP)

    client = IDMClient(
        email=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )

    coordinator = IDMDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: IDMConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: IDMConfigEntry) -> None:
    """Reload the config entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


class IDMDataUpdateCoordinator(DataUpdateCoordinator[dict[str, IDMItem]]):
    """Fetch data from the Mijn IDM portal on a schedule."""

    config_entry: IDMConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: IDMConfigEntry,
        client: IDMClient,
        update_interval: timedelta = COORDINATOR_UPDATE_INTERVAL,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> dict[str, IDMItem]:
        """Fetch the latest data from the portal."""
        try:
            data = await self.hass.async_add_executor_job(self.client.fetch_data)
        except BadCredentialsException as err:
            raise ConfigEntryAuthFailed("The IDM portal rejected the stored credentials") from err
        except IDMServiceException as err:
            raise UpdateFailed(f"The IDM portal is unavailable: {err}") from err

        if not data:
            raise UpdateFailed("The IDM portal returned no usable data")
        return data
