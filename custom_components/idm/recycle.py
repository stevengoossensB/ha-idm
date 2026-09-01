"""Client for the Recycle! (Fost Plus) collection calendar.

IDM does not serve the collection calendar from its own portal -- ``idm.be``
embeds Recycle!. Its public API is unauthenticated, and the address the IDM
portal already gives us (zip code, street, house number) is enough to resolve a
collection schedule, so the calendar needs no extra configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
import re
from typing import Any
import urllib.parse

from requests import Session

from .const import (
    RECYCLE_APP_SETTINGS_URL,
    RECYCLE_CONSUMER,
    RECYCLE_FORECAST_WEEKS,
    RECYCLE_LANGUAGE,
    REQUEST_TIMEOUT,
)
from .exceptions import IDMServiceException

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Collection:
    """A single scheduled kerbside collection."""

    collected_on: date
    fraction: str
    key: str
    color: str | None = None


def slugify_fraction(name: str) -> str:
    """Turn a fraction name into a stable key ("Papier-karton" -> "papier_karton")."""
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower())
    return slug.strip("_")


def house_number_of(value: Any) -> str | None:
    """Extract the numeric part of a house number ("161", "12A" -> "12")."""
    match = re.search(r"\d+", str(value or ""))
    return match.group(0) if match else None


class RecycleClient:
    """Minimal client for the public Recycle! collection API."""

    def __init__(self, session: Session | None = None) -> None:
        """Initialize the client."""
        self.session = session or Session()
        self.session.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "User-Agent": "HomeAssistant-IDM",
                "x-consumer": RECYCLE_CONSUMER,
            }
        )
        self._endpoint: str | None = None

    # -- plumbing ------------------------------------------------------

    @property
    def endpoint(self) -> str:
        """Return the API endpoint, discovering it on first use."""
        if self._endpoint is None:
            response = self.session.get(RECYCLE_APP_SETTINGS_URL, timeout=REQUEST_TIMEOUT)
            if response.status_code != 200:
                raise IDMServiceException(
                    f"Could not read the Recycle! app settings (HTTP {response.status_code})"
                )
            base = response.json().get("API")
            if not base:
                raise IDMServiceException("The Recycle! app settings carried no API base URL")
            self._endpoint = f"{base}/public/v1"
            _LOGGER.debug("[RecycleClient] endpoint %s", self._endpoint)
        return self._endpoint

    def _get(self, path: str) -> dict:
        response = self.session.get(f"{self.endpoint}/{path}", timeout=REQUEST_TIMEOUT)
        if response.status_code != 200:
            raise IDMServiceException(f"Recycle! GET {path} returned HTTP {response.status_code}")
        return response.json()

    def _post(self, path: str) -> dict:
        response = self.session.post(f"{self.endpoint}/{path}", timeout=REQUEST_TIMEOUT)
        if response.status_code != 200:
            raise IDMServiceException(f"Recycle! POST {path} returned HTTP {response.status_code}")
        return response.json()

    # -- lookups -------------------------------------------------------

    def resolve_zipcode(self, zipcode: Any) -> str:
        """Return the Recycle! id for a Belgian postal code."""
        result = self._get(f"zipcodes?q={urllib.parse.quote(str(zipcode))}")
        items = result.get("items") or []
        if not items:
            raise IDMServiceException(f"Recycle! does not know postal code {zipcode}")
        return items[0]["id"]

    def resolve_street(self, street: str, zipcode_id: str) -> str:
        """Return the Recycle! id for a street within a postal code."""
        query = urllib.parse.urlencode({"q": street.strip().lower(), "zipcodes": zipcode_id})
        result = self._post(f"streets?{query}")
        items = result.get("items") or []
        if not items:
            raise IDMServiceException(f"Recycle! does not know street {street!r}")
        if len(items) > 1:
            wanted = street.strip().lower()
            exact = next(
                (
                    item
                    for item in items
                    if (item.get("names") or {}).get(RECYCLE_LANGUAGE, "").strip().lower() == wanted
                ),
                None,
            )
            if exact:
                return exact["id"]
            _LOGGER.debug(
                "Recycle! returned %s matches for %r; using the first", len(items), street
            )
        return items[0]["id"]

    # -- collections ---------------------------------------------------

    def collections(
        self,
        zipcode_id: str,
        street_id: str,
        house_number: str,
        from_date: date | None = None,
        until_date: date | None = None,
    ) -> list[Collection]:
        """Return the upcoming collections for an address, oldest first."""
        from_date = from_date or datetime.now().date()
        until_date = until_date or from_date + timedelta(weeks=RECYCLE_FORECAST_WEEKS)

        query = urllib.parse.urlencode(
            {
                "zipcodeId": zipcode_id,
                "streetId": street_id,
                "houseNumber": house_number,
                "fromDate": from_date.isoformat(),
                "untilDate": until_date.isoformat(),
                "size": 100,
            }
        )
        result = self._get(f"collections?{query}")

        collections: list[Collection] = []
        seen: set[tuple[date, str]] = set()
        for item in result.get("items") or []:
            # A collection that has been moved is superseded by its replacement.
            if (item.get("exception") or {}).get("replacedBy"):
                continue

            stamp = (item.get("timestamp") or "").split("T")[0]
            try:
                collected_on = date.fromisoformat(stamp)
            except ValueError:
                _LOGGER.debug("Skipping collection with unparseable date %r", stamp)
                continue

            fraction = item.get("fraction") or {}
            name = (fraction.get("name") or {}).get(RECYCLE_LANGUAGE)
            if not name:
                continue

            key = slugify_fraction(name)
            if (collected_on, key) in seen:
                continue
            seen.add((collected_on, key))

            collections.append(
                Collection(
                    collected_on=collected_on,
                    fraction=name,
                    key=key,
                    color=fraction.get("color"),
                )
            )

        collections.sort(key=lambda c: (c.collected_on, c.fraction))
        return collections

    def collections_for_address(self, address: dict) -> list[Collection]:
        """Resolve an IDM address and return its upcoming collections."""
        street = address.get("street")
        number = house_number_of(address.get("house_number"))
        zipcode = address.get("zipcode")
        if not (street and number and zipcode):
            raise IDMServiceException(
                "The IDM address is missing a street, house number or postal code"
            )

        zipcode_id = self.resolve_zipcode(zipcode)
        street_id = self.resolve_street(street, zipcode_id)
        return self.collections(zipcode_id, street_id, number)
