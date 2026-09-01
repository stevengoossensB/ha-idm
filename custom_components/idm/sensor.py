"""Sensor platform for the IDM integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CURRENCY_EURO, PERCENTAGE, UnitOfMass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import IDMConfigEntry, IDMDataUpdateCoordinator
from .const import DOMAIN
from .entity import IDMEntity
from .models import IDMItem

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class IDMSensorDescription(SensorEntityDescription):
    """Describes an IDM sensor type."""


SENSOR_DESCRIPTIONS: list[IDMSensorDescription] = [
    IDMSensorDescription(key="address", icon="mdi:map-marker"),
    IDMSensorDescription(key="info", icon="mdi:information-outline"),
    IDMSensorDescription(key="email", icon="mdi:email-outline"),
    IDMSensorDescription(key="aantal", icon="mdi:counter"),
    IDMSensorDescription(
        key="euro",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
    ),
    IDMSensorDescription(
        key="euro_totaal",
        icon="mdi:cash-multiple",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IDMSensorDescription(
        key="gewicht",
        icon="mdi:weight-kilogram",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
    ),
    IDMSensorDescription(
        key="gewicht_totaal",
        icon="mdi:scale",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    IDMSensorDescription(
        key="percentage",
        icon="mdi:percent-outline",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    IDMSensorDescription(
        key="timestamp",
        icon="mdi:calendar-clock",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
]

SUPPORTED_KEYS = {description.key: description for description in SENSOR_DESCRIPTIONS}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IDMConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the IDM sensors."""
    coordinator = entry.runtime_data
    entities: list[IDMSensor] = []

    for item in (coordinator.data or {}).values():
        description = SUPPORTED_KEYS.get(item.type)
        if description is None:
            _LOGGER.debug(
                "[sensor|async_setup_entry] no sensor type %r for %s",
                item.type,
                item.name,
            )
            continue

        entities.append(
            IDMSensor(
                coordinator=coordinator,
                description=IDMSensorDescription(
                    key=str(item.key),
                    name=item.name,
                    icon=description.icon,
                    device_class=description.device_class,
                    state_class=description.state_class,
                    native_unit_of_measurement=(
                        item.native_unit_of_measurement or description.native_unit_of_measurement
                    ),
                ),
                item=item,
            )
        )

    async_add_entities(entities)


class IDMSensor(IDMEntity, SensorEntity):
    """Representation of an IDM sensor."""

    entity_description: IDMSensorDescription

    def __init__(
        self,
        coordinator: IDMDataUpdateCoordinator,
        description: EntityDescription,
        item: IDMItem,
    ) -> None:
        """Initialize the sensor and pin its entity id."""
        super().__init__(coordinator, description, item)
        self.entity_id = f"sensor.{DOMAIN}_{item.key}"

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.item.state

    @property
    def extra_state_attributes(self) -> dict:
        """Return the extra attributes of the sensor."""
        attributes: dict = {"last_synced": self.last_synced}
        attributes.update(self.item.extra_attributes or {})
        return attributes
