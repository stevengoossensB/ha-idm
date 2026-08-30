"""Calendar platform for the IDM integration.

The kerbside collection schedule is not part of the Mijn IDM portal; it comes
from Recycle! (Fost Plus), resolved from the address the portal reports. Each
linked address gets one all-day calendar with an event per collection.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
import logging

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IDMConfigEntry, IDMDataUpdateCoordinator
from .const import DOMAIN
from .entity import IDMEntity
from .models import IDMItem

_LOGGER = logging.getLogger(__name__)

CALENDAR_DESCRIPTION = EntityDescription(key="calendar", icon="mdi:calendar-refresh")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IDMConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the IDM collection calendars."""
    coordinator = entry.runtime_data
    async_add_entities(
        IDMCalendar(coordinator, CALENDAR_DESCRIPTION, item)
        for item in (coordinator.data or {}).values()
        if item.type == "calendar"
    )


class IDMCalendar(IDMEntity, CalendarEntity):
    """A waste collection calendar for one address."""

    def __init__(
        self,
        coordinator: IDMDataUpdateCoordinator,
        description: EntityDescription,
        item: IDMItem,
    ) -> None:
        """Initialize the calendar and pin its entity id."""
        super().__init__(coordinator, description, item)
        self.entity_id = f"calendar.{DOMAIN}_{item.key}"

    def _events(self) -> list[CalendarEvent]:
        """Build calendar events from the coordinator payload."""
        events: list[CalendarEvent] = []
        for entry in self.item.data.get("events", []):
            try:
                day = date.fromisoformat(entry["datum"])
            except (KeyError, TypeError, ValueError):
                _LOGGER.debug("Skipping malformed collection entry %r", entry)
                continue
            events.append(
                CalendarEvent(
                    # All-day events end on the following day.
                    start=day,
                    end=day + timedelta(days=1),
                    summary=entry.get("fractie", "Ophaling"),
                    description=f"Ophaling {entry.get('fractie', '')}".strip(),
                    uid=f"{self.item.key}-{entry['datum']}-{entry.get('key', '')}",
                )
            )
        events.sort(key=lambda event: event.start)
        return events

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming collection."""
        today = date.today()
        return next((event for event in self._events() if event.start >= today), None)

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return the collections that fall inside the requested window."""
        start = start_date.date()
        end = end_date.date()
        return [event for event in self._events() if start <= event.start <= end]
