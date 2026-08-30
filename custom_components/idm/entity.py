"""Base entity for the IDM integration."""

from __future__ import annotations

from datetime import datetime
import logging

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IDMDataUpdateCoordinator
from .const import ATTRIBUTION, DOMAIN, NAME, UNRECORDED_ATTRIBUTES, VERSION, WEBSITE
from .models import IDMItem
from .utils import sensor_name

_LOGGER = logging.getLogger(__name__)


class IDMEntity(CoordinatorEntity[IDMDataUpdateCoordinator]):
    """Base IDM entity."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = False
    _unrecorded_attributes = frozenset(UNRECORDED_ATTRIBUTES)

    def __init__(
        self,
        coordinator: IDMDataUpdateCoordinator,
        description: EntityDescription,
        item: IDMItem,
    ) -> None:
        """Initialize an IDM entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._item = item
        self._key = item.key
        self.client = coordinator.client
        self.last_synced = datetime.now()

        self._attr_unique_id = f"{DOMAIN}_{item.key}"
        self._attr_name = sensor_name(item.name)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(item.device_key))},
            name=f"{NAME} {item.device_name}",
            manufacturer=NAME,
            configuration_url=WEBSITE,
            entry_type=DeviceEntryType.SERVICE,
            model=item.device_model,
            sw_version=VERSION,
        )
        _LOGGER.debug("[IDMEntity|init] %s", self._key)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        item = (self.coordinator.data or {}).get(self._key)
        if item is None:
            _LOGGER.debug(
                "[IDMEntity|_handle_coordinator_update] %s not present in the "
                "latest refresh; keeping the previous state",
                self._attr_unique_id,
            )
            return
        self._item = item
        self.last_synced = datetime.now()
        self.async_write_ha_state()

    @property
    def item(self) -> IDMItem:
        """Return the item backing this entity."""
        return self._item

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return super().available and self._item is not None
