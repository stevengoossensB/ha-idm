"""Tests for the Recycle! collection calendar."""

from __future__ import annotations

from datetime import date, timedelta

from idm.exceptions import IDMServiceException
from idm.recycle import Collection, RecycleClient, house_number_of, slugify_fraction

from . import fixtures
from .test_client import FakeClient, find

TODAY = date.today()

COLLECTIONS = [
    Collection(
        TODAY + timedelta(days=2),
        "Groente, fruit- en tuinafval",
        "groente_fruit_en_tuinafval",
        "#C7D33B",
    ),
    Collection(TODAY + timedelta(days=7), "Papier-karton", "papier_karton", "#FEC91B"),
    Collection(TODAY + timedelta(days=9), "PMD", "pmd", "#66C3FA"),
    Collection(TODAY + timedelta(days=9), "Restafval", "restafval", "#767676"),
    Collection(
        TODAY + timedelta(days=16),
        "Groente, fruit- en tuinafval",
        "groente_fruit_en_tuinafval",
        "#C7D33B",
    ),
]


class CalendarClient(FakeClient):
    """A fake IDM client whose Recycle! lookups are stubbed out."""

    def __init__(self, collections=None, error: Exception | None = None) -> None:
        """Set up the fake with a canned collection list or a failure."""
        super().__init__(collection_calendar=True)
        self._collections = COLLECTIONS if collections is None else collections
        self._error = error
        self.recycle = self  # type: ignore[assignment]

    def collections_for_address(self, address):
        """Stand in for RecycleClient.collections_for_address."""
        if self._error:
            raise self._error
        return self._collections


# -- helpers -----------------------------------------------------------


def test_slugify_fraction():
    """Fraction names become stable keys."""
    assert slugify_fraction("Papier-karton") == "papier_karton"
    assert slugify_fraction("Groente, fruit- en tuinafval") == "groente_fruit_en_tuinafval"
    assert slugify_fraction("PMD") == "pmd"


def test_house_number_of():
    """Recycle! wants a bare number; IDM may carry a suffix."""
    assert house_number_of("161") == "161"
    assert house_number_of("12A") == "12"
    assert house_number_of("bus 3, 44") == "3"
    assert house_number_of("") is None
    assert house_number_of(None) is None


# -- item building -----------------------------------------------------


def test_calendar_item_carries_every_collection():
    """The calendar entity is fed from the item payload, not the attributes."""
    data = CalendarClient().fetch_data()
    calendar = find(data, "ophaalkalender")
    assert calendar.type == "calendar"
    assert len(calendar.data["events"]) == len(COLLECTIONS)
    assert calendar.data["events"][0]["fractie"] == "Groente, fruit- en tuinafval"


def test_next_collection_sensor():
    """The overall next-collection sensor points at the earliest date."""
    data = CalendarClient().fetch_data()
    nxt = find(data, "volgende_ophaling")
    assert nxt.state.date() == COLLECTIONS[0].collected_on
    assert nxt.state.tzinfo is not None


def test_next_collection_per_fraction():
    """Each fraction gets its own next-collection sensor, at its first date."""
    data = CalendarClient().fetch_data()
    gft = find(data, "volgende_ophaling_groente_fruit_en_tuinafval")
    # The later GFT collection must not win.
    assert gft.state.date() == TODAY + timedelta(days=2)
    assert gft.extra_attributes["datums"] == [
        (TODAY + timedelta(days=2)).isoformat(),
        (TODAY + timedelta(days=16)).isoformat(),
    ]
    assert find(data, "volgende_ophaling_restafval").state.date() == TODAY + timedelta(days=9)


def test_same_day_fractions_are_listed_together():
    """PMD and Restafval share a day; both are named on the next-collection sensor."""
    data = CalendarClient(
        collections=[c for c in COLLECTIONS if c.collected_on == TODAY + timedelta(days=9)]
    ).fetch_data()
    assert find(data, "volgende_ophaling").extra_attributes["fracties"] == [
        "PMD",
        "Restafval",
    ]


# -- failure handling --------------------------------------------------


def test_calendar_failure_does_not_break_diftar_sensors():
    """Recycle! is a separate service; losing it must not lose the portal data."""
    data = CalendarClient(error=IDMServiceException("Recycle! is down")).fetch_data()
    assert find(data, "totaal_gewicht_ledigingen").state == 3865.0
    assert not [key for key in data if "ophaal" in key]


def test_calendar_can_be_switched_off():
    """With the calendar disabled nothing is fetched and no items are created."""
    data = FakeClient(collection_calendar=False).fetch_data()
    assert not [key for key in data if "ophaal" in key]


def test_empty_schedule_creates_no_entities():
    """An address Recycle! knows nothing about yields no calendar entities."""
    data = CalendarClient(collections=[]).fetch_data()
    assert not [key for key in data if "ophaal" in key]


def test_address_without_a_street_is_rejected():
    """A missing address field is a clear error rather than a bad lookup."""
    client = RecycleClient()
    for broken in (
        {**fixtures.ADDRESS, "street": None},
        {**fixtures.ADDRESS, "house_number": "bus"},
        {**fixtures.ADDRESS, "zipcode": None},
    ):
        try:
            client.collections_for_address(broken)
        except IDMServiceException as err:
            assert "missing" in str(err)
        else:  # pragma: no cover - the call must not succeed
            raise AssertionError("expected an IDMServiceException")
