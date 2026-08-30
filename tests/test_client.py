"""Tests for the IDM client's data assembly."""

from __future__ import annotations

from datetime import datetime
import json

from idm.client import IDMClient
from idm.utils import address_key, parse_datetime, to_float
import pytest

from . import fixtures


class FakeClient(IDMClient):
    """An IDM client with every HTTP call replaced by a captured payload."""

    def __init__(self, address: dict | None = None, collection_calendar: bool = False) -> None:
        """Set up the fake with a chosen address payload.

        The collection calendar is off by default so that the DIFTAR tests never
        reach out to the Recycle! API; the calendar has its own tests below.
        """
        super().__init__(
            email="resident@example.be",
            password="hunter2",
            collection_calendar=collection_calendar,
        )
        self.scope = fixtures.SCOPE
        self._address = address or fixtures.ADDRESS

    def login(self):
        """Pretend the login succeeded."""
        self.scope = fixtures.SCOPE
        return fixtures.USER

    def mijn_adressen(self):
        """Return the single linked address."""
        return [self._address]

    def overzicht(self, address_id):
        """Return the captured overview payload."""
        return fixtures.OVERZICHT

    def ledigingen(self, address_id, from_date=None):
        """Return the captured emptyings payload."""
        return fixtures.LEDIGINGEN

    def ondergrondse_stortingen(self, address_id, from_date=None):
        """Return the captured dumpings payload."""
        return fixtures.STORTINGEN

    def afval_op_afroep(self, address_id):
        """Return the captured on-demand payload."""
        return fixtures.AFVAL_OP_AFROEP

    def recyclageparken(self, address_id, year=None):
        """Return the captured recycling centre payload."""
        return fixtures.RECYCLAGEPARKEN


@pytest.fixture(name="data")
def data_fixture() -> dict:
    """Build the item set once for the whole module."""
    return FakeClient().fetch_data()


def find(data: dict, needle: str):
    """Return the single item whose key ends with ``needle``."""
    matches = [item for key, item in data.items() if key.endswith(needle)]
    assert len(matches) == 1, f"expected exactly one item for {needle!r}, got {len(matches)}"
    return matches[0]


# -- units and scaling -------------------------------------------------


def test_totals_are_not_rescaled(data):
    """The portal already reports EUR and kg, so totals must pass through."""
    assert find(data, "totaal_gewicht_ledigingen").state == 3865.0
    assert find(data, "totale_kost_ledigingen").state == 813.94


def test_decimal_strings_become_floats(data):
    """Weights and prices arrive as strings like "14.00"."""
    rest = find(data, "laatste_lediging_rest")
    assert rest.state == 14.0
    assert isinstance(rest.state, float)
    assert find(data, "laatste_lediging_kost_rest").state == 3.30


def test_to_float_handles_comma_decimals():
    """Some Laravel locales emit comma decimals; both must parse."""
    assert to_float("3,30") == 3.30
    assert to_float("3.30") == 3.30
    assert to_float(None, 0.0) == 0.0
    assert to_float("not a number", -1) == -1


# -- per-fraction selection --------------------------------------------


def test_latest_emptying_per_fraction(data):
    """Each fraction gets its most recent emptying, not the first in the list."""
    assert find(data, "laatste_lediging_rest").state == 14.0
    assert find(data, "laatste_lediging_gft").state == 7.67
    # The older REST emptying (12.00 kg) must not win.
    assert find(data, "laatste_lediging_rest").state != 12.0


def test_latest_emptying_is_selected_regardless_of_order():
    """Sorting must not depend on the portal returning newest-first."""
    shuffled = {
        **fixtures.LEDIGINGEN,
        "emptyings": list(reversed(fixtures.LEDIGINGEN["emptyings"])),
    }

    class Reordered(FakeClient):
        def ledigingen(self, address_id, from_date=None):
            return shuffled

    data = Reordered().fetch_data()
    assert find(data, "laatste_lediging_rest").state == 14.0


# -- timestamps --------------------------------------------------------


