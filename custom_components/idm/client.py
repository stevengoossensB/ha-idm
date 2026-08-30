"""IDM (mijnidm.be) API client.

The IDM portal is a Laravel application that renders its pages with Inertia.js.
Every response embeds the full page state as JSON in the ``data-page`` attribute
of ``<div id="app">``, so there is no separate REST API to talk to: we log in
with the user's portal credentials, request the same URLs the browser does and
read the props straight out of the markup.

All monetary values are returned by the portal as decimal strings in EUR and all
weights as decimal strings in kg, so no scaling is applied anywhere below.
"""

from __future__ import annotations

import copy
from datetime import datetime
import json
import logging
from typing import Any
import urllib.parse

from bs4 import BeautifulSoup
from requests import Session

from .const import (
    BASE_HEADERS,
    CONNECTION_RETRY,
    DEFAULT_IDM_ENVIRONMENT,
    HISTORY_FROM_DATE,
    REQUEST_TIMEOUT,
    SENSITIVE_FIELDS,
)
from .exceptions import BadCredentialsException, IDMServiceException
from .models import IDMEnvironment, IDMItem
from .recycle import RecycleClient
from .utils import (
    address_key,
    format_entity_name,
    mask_fields,
    parse_datetime,
    redact,
    to_float,
)

_LOGGER = logging.getLogger(__name__)

# Props that Inertia shares with every page; not interesting per endpoint.
_SHARED_PROPS = ("errors", "auth", "linkedAddress", "linkedAddresses", "flash", "config")


