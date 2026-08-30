"""Constants used by the IDM integration."""

from datetime import timedelta
import json
from pathlib import Path
from typing import Final

from homeassistant.const import Platform

from .models import IDMEnvironment

PLATFORMS: Final = [Platform.CALENDAR, Platform.SENSOR]

ATTRIBUTION: Final = "Data provided by IDM"

WEBSITE: Final = "https://www.mijnidm.be/"

DEFAULT_IDM_ENVIRONMENT = IDMEnvironment(
    api_endpoint="https://www.mijnidm.be",
)

# Attributes that hold long lists; keeping them out of the recorder database
# avoids bloating it on every coordinator refresh.
UNRECORDED_ATTRIBUTES: Final = {
    "ledigingen",
    "stortingen",
    "afval_op_afroep",
    "recyclagepark_bezoeken",
    "reservaties",
    "fracties",
    "jaarverbruik",
    "gemiddelde_per_gezinsgrootte",
}

# Fields that must never be logged or exposed as entity attributes.
SENSITIVE_FIELDS: Final = [
    "password",
    "national_registration_number",
    "rijksregisternummer",
]

BASE_HEADERS: Final = {
    "x-requested-with": "XMLHttpRequest",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
}

# The portal accepts dd/mm/yyyy for its date filters.
API_DATE_FORMAT: Final = "%d/%m/%Y"
# Emptyings and visits come back as ISO-8601 with microseconds, in UTC.
API_DATETIME_FORMATS: Final = (
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%d",
)

# Far enough back to capture a full DIFTAR history.
HISTORY_FROM_DATE: Final = "01/01/2010"

# Recycle! (Fost Plus) serves the collection calendar that idm.be embeds. Its
# public API needs no key, and the address from the IDM portal is enough to
# resolve a schedule, so the calendar configures itself.
RECYCLE_APP_SETTINGS_URL: Final = "https://www.recycleapp.be/config/app.settings.json"
RECYCLE_CONSUMER: Final = "recycleapp.be"
RECYCLE_LANGUAGE: Final = "nl"
RECYCLE_FORECAST_WEEKS: Final = 12

COORDINATOR_UPDATE_INTERVAL: Final = timedelta(minutes=30)
CONNECTION_RETRY: Final = 5
REQUEST_TIMEOUT: Final = 20

manifestfile = Path(__file__).parent / "manifest.json"
with open(manifestfile, encoding="utf-8") as json_file:
    manifest_data = json.load(json_file)

DOMAIN: Final = manifest_data.get("domain")
NAME: Final = manifest_data.get("name")
VERSION: Final = manifest_data.get("version")
ISSUEURL: Final = manifest_data.get("issue_tracker")

STARTUP: Final = f"""
-------------------------------------------------------------------
{NAME}
Version: {VERSION}
This is a custom component
If you have any issues with this you need to open an issue here:
{ISSUEURL}
-------------------------------------------------------------------
"""
