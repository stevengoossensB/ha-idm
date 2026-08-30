"""Models used by the IDM integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict


class IDMConfigEntryData(TypedDict):
    """Config entry data for the IDM integration."""

    username: str | None
    password: str | None


@dataclass
class IDMEnvironment:
    """Describes an IDM environment (portal base URL)."""

    api_endpoint: str


@dataclass
class IDMItem:
    """A single piece of data that becomes one Home Assistant entity."""

    name: str = ""
    key: str = ""
    type: str = ""
    state: str | float | None = ""
    device_key: str = ""
    device_name: str = ""
    device_model: str = ""
    data: dict = field(default_factory=dict)
    extra_attributes: dict = field(default_factory=dict)
    native_unit_of_measurement: str | None = None
