"""Firmware update check for the BYD HVS Battery integration.

Two update entities ("BMU Firmware" and "BMS Firmware") compare the firmware
installed on the battery with the newest firmware offered by BYD's download
server (the same server the BYD Be Connect app uses).

The entities are disabled by default. Enabling at least one of them is the
opt-in for the online check: while both are disabled, no request is sent to
BYD. The firmware cannot be installed from Home Assistant; updates are only
possible via the BYD Be Connect app.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import dt as dt_util

from .const import DOMAIN, signal_coordinator_ready

_LOGGER = logging.getLogger(__name__)

# Unofficial endpoint used by BYD Be Connect / Be Connect Plus to list the
# firmware files available for download. It may change or disappear.
FIRMWARE_LIST_URL = "https://deapp.byd.com/api/V1/Http2/GetFileNewLink"
FIRMWARE_LIST_PAYLOAD = {"SoftVersion": "V1.0"}
FIRMWARE_CHECK_INTERVAL = timedelta(hours=24)
FIRMWARE_REQUEST_TIMEOUT = 10

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.firmware_versions"

RELEASE_URL = "https://github.com/bbr111/byd_hvs#firmware-update-check"
PRIVACY_URL = "https://github.com/bbr111/byd_hvs#network--privacy"
FORUM_URL = "https://www.photovoltaikforum.com/thread/150898-byd-hvs-firmware-update/"
# HA truncates release_summary to 255 characters; links go to the README,
# which has the forum link and the Network / Privacy details.
RELEASE_SUMMARY = (
    "Update only via the BYD Be Connect app. Ask your installer or the forum "
    "first (aggressive balancing reported since BMS 3.31). This entity "
    "contacts a BYD server once a day, see Network / Privacy: "
    f"{PRIVACY_URL}"
)

# e.g. "BMU-P3-3.27-A-8956.bin", "BMS-P2-1.17-B-49DE.bin"
_FILE_NAME_RE = re.compile(
    r"^(?P<kind>BMU|BMS)-(?P<line>P\d+)-(?P<major>\d+)\.(?P<minor>\d+)-[A-Z]",
    re.IGNORECASE,
)
# e.g. "V3.31-B", "3.26", "V1.8-A"
_INSTALLED_RE = re.compile(r"^\s*V?(?P<major>\d+)\.(?P<minor>\d+)")

# Firmware line per installed major version: P3 = Premium HVS/HVM/HVL,
# P2 = Premium LVS/LVL.
LINE_BY_MAJOR = {3: "P3", 1: "P2"}

FIRMWARE_TYPES = {
    "bmu": ("BMU", "bmu_firmware", "BMU Firmware"),
    "bms": ("BMS", "bms_firmware", "BMS Firmware"),
}

Version = tuple[int, int]


def parse_installed_version(value: Any) -> Version | None:
    """Return (major, minor) of an installed version like "V3.31-B"."""
    if not isinstance(value, str):
        return None
    match = _INSTALLED_RE.match(value)
    if match is None:
        return None
    return int(match["major"]), int(match["minor"])


def format_version(version: Version | None) -> str | None:
    """Format a version tuple as "3.31" (minor zero-padded to two digits)."""
    if version is None:
        return None
    return f"{version[0]}.{version[1]:02d}"


def parse_firmware_list(payload: Any) -> dict[str, dict[str, Version]]:
    """Return the newest version per kind and line from the BYD response.

    Result example: {"BMU": {"P3": (3, 27), "P2": (1, 37)}, "BMS": {...}}.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("Data"), list):
        raise TypeError("Unexpected firmware list format")
    latest: dict[str, dict[str, Version]] = {"BMU": {}, "BMS": {}}
    for item in payload["Data"]:
        if not isinstance(item, dict):
            continue
        match = _FILE_NAME_RE.match(str(item.get("FileName", "")))
        if match is None:
            continue
        kind = match["kind"].upper()
        line = match["line"].upper()
        version = (int(match["major"]), int(match["minor"]))
        if version > latest[kind].get(line, (-1, -1)):
            latest[kind][line] = version
    return latest


class BYDFirmwareCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch the list of available firmware from BYD once a day.

    No refresh is done at setup. The first request is triggered when an update
    entity is added (i.e. enabled), and the coordinator only keeps polling while
    it has listeners.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="BYD HVS firmware check",
            update_interval=FIRMWARE_CHECK_INTERVAL,
        )
        self._session = async_get_clientsession(hass)
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._loaded = False
        self._started = False
        self._warned = False

    async def _async_load(self) -> None:
        """Load the last known versions saved before a restart."""
        if self._loaded:
            return
        self._loaded = True
        stored = await self._store.async_load()
        if isinstance(stored, dict) and isinstance(stored.get("latest"), dict):
            latest = {
                kind: {
                    line: tuple(version)
                    for line, version in (stored["latest"].get(kind) or {}).items()
                    if isinstance(version, list) and len(version) == 2
                }
                for kind in ("BMU", "BMS")
            }
            self.async_set_updated_data(
                {"latest": latest, "fetched": stored.get("fetched")}
            )

    async def async_start(self) -> None:
        """Run the first check when the first entity is added.

        If the stored result is younger than the check interval, no request is
        made now; the next one follows with the regular daily schedule.
        """
        if self._started:
            return
        self._started = True
        await self._async_load()
        fetched = None
        if self.data and self.data.get("fetched"):
            fetched = dt_util.parse_datetime(self.data["fetched"])
        if fetched is not None and dt_util.utcnow() - fetched < self.update_interval:
            return
        await self.async_refresh()

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the firmware list; keep the last known data on failure."""
        await self._async_load()
        try:
            async with asyncio.timeout(FIRMWARE_REQUEST_TIMEOUT):
                async with self._session.post(
                    FIRMWARE_LIST_URL, json=FIRMWARE_LIST_PAYLOAD
                ) as response:
                    response.raise_for_status()
                    payload = await response.json(content_type=None)
            latest = parse_firmware_list(payload)
        except (aiohttp.ClientError, TimeoutError, ValueError, TypeError) as err:
            if not self._warned:
                self._warned = True
                _LOGGER.warning(
                    "Could not check for BYD firmware updates (%s); "
                    "keeping the last known versions",
                    err,
                )
            return self.data or {}

        if self._warned:
            _LOGGER.info("BYD firmware update check is working again")
            self._warned = False
        fetched = dt_util.utcnow().isoformat()
        await self._store.async_save(
            {
                "latest": {
                    kind: {line: list(version) for line, version in lines.items()}
                    for kind, lines in latest.items()
                },
                "fetched": fetched,
            }
        )
        return {"latest": latest, "fetched": fetched}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the firmware update entities (disabled by default)."""
    serial = config_entry.unique_id or config_entry.data.get("serial_number")
    if not serial:
        battery_data = hass.data.get(DOMAIN, {}).get(config_entry.entry_id, {})
        serial = getattr(battery_data.get("battery"), "hvs_serial", "")
    if not serial:
        raise PlatformNotReady("Serial number of the BYD battery not known yet")

    coordinator = BYDFirmwareCoordinator(hass, config_entry)
    async_add_entities(
        BYDFirmwareUpdateEntity(coordinator, config_entry, serial, key)
        for key in FIRMWARE_TYPES
    )


class BYDFirmwareUpdateEntity(CoordinatorEntity[BYDFirmwareCoordinator], UpdateEntity):
    """Compare installed BMU/BMS firmware with the newest one offered by BYD."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_has_entity_name = True  # "BYD Battery <serial> BMU Firmware"
    _attr_icon = "mdi:chip"
    _attr_release_url = RELEASE_URL
    _attr_release_summary = RELEASE_SUMMARY
    _attr_supported_features = UpdateEntityFeature(0)  # no install support

    def __init__(
        self,
        coordinator: BYDFirmwareCoordinator,
        entry: ConfigEntry,
        serial: str,
        key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._battery_unsub: Callable[[], None] | None = None
        self._subscribed_to: DataUpdateCoordinator | None = None
        self._kind, self._data_key, self._attr_name = FIRMWARE_TYPES[key]
        self._attr_unique_id = f"byd_{serial}_{key}_firmware_update"
        # Historic entity_id scheme (update.byd_bmu_firmware); Home Assistant
        # would otherwise prefix the device name to new entity ids.
        self.entity_id = f"update.byd_{key}_firmware"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, serial)},
            "name": f"BYD Battery {serial}",
            "manufacturer": "BYD",
        }

    async def async_added_to_hass(self) -> None:
        """Start the firmware check and follow the battery data."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal_coordinator_ready(self._entry.entry_id),
                self._async_battery_ready,
            )
        )
        self.async_on_remove(self._async_unsubscribe_battery)
        self._async_battery_ready()
        self.hass.async_create_task(self.coordinator.async_start())

    @callback
    def _async_unsubscribe_battery(self) -> None:
        if self._battery_unsub is not None:
            self._battery_unsub()
            self._battery_unsub = None
        self._subscribed_to = None

    @callback
    def _async_battery_ready(self) -> None:
        """Subscribe to the battery coordinator for the installed version."""
        battery_coordinator = self._battery_coordinator
        if battery_coordinator is None or battery_coordinator is self._subscribed_to:
            return
        self._async_unsubscribe_battery()
        self._subscribed_to = battery_coordinator
        self._battery_unsub = battery_coordinator.async_add_listener(
            self.async_write_ha_state
        )
        self.async_write_ha_state()

    @property
    def _battery_coordinator(self) -> DataUpdateCoordinator | None:
        return (
            self.hass.data.get(DOMAIN, {})
            .get(self._entry.entry_id, {})
            .get("coordinator")
        )

    @property
    def _installed(self) -> Version | None:
        battery_coordinator = self._battery_coordinator
        if battery_coordinator is None or not battery_coordinator.data:
            return None
        return parse_installed_version(battery_coordinator.data.get(self._data_key))

    @property
    def installed_version(self) -> str | None:
        """Installed firmware version without the flash bank suffix (A/B)."""
        return format_version(self._installed)

    @property
    def latest_version(self) -> str | None:
        """Newest firmware of the same line offered by BYD, if known."""
        installed = self._installed
        data = self.coordinator.data or {}
        if installed is None or not data.get("latest"):
            return None
        line = LINE_BY_MAJOR.get(installed[0])
        latest = data["latest"].get(self._kind, {}).get(line)
        if latest is None:
            return None
        # Never report an older server version as "latest".
        return format_version(max(latest, installed))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose when BYD was last checked successfully."""
        fetched = (self.coordinator.data or {}).get("fetched")
        return {"last_check": fetched} if fetched else None

    def version_is_newer(self, latest_version: str, installed_version: str) -> bool:
        """Compare versions numerically ("3.8" < "3.10")."""
        latest = parse_installed_version(latest_version)
        installed = parse_installed_version(installed_version)
        if latest is None or installed is None:
            return latest_version != installed_version
        return latest > installed