class IDMClient:
    """Client for the Mijn IDM portal."""

    session: Session
    environment: IDMEnvironment

    def __init__(
        self,
        session: Session | None = None,
        email: str | None = None,
        password: str | None = None,
        headers: dict | None = None,
        environment: IDMEnvironment = DEFAULT_IDM_ENVIRONMENT,
        collection_calendar: bool = True,
    ) -> None:
        """Initialize the IDM client."""
        self.session = session or Session()
        self.email = email
        self.password = password
        self.environment = environment
        self.session.headers.update(headers or BASE_HEADERS)
        self.scope: dict[str, bool] = {}
        self.request_error: dict = {}
        # The collection calendar comes from Recycle!, not from the IDM portal.
        self.collection_calendar = collection_calendar
        self.recycle = RecycleClient()

    # ------------------------------------------------------------------
    # Plumbing
    # ------------------------------------------------------------------

    def request(
        self,
        url: str,
        caller: str = "Not set",
        data: dict | None = None,
        expected: int | None = 200,
        parse: bool = False,
        log: bool = False,
        connection_retry_left: int = CONNECTION_RETRY,
    ) -> Any:
        """Send a request to the IDM portal and optionally return page props."""
        if data is None:
            _LOGGER.debug("%s Calling GET %s", caller, url)
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
        else:
            data_copy = mask_fields(copy.deepcopy(data), SENSITIVE_FIELDS)
            _LOGGER.debug("%s Calling POST %s with %s", caller, url, data_copy)
            response = self.session.post(url, data=data, timeout=REQUEST_TIMEOUT)

        # Laravel rotates the CSRF token on every response; keep it in sync so a
        # subsequent POST is accepted.
        if (xsrf := self.session.cookies.get("XSRF-TOKEN")) is not None:
            self.session.headers["x-xsrf-token"] = urllib.parse.unquote(
                xsrf, encoding="utf-8", errors="replace"
            )

        _LOGGER.debug(
            "%s http status code = %s (expecting %s)",
            caller,
            response.status_code,
            expected,
        )
        if log:
            _LOGGER.debug("%s response:\n%s", caller, response.text)

        if expected is not None and response.status_code != expected:
            if response.status_code == 404:
                try:
                    self.request_error = response.json()
                except ValueError:
                    self.request_error = {"error": response.text}
                return False
            if response.status_code in (401, 419):
                raise BadCredentialsException(response.text)
            if response.status_code in (502, 503, 504) and connection_retry_left > 0:
                _LOGGER.debug(
                    "%s transient HTTP %s, %s retries left",
                    caller,
                    response.status_code,
                    connection_retry_left,
                )
                return self.request(
                    url,
                    caller,
                    data,
                    expected,
                    parse,
                    log,
                    connection_retry_left - 1,
                )
            raise IDMServiceException(
                f"[{caller}] Expecting HTTP {expected} | response HTTP "
                f"{response.status_code}, url: {response.url}"
            )

        if parse:
            return self._parse_page(response.text)
        return response

    @staticmethod
    def _parse_page(html: str) -> dict:
        """Extract the Inertia page props from an HTML response."""
        soup = BeautifulSoup(html, "html.parser")
        tag = soup.find("div", {"id": "app"})
        if tag is None:
            raise IDMServiceException("Could not find the Inertia app container on the IDM page")
        data_page = tag.get("data-page")
        if not data_page:
            raise IDMServiceException("The IDM page did not carry any page data")
        try:
            page = json.loads(data_page)
        except json.JSONDecodeError as err:
            raise IDMServiceException(f"Could not decode the IDM page data: {err}") from err
        props = page.get("props", {})
        _LOGGER.debug(
            "Page props (%s): %s",
            page.get("component"),
            redact(
                {k: v for k, v in props.items() if k not in _SHARED_PROPS},
                SENSITIVE_FIELDS,
            ),
        )
        return props

    def _endpoint(self, path: str) -> str:
        return f"{self.environment.api_endpoint}{path}"

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------

    def login(self) -> dict | bool:
        """Start a new session with an email address and password."""
        _LOGGER.debug("[IDMClient|login|start]")
        if self.email is None or self.password is None:
            return False

        self.session = Session()
        self.session.headers.update(BASE_HEADERS)

        # First GET the login page so Laravel hands us a session and CSRF token.
        self.request(
            self._endpoint("/login"),
            "[IDMClient|login|get csrf]",
            None,
            200,
        )
        props = self.request(
            self._endpoint("/login"),
            "[IDMClient|login|authenticate]",
            {"email": self.email, "password": self.password},
            200,
            parse=True,
        )

        auth = props.get("auth") or {}
        if not auth.get("loggedIn"):
            error = (props.get("flash") or {}).get("error")
            errors = props.get("errors") or {}
            message = error or "; ".join(str(v) for v in errors.values()) or "Login failed"
            raise BadCredentialsException(message)

        self.scope = auth.get("can") or {}
        _LOGGER.debug("[IDMClient|login] scope: %s", self.scope)
        return auth.get("user")

    def mijn_adressen(self) -> list[dict]:
        """Return the addresses linked to the account."""
        props = self.request(
            self._endpoint("/mijn-adressen"),
            "[IDMClient|mijn_adressen]",
            None,
            200,
            parse=True,
        )
        return props.get("addresses") or props.get("linkedAddresses") or []

    def overzicht(self, address_id: str) -> dict:
        """Return the consumption overview for an address."""
        return self.request(
            self._endpoint(f"/mijn-adressen/{address_id}/mijn-verbruik"),
            f"[IDMClient|{address_id}|overzicht]",
            None,
            200,
            parse=True,
        )

    def ledigingen(self, address_id: str, from_date: str = HISTORY_FROM_DATE) -> dict:
        """Return the kerbside emptyings (DIFTAR weighings) for an address."""
        query = urllib.parse.urlencode({"fromDate": from_date})
        props = self.request(
            self._endpoint(f"/mijn-adressen/{address_id}/mijn-verbruik/ledigingen?{query}"),
            f"[IDMClient|{address_id}|ledigingen]",
            None,
            200,
            parse=True,
        )
        if not props or "emptyings" not in props:
            return {}
        return props

    def ondergrondse_stortingen(self, address_id: str, from_date: str = HISTORY_FROM_DATE) -> dict:
        """Return the underground container dumpings for an address."""
        query = urllib.parse.urlencode({"fromDate": from_date})
        props = self.request(
            self._endpoint(
                f"/mijn-adressen/{address_id}/mijn-verbruik/ondergrondse-stortingen?{query}"
            ),
            f"[IDMClient|{address_id}|ondergrondse_stortingen]",
            None,
            200,
            parse=True,
        )
        if not props or "dumpings" not in props:
            return {}
        return props

    def afval_op_afroep(self, address_id: str) -> dict:
        """Return the on-demand waste collections for an address."""
        props = self.request(
            self._endpoint(f"/mijn-adressen/{address_id}/mijn-verbruik/afval-op-afroep"),
            f"[IDMClient|{address_id}|afval_op_afroep]",
            None,
            200,
            parse=True,
        )
        if not props or "wasteOnDemands" not in props:
            return {}
        return props

    def recyclageparken(self, address_id: str, year: int | None = None) -> dict:
        """Return recycling centre visits and reservations for an address."""
        year = year or datetime.now().year
        query = urllib.parse.urlencode({"year": year})
        props = self.request(
            self._endpoint(f"/mijn-adressen/{address_id}/mijn-verbruik/recyclageparken?{query}"),
            f"[IDMClient|{address_id}|recyclageparken]",
            None,
            200,
            parse=True,
        )
        return props or {}

    # ------------------------------------------------------------------
    # Data assembly
    # ------------------------------------------------------------------

    def fetch_data(self) -> dict[str, IDMItem]:
        """Log in and build the full set of items exposed as entities."""
        data: dict[str, IDMItem] = {}

        user_info = self.login()
        if not user_info or "email" not in user_info:
            return {}

        self._add_account_items(data, user_info)

        for address in self.mijn_adressen():
            self._add_address_items(data, address)

        _LOGGER.debug("[IDMClient|fetch_data] built %s items", len(data))
        return data

    # -- account -------------------------------------------------------

    def _add_account_items(self, data: dict[str, IDMItem], user_info: dict) -> None:
        email = user_info.get("email")
        device_key = format_entity_name(f"user {email}")
        device_name = f"Account {email}"
        safe_user = redact(user_info, SENSITIVE_FIELDS)

        def add(name: str, suffix: str, item_type: str, state: Any) -> None:
            key = format_entity_name(f"{email} {suffix}")
            data[key] = IDMItem(
                name=name,
                key=key,
                type=item_type,
                device_key=device_key,
                device_name=device_name,
                device_model="Gebruiker",
                state=state,
                extra_attributes=safe_user,
            )

        add("E-mail", "email", "email", email)
        add("Voornaam", "first_name", "info", user_info.get("first_name"))
        add("Achternaam", "last_name", "info", user_info.get("last_name"))

    # -- address -------------------------------------------------------

    def _add_address_items(self, data: dict[str, IDMItem], address: dict) -> None:
        address_id = address.get("id")
        if not address_id:
            return

        street = address.get("street", "")
        house_number = address.get("house_number", "")
        # NOT address_id: the portal issues a fresh UUID per session, so keying
        # entities on it would orphan every entity on each restart.
        stable_key = address_key(address)
        device_key = format_entity_name(f"address {stable_key}")
        device_name = f"Adres {street} {house_number}".strip()
        device_model = "Adres"
        safe_address = redact(address, SENSITIVE_FIELDS)

        _LOGGER.debug(
            "Address %s %s, %s %s",
            street,
            house_number,
            address.get("zipcode"),
            address.get("city"),
        )

        def add(
            name: str,
            suffix: str,
            item_type: str,
            state: Any,
            attributes: dict | None = None,
            payload: dict | None = None,
        ) -> None:
            key = format_entity_name(f"{stable_key} {suffix}")
            data[key] = IDMItem(
                name=name,
                key=key,
                type=item_type,
                device_key=device_key,
                device_name=device_name,
                device_model=device_model,
                state=state,
                extra_attributes=attributes or {},
                data=payload or {},
            )

        add(
            f"{street} {house_number}, {address.get('zipcode')} {address.get('city')}",
            "adres",
            "address",
            address.get("category"),
            safe_address,
        )

        overzicht = self.overzicht(address_id) or {}

        if self.scope.get("view_emptyings"):
            self._add_emptying_items(add, address_id, overzicht)

        if self.scope.get("view_dumpings"):
            self._add_dumping_items(add, address_id)

        if self.scope.get("view_waste_on_demands"):
            self._add_waste_on_demand_items(add, address_id)

        if self.scope.get("view_recycling_center_visits"):
            self._add_recycling_center_items(add, address_id, overzicht)

        if self.scope.get("view_residual_waste_consumption_comparison"):
            self._add_residual_comparison_items(add, overzicht)

        self._add_collection_items(add, address)

    # -- collection calendar --------------------------------------------

    def _add_collection_items(self, add, address: dict) -> None:
        """Add the kerbside collection schedule, sourced from Recycle!.

        The calendar lives outside the IDM portal, so a failure here is not a
        failure of the integration: the DIFTAR sensors stay up and only the
        calendar goes missing.
        """
        if not self.collection_calendar:
            return

        try:
            collections = self.recycle.collections_for_address(address)
        except IDMServiceException as err:
            _LOGGER.warning(
                "Could not load the Recycle! collection calendar for this address "
                "(%s); the DIFTAR sensors are unaffected",
                err,
            )
            return
        except Exception:
            _LOGGER.exception("Unexpected error while loading the Recycle! calendar")
            return

        if not collections:
            _LOGGER.debug("Recycle! returned no upcoming collections for this address")
            return

        events = [
            {
                "datum": collection.collected_on.isoformat(),
                "fractie": collection.fraction,
                "key": collection.key,
                "kleur": collection.color,
            }
            for collection in collections
        ]

        first = collections[0]
        add(
            "Ophaalkalender",
            "ophaalkalender",
            "calendar",
            first.fraction,
            {
                "volgende_ophaling": first.collected_on.isoformat(),
                "aantal_geplande_ophalingen": len(collections),
                "ophalingen": events,
            },
            {"events": events},
        )
        add(
            "Volgende ophaling",
            "volgende ophaling",
            "timestamp",
            parse_datetime(first.collected_on.isoformat()),
            {
                "fractie": first.fraction,
                "fracties": sorted(
                    {c.fraction for c in collections if c.collected_on == first.collected_on}
                ),
                "ophalingen": events,
            },
        )

        for key in dict.fromkeys(c.key for c in collections):
            nxt = next(c for c in collections if c.key == key)
            add(
                f"Volgende ophaling {nxt.fraction}",
                f"volgende ophaling {key}",
                "timestamp",
                parse_datetime(nxt.collected_on.isoformat()),
                {
                    "fractie": nxt.fraction,
                    "kleur": nxt.color,
                    "datums": [c.collected_on.isoformat() for c in collections if c.key == key],
                },
            )
            _LOGGER.debug("  - volgende %s: %s", nxt.fraction, nxt.collected_on)

    # -- emptyings -----------------------------------------------------

    def _add_emptying_items(self, add, address_id: str, overzicht: dict) -> None:
        ledigingen = self.ledigingen(address_id)
        if not ledigingen:
            return

        emptyings = ledigingen.get("emptyings") or []
        total_weight = to_float(ledigingen.get("totalWeight"), 0.0)
        total_price = to_float(ledigingen.get("totalPrice"), 0.0)
        fractions = ledigingen.get("availableFractions") or []

        _LOGGER.debug(
            "Ledigingen van %s tot %s: %s kg / %s EUR over %s ledigingen",
            ledigingen.get("fromDate"),
            ledigingen.get("untilDate"),
            total_weight,
            total_price,
            len(emptyings),
        )

        add(
            "Totaal gewicht ledigingen",
            "totaal gewicht ledigingen",
            "gewicht_totaal",
            round(total_weight, 2),
            {
                "aantal_ledigingen": len(emptyings),
                "van": ledigingen.get("fromDate"),
                "tot": ledigingen.get("untilDate"),
                "fracties": fractions,
                "ledigingen": emptyings,
            },
        )
        add(
            "Totale kost ledigingen",
            "totale kost ledigingen",
            "euro_totaal",
            round(total_price, 2),
            {
                "aantal_ledigingen": len(emptyings),
                "van": ledigingen.get("fromDate"),
                "tot": ledigingen.get("untilDate"),
            },
        )

        # Per-fraction: most recent emptying. The portal returns newest first,
        # but sort defensively so we never depend on that.
        sorted_emptyings = sorted(
            emptyings,
            key=lambda e: e.get("emptied_on") or "",
            reverse=True,
        )
        seen: set[str] = set()
        for emptying in sorted_emptyings:
            fraction = emptying.get("fraction")
            if not fraction or fraction in seen:
                continue
            seen.add(fraction)

            emptied_on = parse_datetime(emptying.get("emptied_on"))
            weight = to_float(emptying.get("weight"), 0.0)
            price = to_float(emptying.get("price"), 0.0)
            attributes = {
                "fractie": fraction,
                "datum": emptying.get("emptied_on"),
                "gewicht": weight,
                "prijs": price,
                "volume": emptying.get("volume"),
                "barcode": emptying.get("barcode"),
                "servicekost": to_float(emptying.get("service_cost")),
                "eenheidsprijs": to_float(emptying.get("unit_cost")),
            }

            add(
                f"{fraction} laatste lediging",
                f"laatste lediging {fraction}",
                "gewicht",
                weight,
                attributes,
            )
            add(
                f"{fraction} laatste lediging datum",
                f"laatste lediging datum {fraction}",
                "timestamp",
                emptied_on,
                attributes,
            )
            add(
                f"{fraction} laatste lediging kost",
                f"laatste lediging kost {fraction}",
                "euro",
                price,
                attributes,
            )
            _LOGGER.debug(
                "  - %s %s %sL: %s kg / %s EUR",
                emptying.get("emptied_on"),
                fraction,
                emptying.get("volume"),
                weight,
                price,
            )

        # Cost per fraction for the running year.
        if self.scope.get("view_yearly_cost"):
            self._add_yearly_cost_items(add, overzicht)

    def _add_yearly_cost_items(self, add, overzicht: dict) -> None:
        summary = overzicht.get("yearlyCostSummary") or {}
        years = summary.get("years") or []
        series = summary.get("series") or []
        if not years or not series:
            return

        current_year = datetime.now().year
        index = years.index(current_year) if current_year in years else len(years) - 1
        year = years[index]

        year_total = 0.0
        for serie in series:
            fraction = serie.get("name")
            values = serie.get("data") or []
            if index >= len(values):
                continue
            amount = to_float(values[index], 0.0)
            year_total += amount
            add(
                f"{fraction} kost {year}",
                f"jaarkost {year} {fraction}",
                "euro",
                round(amount, 2),
                {"jaar": year, "fractie": fraction},
            )

        add(
            f"Totale kost {year}",
            f"jaarkost {year} totaal",
            "euro",
            round(year_total, 2),
            {
                "jaar": year,
                "jaarverbruik": {
                    serie.get("name"): dict(zip(years, serie.get("data") or [], strict=False))
                    for serie in series
                },
            },
        )

    # -- dumpings ------------------------------------------------------

    def _add_dumping_items(self, add, address_id: str) -> None:
        stortingen = self.ondergrondse_stortingen(address_id)
        if not stortingen:
            return
        dumpings = stortingen.get("dumpings") or []
        add(
            "Totale kost ondergrondse stortingen",
            "totale kost stortingen",
            "euro_totaal",
            round(to_float(stortingen.get("totalPrice"), 0.0), 2),
            {
                "aantal_stortingen": len(dumpings),
                "van": stortingen.get("fromDate"),
                "tot": stortingen.get("untilDate"),
                "stortingen": dumpings,
            },
        )

    # -- waste on demand -----------------------------------------------

    def _add_waste_on_demand_items(self, add, address_id: str) -> None:
        afroep = self.afval_op_afroep(address_id)
        if not afroep:
            return
        collections = afroep.get("wasteOnDemands") or []
        add(
            "Totale kost afval op afroep",
            "totale kost afval op afroep",
            "euro_totaal",
            round(to_float(afroep.get("totalPrice"), 0.0), 2),
            {
                "aantal_ophalingen": len(collections),
                "van": afroep.get("fromDate"),
                "tot": afroep.get("untilDate"),
                "afval_op_afroep": collections,
            },
        )

    # -- recycling centres ---------------------------------------------

    def _add_recycling_center_items(self, add, address_id: str, overzicht: dict) -> None:
        parken = self.recyclageparken(address_id)
        year = parken.get("year") or datetime.now().year

        distribution = ((parken.get("wasteDistribution") or {}).get("data")) or []
        if distribution:
            total_weight = sum(to_float(row.get("weight"), 0.0) for row in distribution)
            total_price = sum(to_float(row.get("price"), 0.0) for row in distribution)
            add(
                f"Recyclagepark gewicht {year}",
                f"recyclagepark gewicht {year}",
                "gewicht",
                round(total_weight, 2),
                {
                    "jaar": year,
                    "fracties": [
                        {
                            "fractie": row.get("fraction"),
                            "gewicht": to_float(row.get("weight")),
                            "prijs": to_float(row.get("price")),
                            "gratis": row.get("free"),
                            "eenheid": row.get("unit"),
                        }
                        for row in distribution
                    ],
                },
            )
            add(
                f"Recyclagepark kost {year}",
                f"recyclagepark kost {year}",
                "euro",
                round(total_price, 2),
                {"jaar": year},
            )

        # Most recent visit, from the overview page.
        visits = overzicht.get("recyclingCenterVisits") or []
        if visits:
            latest = max(visits, key=lambda v: v.get("date") or "")
            add(
                "Laatste recyclageparkbezoek",
                "laatste recyclagepark bezoek",
                "timestamp",
                parse_datetime(latest.get("date")),
                {
                    "locatie": latest.get("locationName"),
                    "gewicht": to_float(latest.get("weight")),
                    "prijs": to_float(latest.get("price")),
                    "details": latest.get("details"),
                    "recyclagepark_bezoeken": visits,
                },
            )

        # Next planned reservation, if any.
        planned = parken.get("plannedReservations") or []
        upcoming = sorted(planned, key=lambda r: (r.get("date") or "", r.get("opens_at") or ""))
        if upcoming:
            nxt = upcoming[0]
            centre = nxt.get("recycling_center") or {}
            add(
                "Volgende recyclagepark reservatie",
                "volgende recyclagepark reservatie",
                "timestamp",
                parse_datetime(nxt.get("date")),
                {
                    "locatie": centre.get("name"),
                    "adres": centre.get("address"),
                    "van": nxt.get("opens_at"),
                    "tot": nxt.get("closes_at"),
                    "annuleerbaar": nxt.get("can_be_cancelled"),
                    "reservaties": upcoming,
                },
            )
        add(
            "Geplande recyclagepark reservaties",
            "geplande recyclagepark reservaties",
            "aantal",
            len(planned),
            {"reservaties": planned},
        )

    # -- residual waste comparison --------------------------------------

    def _add_residual_comparison_items(self, add, overzicht: dict) -> None:
        consumptions = overzicht.get("residualWasteConsumptions") or []
        averages = overzicht.get("averageResidualWasteConsumptions") or []
        occupants = overzicht.get("occupantCount")

        if occupants is not None:
            add(
                "Aantal gezinsleden",
                "aantal gezinsleden",
                "aantal",
                occupants,
                {},
            )

        if not consumptions:
            return

        latest = max(consumptions, key=lambda c: c.get("year") or 0)
        year = latest.get("year")
        own = to_float(latest.get("total_weight"), 0.0)
        add(
            f"Restafval {year}",
            f"restafval {year}",
            "gewicht",
            round(own, 2),
            {
                "jaar": year,
                "jaarverbruik": {c.get("year"): c.get("total_weight") for c in consumptions},
            },
        )

        peer = next(
            (a for a in averages if a.get("year") == year and a.get("occupant_count") == occupants),
            None,
        )
        if peer is None:
            return

        average = to_float(peer.get("average_weight"), 0.0)
        add(
            f"Restafval gemiddelde gezin {year}",
            f"restafval gemiddelde {year}",
            "gewicht",
            round(average, 2),
            {
                "jaar": year,
                "gezinsgrootte": occupants,
                "gemiddelde_per_gezinsgrootte": [a for a in averages if a.get("year") == year],
            },
        )
        if average:
            add(
                f"Restafval t.o.v. gemiddelde {year}",
                f"restafval versus gemiddelde {year}",
                "percentage",
                round(own / average * 100, 1),
                {
                    "jaar": year,
                    "eigen_gewicht": round(own, 2),
                    "gemiddeld_gewicht": round(average, 2),
                    "verschil": round(own - average, 2),
                    "gezinsgrootte": occupants,
                },
            )
