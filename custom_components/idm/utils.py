"""Utility helpers for the IDM integration."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha1
import logging
import re
from typing import Any

from .const import API_DATETIME_FORMATS

_LOGGER = logging.getLogger(__name__)


def address_key(address: dict) -> str:
    """Return a stable identifier for a linked address.

    The portal hands out a fresh UUID for an address on every session, so it
    cannot be used for entity unique ids -- every restart would orphan the old
    entities and create a new set. The address itself does not move, so a short
    digest of its identifying fields is used instead. Hashing also keeps the
    street and house number out of entity ids while the device name still shows
    them in the UI.
    """
    identity = "|".join(
        str(address.get(field) or "").strip().lower()
        for field in ("zipcode", "street", "house_number", "category")
    )
    return sha1(identity.encode("utf-8"), usedforsecurity=False).hexdigest()[:12]


def format_entity_name(string: str) -> str:
    """Turn an arbitrary string into a safe entity key."""
    string = string.strip()
    string = re.sub(r"\s+", "_", string)
    return re.sub(r"\W+", "", string).lower()


def sensor_name(string: str) -> str:
    """Format a human readable sensor name."""
    return string.strip().replace("_", " ").title()


def to_float(value: Any, default: float | None = None) -> float | None:
    """Parse the portal's decimal strings ("14.00", "3,30") into a float.

    The IDM portal returns money and weights as strings with two decimals,
    unlike some sibling portals that return integer cents/grams. Everything
    here is already in EUR and kg, so no scaling is applied.
    """
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        _LOGGER.debug("Could not parse %r as a float", value)
        return default


def parse_datetime(value: str | None) -> datetime | None:
    """Parse a timestamp returned by the portal.

    Home Assistant requires timezone-aware datetimes for timestamp sensors, and
    the portal mixes full UTC timestamps with bare dates, so anything naive is
    anchored to UTC.
    """
    if not value:
        return None
    cleaned = value.replace("Z", "+0000")
    for fmt in API_DATETIME_FORMATS:
        try:
            parsed = datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed
    _LOGGER.debug("Could not parse %r as a datetime", value)
    return None


def mask_fields(json_data: Any, fields_to_mask: list[str]) -> Any:
    """Recursively replace sensitive values with a placeholder, in place."""
    if isinstance(json_data, dict):
        for field in fields_to_mask:
            if field in json_data:
                json_data[field] = "***FILTERED***"
        for value in json_data.values():
            mask_fields(value, fields_to_mask)
    elif isinstance(json_data, list):
        for item in json_data:
            mask_fields(item, fields_to_mask)
    return json_data


def redact(data: Any, fields_to_mask: list[str]) -> Any:
    """Return a copy of ``data`` with sensitive fields removed."""
    if isinstance(data, dict):
        return {
            key: ("***FILTERED***" if key in fields_to_mask else redact(value, fields_to_mask))
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [redact(item, fields_to_mask) for item in data]
    return data


def sizeof_fmt(num: float, suffix: str = "b") -> str:
    """Convert a byte count to a human readable string."""
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"