def test_timestamps_are_timezone_aware(data):
    """Home Assistant rejects naive datetimes on timestamp sensors."""
    for suffix in (
        "laatste_lediging_datum_rest",
        "laatste_recyclagepark_bezoek",
        "volgende_recyclagepark_reservatie",
    ):
        state = find(data, suffix).state
        assert isinstance(state, datetime), suffix
        assert state.tzinfo is not None, f"{suffix} is naive"


def test_bare_dates_parse():
    """Planned reservations carry a bare date rather than a full timestamp."""
    parsed = parse_datetime("2026-09-12")
    assert parsed is not None
    assert parsed.tzinfo is not None
    assert parse_datetime("") is None
    assert parse_datetime("nonsense") is None


def test_latest_visit_wins(data):
    """The most recent recycling centre visit is the one reported."""
    assert find(data, "laatste_recyclagepark_bezoek").state.date().isoformat() == "2026-08-29"


# -- yearly figures ----------------------------------------------------


def test_yearly_cost_uses_the_running_year(data):
    """The 2026 column, not the 2025 one, drives the yearly cost sensors."""
    assert find(data, "jaarkost_2026_rest").state == 60.40
    assert find(data, "jaarkost_2026_gft").state == 14.16
    assert find(data, "jaarkost_2026_totaal").state == pytest.approx(74.56)


def test_residual_waste_comparison(data):
    """Own consumption is compared against the average for the same household size."""
    assert find(data, "restafval_2026").state == 284.5
    assert find(data, "restafval_gemiddelde_2026").state == 569.0
    assert find(data, "restafval_versus_gemiddelde_2026").state == pytest.approx(50.0)
    assert find(data, "aantal_gezinsleden").state == 5


def test_recycling_centre_totals(data):
    """Recycling centre weight and cost are summed over the fractions."""
    assert find(data, "recyclagepark_gewicht_2026").state == 325.0
    assert find(data, "recyclagepark_kost_2026").state == 12.0
    assert find(data, "geplande_recyclagepark_reservaties").state == 1


# -- stability ---------------------------------------------------------


def test_entity_keys_survive_a_rotated_address_uuid():
    """The portal issues a new address UUID per session; keys must not move."""
    first = FakeClient(fixtures.ADDRESS).fetch_data()
    second = FakeClient(fixtures.ADDRESS_ROTATED_UUID).fetch_data()

    assert fixtures.ADDRESS["id"] != fixtures.ADDRESS_ROTATED_UUID["id"]
    assert set(first) == set(second)
    assert {item.device_key for item in first.values()} == {
        item.device_key for item in second.values()
    }


def test_address_key_ignores_the_uuid():
    """Only the address itself feeds the stable key."""
    assert address_key(fixtures.ADDRESS) == address_key(fixtures.ADDRESS_ROTATED_UUID)
    other = {**fixtures.ADDRESS, "house_number": "162"}
    assert address_key(fixtures.ADDRESS) != address_key(other)


# -- privacy -----------------------------------------------------------


def test_national_registration_number_never_leaks(data):
    """The rijksregisternummer must not reach any state or attribute."""
    secret = fixtures.ADDRESS["national_registration_number"]
    blob = json.dumps(
        [{"state": str(item.state), "attributes": item.extra_attributes} for item in data.values()],
        default=str,
    )
    assert secret not in blob
    assert "***FILTERED***" in blob

    address_item = find(data, "adres")
    assert address_item.extra_attributes["national_registration_number"] == "***FILTERED***"


# -- scopes ------------------------------------------------------------


def test_sensors_follow_account_permissions():
    """Nothing is created for a service the account cannot see."""

    class Limited(FakeClient):
        def login(self):
            self.scope = {"view_address": True, "view_emptyings": True}
            return fixtures.USER

    data = Limited().fetch_data()
    keys = " ".join(data)
    assert "laatste_lediging_rest" in keys
    assert "recyclagepark" not in keys
    assert "restafval" not in keys


def test_no_data_without_a_login():
    """A client without credentials yields nothing rather than raising."""
    assert IDMClient().fetch_data() == {}
