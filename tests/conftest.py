"""Test bootstrap.

These tests exercise the portal client and its helpers, which are pure Python.
Two things are arranged here so that a full Home Assistant install is not needed
to run them:

1. ``custom_components/idm/__init__.py`` sets up the config entry and pulls in a
   large part of Home Assistant. The component directory is therefore mounted as
   a bare package named ``idm`` so ``idm.client`` can be imported on its own.
2. ``const.py`` needs ``homeassistant.const.Platform``; a minimal shim is
   registered when Home Assistant is not installed. The real package wins when
   it is.
"""

from __future__ import annotations

import enum
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "idm"

sys.path.insert(0, str(ROOT))

try:  # pragma: no cover - exercised only when HA is installed
    import homeassistant.const
except ModuleNotFoundError:  # pragma: no cover - the common case for this repo
    homeassistant = types.ModuleType("homeassistant")
    const = types.ModuleType("homeassistant.const")

    class Platform(enum.StrEnum):
        """Minimal stand-in for homeassistant.const.Platform."""

        CALENDAR = "calendar"
        SENSOR = "sensor"

    const.Platform = Platform
    homeassistant.const = const
    sys.modules["homeassistant"] = homeassistant
    sys.modules["homeassistant.const"] = const

# Mount the component as a package without running its Home Assistant setup.
if "idm" not in sys.modules:
    package = types.ModuleType("idm")
    package.__path__ = [str(COMPONENT)]
    sys.modules["idm"] = package
