"""Sensor platform for the BYD HVS Battery integration."""

from datetime import timedelta
import logging
import re

import asyncio
import bydhvs
from bydhvs import BYDHVSConnectionError, BYDHVSTimeoutError, BYDHVSError

from homeassistant.components.sensor import SensorEntity

from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfEnergy,
    UnitOfTemperature,
    PERCENTAGE,
    EntityCategory,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SHOW_CELL_TEMPERATURE,
    SHOW_CELL_VOLTAGE,
    SHOW_MODULES,
    SHOW_RESET_COUNTER,
    SHOW_TOWERS,
    AGGREGATE_MODULES,
    signal_coordinator_ready,
)

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    "soc": ["State of Charge", "mdi:battery", PERCENTAGE, SensorDeviceClass.BATTERY],
    "power": ["Power", "mdi:flash", UnitOfPower.WATT, SensorDeviceClass.POWER],
    "max_voltage": [
        "Max Voltage",
        "mdi:current-ac",
        UnitOfElectricPotential.VOLT,
        SensorDeviceClass.VOLTAGE,
    ],
    "min_voltage": [
        "Min Voltage",
        "mdi:current-ac",
        UnitOfElectricPotential.VOLT,
        SensorDeviceClass.VOLTAGE,
    ],
    "current": [
        "Current",
        "mdi:current-dc",
        UnitOfElectricCurrent.AMPERE,
        SensorDeviceClass.CURRENT,
    ],
    "battery_voltage": [
        "Battery Voltage",
        "mdi:car-battery",
        UnitOfElectricPotential.VOLT,
        SensorDeviceClass.VOLTAGE,
    ],
    "max_temperature": [
        "Max Temperature",
        "mdi:thermometer",
        UnitOfTemperature.CELSIUS,
        SensorDeviceClass.TEMPERATURE,
    ],
    "min_temperature": [
        "Min Temperature",
        "mdi:thermometer",
        UnitOfTemperature.CELSIUS,
        SensorDeviceClass.TEMPERATURE,
    ],
    "battery_temperature": [
        "Battery Temperature",
        "mdi:thermometer",
        UnitOfTemperature.CELSIUS,
        SensorDeviceClass.TEMPERATURE,
    ],
    "voltage_difference": [
        "Voltage Difference",
        "mdi:delta",
        UnitOfElectricPotential.VOLT,
        SensorDeviceClass.VOLTAGE,
    ],
    "soh": [
        "State of Health",
        "mdi:heart-pulse",
        PERCENTAGE,
        None,
        SensorStateClass.MEASUREMENT,
    ],
    "serial_number": ["Serial Number", "mdi:identifier", None, None],
    "bmu_firmware": ["BMU Firmware", "mdi:chip", None, None],
    "bms_firmware": ["BMS Firmware", "mdi:chip", None, None],
    "modules": ["Modules", "mdi:counter", None, None],
    "module_cell_count": ["ModuleCellCount", "mdi:counter", None, None],
    "module_cell_temp_count": ["ModuleCellTempCount", "mdi:counter", None, None],
    "towers": ["Towers", "mdi:counter", None, None],
    "grid_type": ["Grid Type", "mdi:transmission-tower", None, None],
    "error_number": ["Error Number", "mdi:alert-circle", None, None],
    "error_string": ["Error String", "mdi:alert-circle", None, None],
    "param_t": ["Param T", "mdi:information-outline", None, None],
    "output_voltage": [
        "Output Voltage",
        "mdi:current-ac",
        UnitOfElectricPotential.VOLT,
        SensorDeviceClass.VOLTAGE,
    ],
    "charge_total": [
        "Charge Total",
        "mdi:battery-charging",
        UnitOfEnergy.KILO_WATT_HOUR,
        SensorDeviceClass.ENERGY,
        SensorStateClass.TOTAL_INCREASING,
    ],
    "discharge_total": [
        "Discharge Total",
        "mdi:battery-minus",
        UnitOfEnergy.KILO_WATT_HOUR,
        SensorDeviceClass.ENERGY,
        SensorStateClass.TOTAL_INCREASING,
    ],
    "eta": ["ETA", "mdi:timer", PERCENTAGE, None],
    "battery_type_from_serial": [
        "Battery Type From Serial",
        "mdi:information-outline",
        None,
        None,
    ],
    "battery_type": ["Battery Type", "mdi:information-outline", None, None],
    "battery_type_string": [
        "Battery Type String",
        "mdi:information-outline",
        None,
        None,
    ],
    "inverter_type": ["Inverter Type", "mdi:information-outline", None, None],
    "number_of_cells": ["Number of Cells", "mdi:counter", None, None],
    "number_of_temperatures": ["Number of Temperatures", "mdi:counter", None, None],
}

TOWER_SENSOR_TYPES = {
    "balancing_status": ["Balancing Status", "mdi:scale-balance", None, None],
    "balancing_count": ["Balancing Count", "mdi:counter", None, None],
    "max_cell_voltage_mv": [
        "Max Cell Voltage mV",
        "mdi:current-ac",
        UnitOfElectricPotential.MILLIVOLT,
        SensorDeviceClass.VOLTAGE,
    ],
    "min_cell_voltage_mv": [
        "Min Cell Voltage mV",
        "mdi:current-ac",
        UnitOfElectricPotential.MILLIVOLT,
        SensorDeviceClass.VOLTAGE,
    ],
    "max_cell_voltage_cell": ["Voltage Max Cell No", "mdi:counter", None, None],
    "min_cell_voltage_cell": ["Voltage Min Cell No", "mdi:counter", None, None],
    "max_cell_temp": [
        "Temperature Max Cell",
        "mdi:thermometer",
        UnitOfTemperature.CELSIUS,
        SensorDeviceClass.TEMPERATURE,
    ],
    "min_cell_temp": [
        "Temperature Min Cell",
        "mdi:thermometer",
        UnitOfTemperature.CELSIUS,
        SensorDeviceClass.TEMPERATURE,
    ],
    "max_cell_temp_cell": ["Temperature Max Cell No", "mdi:counter", None, None],
    "min_cell_temp_cell": ["Temperature Min Cell No", "mdi:counter", None, None],
    "charge_total": [
        "Charge Total",
        "mdi:battery-charging",
        UnitOfEnergy.KILO_WATT_HOUR,
        SensorDeviceClass.ENERGY,
        SensorStateClass.TOTAL_INCREASING,
    ],
    "discharge_total": [
        "Discharge Total",
        "mdi:battery-minus",
        UnitOfEnergy.KILO_WATT_HOUR,
        SensorDeviceClass.ENERGY,
        SensorStateClass.TOTAL_INCREASING,
    ],
    "eta": ["ETA", "mdi:timer", PERCENTAGE, None],
    "battery_volt": [
        "Battery Voltage",
        "mdi:car-battery",
        UnitOfElectricPotential.VOLT,
        SensorDeviceClass.VOLTAGE,
    ],
    "out_volt": [
        "Output Voltage",
        "mdi:current-ac",
        UnitOfElectricPotential.VOLT,
        SensorDeviceClass.VOLTAGE,
    ],
    "current": [
        "Current",
        "mdi:current-dc",
        UnitOfElectricCurrent.AMPERE,
        SensorDeviceClass.CURRENT,
    ],
    "hvs_soc_diagnosis": [
        "SOC Diagnosis",
        "mdi:battery",
        PERCENTAGE,
        None,
    ],
    "soh": [
        "State of Health",
        "mdi:heart-pulse",
        PERCENTAGE,
        None,
        SensorStateClass.MEASUREMENT,
    ],
    "state": ["State", "mdi:information-outline", None, None],
    "state_string": ["State String", "mdi:information-outline", None, None],
}


# Default display precision per sensor type, matching the resolution bydhvs
# delivers (see the Modbus scaling in bydhvs). Text, hex and count sensors
# have none. Users can still override it in the entity settings.
SENSOR_PRECISION = {
    "soc": 0,  # integer %
    "power": 0,  # W, current (0.1 A) x voltage (0.1 V)
    "max_voltage": 2,  # V, /100 (highest cell voltage)
    "min_voltage": 2,  # V, /100 (lowest cell voltage)
    "current": 1,  # A, /10
    "battery_voltage": 1,  # V, /100 rounded to 0.1 by bydhvs
    "max_temperature": 0,  # integer °C
    "min_temperature": 0,
    "battery_temperature": 0,
    "voltage_difference": 3,  # V, difference of /100 values
    "soh": 0,  # integer %
    "output_voltage": 1,  # V, /100 rounded to 0.1 by bydhvs
    "charge_total": 1,  # kWh, /10
    "discharge_total": 1,  # kWh, /10
    "eta": 1,  # %, calculated
}

TOWER_SENSOR_PRECISION = {
    "max_cell_voltage_mv": 0,  # integer mV
    "min_cell_voltage_mv": 0,
    "max_cell_temp": 0,  # integer °C
    "min_cell_temp": 0,
    "charge_total": 3,  # kWh, /1000 (Wh resolution)
    "discharge_total": 3,
    "eta": 1,  # %, calculated
    "battery_volt": 1,  # V, /10
    "out_volt": 1,  # V, /10
    "current": 1,  # A, /10
    "hvs_soc_diagnosis": 1,  # %, /10
    "soh": 0,  # integer %
}


def _plausible_count(
    available: int, total: int | None, per_module: int | None, modules: int | None
) -> int:
    """Return how many cell values can be trusted.

    Older bydhvs versions can return more values than the battery has (e.g. a
    negative slice appended ~110 garbage temperature bytes for systems with
    <= 30 temperature sensors). Limit the list to the count reported by the
    library and fall back to the full list if no count is known.
    """
    expected = total or 0
    if expected <= 0 and per_module and modules:
        expected = per_module * modules
    if expected <= 0:
        return available
    return min(available, expected)


# Cell sensor category -> (list key in tower data, total count key,
# per-module count key) as returned by bydhvs.
CELL_CATEGORIES = {
    "cell_voltage": ("cell_voltages", "number_of_cells", "module_cell_count"),
    "cell_temperature": (
        "cell_temperatures",
        "number_of_temperatures",
        "module_cell_temp_count",
    ),
}


def _plausible_cell_count(data: dict, tower: dict, category: str) -> int:
    """Return the number of trustworthy values of a category for a tower."""
    list_key, total_key, per_module_key = CELL_CATEGORIES[category]
    return _plausible_count(
        len(tower.get(list_key, [])),
        data.get(total_key),
        data.get(per_module_key),
        data.get("modules") or 0,
    )


def _per_module(data: dict, category: str) -> int:
    """Return the number of values per module (at least 1)."""
    return data.get(CELL_CATEGORIES[category][2]) or 1


def _index_width(count: int, show_reset_counter: bool) -> int:
    """Return the zero-padded width of the cell index in names/unique_ids."""
    if show_reset_counter:
        return 2
    return 3 if count >= 100 else 2


def _cell_unique_id(
    serial: str, category: str, tower_index: int, module: int, index: int, width: int
) -> str:
    """Return the unique_id of a cell voltage/temperature sensor."""
    return f"byd_{serial}_{category}_{tower_index + 1}_{module}_{index:0{width}d}"


def _cell_entity_specs(
    data: dict,
    tower: dict,
    category: str,
    show_modules: bool,
    show_reset_counter: bool,
) -> list[tuple[int, int, int, int]]:
    """Return (cell_index, module_no, counter, width) for each cell entity.

    Used both to create the entities and to compute the unique_ids for the
    registry migration, so both always agree.
    """
    count = _plausible_cell_count(data, tower, category)
    per_module = _per_module(data, category)
    width = _index_width(count, show_reset_counter)
    specs = []
    counter = 0
    for cell_index in range(count):
        counter += 1
        if show_reset_counter and counter > per_module:
            counter = 1
        module_no = cell_index // per_module + 1 if show_modules else 0
        specs.append((cell_index, module_no, counter, width))
    return specs


def _tower_module_count(data: dict, tower: dict) -> int:
    """Return the number of modules of a tower.

    Use the module count reported by the BMU; only derive it from the
    (plausible) list lengths if the library did not report one.
    """
    if modules := data.get("modules") or 0:
        return modules
    return max(
        _plausible_cell_count(data, tower, "cell_voltage")
        // _per_module(data, "cell_voltage"),
        _plausible_cell_count(data, tower, "cell_temperature")
        // _per_module(data, "cell_temperature"),
        1,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BYD Battery sensors from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = {}

    ip_address = config_entry.data["ip_address"]
    port = config_entry.data.get("port", 8080)
    scan_interval = config_entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL)
    show_cell_voltage = config_entry.data.get(SHOW_CELL_VOLTAGE, True)
    show_cell_temperature = config_entry.data.get(SHOW_CELL_TEMPERATURE, True)
    show_modules = config_entry.data.get(SHOW_MODULES, False)
    show_reset_counter = config_entry.data.get(SHOW_RESET_COUNTER, False)
    show_towers = config_entry.data.get(SHOW_TOWERS, True)
    aggregate_modules = config_entry.data.get(AGGREGATE_MODULES, False)

    byd_hvs = bydhvs.BYDHVS(ip_address, port)

    async def async_update_data():
        """Fetch data from the BYD HVS battery."""
        _LOGGER.debug("Starting data retrieval from the BYD HVS Battery")

        try:
            await byd_hvs.poll()
            data = byd_hvs.get_data()

            if not data:
                _LOGGER.warning(
                    "No data received from BYD HVS, keeping previous values"
                )
                return coordinator.data or {}

            # Validate structure
            if "tower_attributes" not in data or not isinstance(
                data["tower_attributes"], list
            ):
                _LOGGER.warning(
                    "Malformed data: tower_attributes missing or invalid → %s", data
                )
                return coordinator.data or {}

            _LOGGER.debug("Data block: %s", data)
            _LOGGER.debug("Data retrieval successfully completed")

            return data

        except (BYDHVSConnectionError, BYDHVSTimeoutError) as e:
            _LOGGER.warning(
                "Connection/timeout issue with BYD HVS @ %s:%s – %s",
                ip_address,
                port,
                e,
            )
            return coordinator.data or {}

        except BYDHVSError as e:
            _LOGGER.error("General BYD HVS error @ %s:%s – %s", ip_address, port, e)
            return coordinator.data or {}

        except asyncio.TimeoutError as e:
            _LOGGER.warning(
                "Async timeout while polling BYD HVS @ %s:%s – %s", ip_address, port, e
            )
            return coordinator.data or {}

        except (ValueError, AttributeError, TypeError) as e:
            _LOGGER.exception(
                "Data processing error from BYD HVS @ %s:%s – %s", ip_address, port, e
            )
            return coordinator.data or {}

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="BYD HVS Battery",
        update_method=async_update_data,
        update_interval=timedelta(seconds=scan_interval),
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except UpdateFailed as err:
        _LOGGER.warning(
            "Initial data load from BYD HVS failed: %s — sensors will "
            "update automatically when data becomes available",
            err,
        )

    # The serial number is part of every unique_id, but it is only known after
    # a successful poll. Without a stable fallback the first setup would
    # register entities as "byd__<sensor>", and a later successful setup would
    # register them again as "byd_<serial>_<sensor>", leaving orphaned
    # duplicate entities behind. The config entry unique_id is known without
    # polling and is set to the battery serial by the config flow.
    serial = (
        getattr(byd_hvs, "hvs_serial", "")
        or config_entry.unique_id
        or config_entry.data.get("serial_number")
        or ""
    )
    if not serial or not (coordinator.data or {}).get("tower_attributes"):
        raise PlatformNotReady(
            "BYD HVS did not return complete data during setup "
            "(serial number or tower data missing)"
        )
    byd_hvs.hvs_serial = serial

    # Clean up entities registered by older versions without a serial number,
    # before the entities are added so migrated registry entries are reused.
    _async_migrate_orphan_entities(hass, config_entry, serial)

    hass.data[DOMAIN][config_entry.entry_id]["coordinator"] = coordinator
    hass.data[DOMAIN][config_entry.entry_id]["battery"] = byd_hvs
    # Let the firmware update entities pick up the installed versions.
    async_dispatcher_send(hass, signal_coordinator_ready(config_entry.entry_id))

    sensors: list[SensorEntity] = []

    # General sensors
    sensors.extend(
        [
            BYDBatterySensor(coordinator, sensor_type, byd_hvs)
            for sensor_type in SENSOR_TYPES
        ]
    )

    towers = coordinator.data.get("tower_attributes", [])
    if not towers:
        _LOGGER.debug("No tower data available yet; will populate on next update")

    # Tower sensors
    if show_towers:
        sensors.extend(
            [
                BYDBatterySensor(
                    coordinator,
                    sensor_type,
                    byd_hvs,
                    tower_index,
                    0,
                    "tower",
                )
                for tower_index in range(len(towers))
                for sensor_type in TOWER_SENSOR_TYPES
            ]
        )

    data = coordinator.data

    # Fix up cell/module entities registered with wrong counts by older
    # versions (e.g. 100+ bogus temperatures), before the entities are added.
    _async_migrate_cell_entities(
        hass, config_entry, serial, data, show_modules, show_reset_counter
    )

    # Runs on every setup (not only during a migration), so installations that
    # were already migrated by 0.4.14 are repaired as well (#47).
    _async_repair_device_disabled_entities(hass, config_entry)

    # Cell voltage and temperature sensors
    for category, enabled in (
        ("cell_voltage", show_cell_voltage),
        ("cell_temperature", show_cell_temperature),
    ):
        if not enabled:
            continue
        for tower_index, tower in enumerate(towers):
            for cell_index, module_no, counter, width in _cell_entity_specs(
                data, tower, category, show_modules, show_reset_counter
            ):
                cell_no = f"{module_no}_{counter}" if show_modules else cell_index + 1
                sensors.append(
                    BYDBatterySensor(
                        coordinator,
                        f"{category}_{tower_index + 1}_{cell_no}",
                        byd_hvs,
                        tower_index,
                        cell_index,
                        category,
                        width,
                        module_no,
                        counter,
                    )
                )

    if aggregate_modules:
        _LOGGER.debug(
            "Aggregate enabled: %s | Towers found: %s", aggregate_modules, len(towers)
        )
        for tower_index, tower in enumerate(towers):
            sensors.extend(
                BYDModuleAggregateSensor(
                    coordinator, module_index, tower_index, byd_hvs
                )
                for module_index in range(_tower_module_count(data, tower))
            )

    async_add_entities(sensors)


def _prefer_existing(
    ent_reg: er.EntityRegistry, entry: er.RegistryEntry, existing_entity_id: str
) -> bool:
    """Return True if the existing duplicate should be kept instead of entry.

    The outdated entry normally wins (it holds the original entity_id), but not
    if it is disabled while the duplicate is enabled (#47).
    """
    existing = ent_reg.async_get(existing_entity_id)
    return (
        entry.disabled_by is not None
        and existing is not None
        and existing.disabled_by is None
    )


@callback
def _async_update_unique_id(
    ent_reg: er.EntityRegistry, entry: er.RegistryEntry, new_unique_id: str
) -> None:
    """Change the unique_id; re-enable entities only disabled via a device.

    If the entity's device is really disabled, Home Assistant disables the
    entity again when it is added.
    """
    if entry.disabled_by is er.RegistryEntryDisabler.DEVICE:
        ent_reg.async_update_entity(
            entry.entity_id, new_unique_id=new_unique_id, disabled_by=None
        )
    else:
        ent_reg.async_update_entity(entry.entity_id, new_unique_id=new_unique_id)


@callback
def _async_repair_device_disabled_entities(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Re-enable entities disabled only via a device that is not disabled.

    Older versions created a bogus device "BYD Battery " with an empty serial
    (identifier (DOMAIN, "")). If users disabled it, its entities got
    disabled_by=device, and the 0.4.14 migration could keep such entities and
    move them to the real device, where they stayed disabled (#47).

    - Entities still attached to the bogus device are detached from it; Home
      Assistant attaches them to the real device when they are added.
    - Entities with disabled_by=device whose device is not disabled (or is the
      bogus device) are re-enabled. If the device is disabled, Home Assistant
      disables them again when they are added.
    - The bogus device is removed once no entity references it anymore and it
      belongs to this config entry only.
    """
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    bogus = dev_reg.async_get_device(identifiers={(DOMAIN, "")})
    bogus_id = bogus.id if bogus else None
    # device_id -> device is disabled; there are only one or two devices, but
    # hundreds of cell entities.
    device_disabled: dict[str, bool] = {}
    reenabled: list[str] = []

    # Single pass over all entities of this entry (incl. cell entities).
    for entry in er.async_entries_for_config_entry(ent_reg, config_entry.entry_id):
        changes: dict = {}
        on_bogus = bogus_id is not None and entry.device_id == bogus_id
        if on_bogus:
            changes["device_id"] = None
        if entry.disabled_by is er.RegistryEntryDisabler.DEVICE:
            disabled = False
            if entry.device_id and not on_bogus:
                if entry.device_id not in device_disabled:
                    device = dev_reg.async_get(entry.device_id)
                    device_disabled[entry.device_id] = bool(device and device.disabled)
                disabled = device_disabled[entry.device_id]
            if not disabled:
                changes["disabled_by"] = None
                reenabled.append(entry.entity_id)
        if changes:
            ent_reg.async_update_entity(entry.entity_id, **changes)

    if reenabled:
        _LOGGER.warning(
            "Re-enabled %d entities that were disabled via a device which is "
            "not disabled (anymore), e.g. %s",
            len(reenabled),
            ", ".join(reenabled[:5]),
        )

    if (
        bogus is not None
        and bogus.config_entries <= {config_entry.entry_id}
        and not er.async_entries_for_device(
            ent_reg, bogus.id, include_disabled_entities=True
        )
    ):
        _LOGGER.info("Removing empty device %s without serial number", bogus.name)
        dev_reg.async_remove_device(bogus.id)


# Prefix of unique_ids registered by older versions while the serial was empty.
ORPHAN_UNIQUE_ID_PREFIX = "byd__"


@callback
def _async_migrate_orphan_entities(
    hass: HomeAssistant, config_entry: ConfigEntry, serial: str
) -> None:
    """Migrate or remove entities registered with an empty serial number.

    Older versions could register entities as "byd__<sensor>" when the serial
    was not yet known, and later as "byd_<serial>_<sensor>" as well, leaving
    orphaned duplicates behind. The old entity's unique_id is rewritten so its
    entity_id, history and customizations are kept. If a duplicate with the
    new unique_id exists, that duplicate is removed first.
    """
    ent_reg = er.async_get(hass)
    new_prefix = f"byd_{serial}_"
    dropped = 0

    for entry in er.async_entries_for_config_entry(ent_reg, config_entry.entry_id):
        if not entry.unique_id.startswith(ORPHAN_UNIQUE_ID_PREFIX):
            continue

        new_unique_id = new_prefix + entry.unique_id[len(ORPHAN_UNIQUE_ID_PREFIX) :]
        existing_entity_id = ent_reg.async_get_entity_id(
            entry.domain, DOMAIN, new_unique_id
        )

        if existing_entity_id is not None and _prefer_existing(
            ent_reg, entry, existing_entity_id
        ):
            # The orphan is disabled (typically because the bogus empty-serial
            # device was disabled) but the duplicate works: keep the working
            # entity and drop the orphan (#47).
            _LOGGER.debug(
                "Removing disabled orphan entity %s (unique_id %s); keeping %s",
                entry.entity_id,
                entry.unique_id,
                existing_entity_id,
            )
            ent_reg.async_remove(entry.entity_id)
            dropped += 1
            continue

        if existing_entity_id is not None:
            # Keep the original entity (its entity_id is what automations and
            # dashboards usually reference, and it holds the longer history)
            # and drop the duplicate that was created later.
            _LOGGER.warning(
                "Removing duplicate entity %s (unique_id %s); %s is kept and "
                "migrated. Update automations, scripts and dashboards that "
                "reference %s",
                existing_entity_id,
                new_unique_id,
                entry.entity_id,
                existing_entity_id,
            )
            ent_reg.async_remove(existing_entity_id)

        _LOGGER.info(
            "Migrating %s: unique_id %s -> %s",
            entry.entity_id,
            entry.unique_id,
            new_unique_id,
        )
        _async_update_unique_id(ent_reg, entry, new_unique_id)

    if dropped:
        _LOGGER.warning(
            "Removed %d disabled orphan entities without serial number; the "
            "working duplicates were kept",
            dropped,
        )


_CELL_UNIQUE_ID_RE = re.compile(r"^(cell_voltage|cell_temperature)_(\d+)_(\d+)_(\d+)$")
_MODULE_UNIQUE_ID_RE = re.compile(r"^tower(\d+)_module(\d+)$")
_MAX_REMOVAL_WARNINGS = 10


@callback
def _async_migrate_cell_entities(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    serial: str,
    data: dict,
    show_modules: bool,
    show_reset_counter: bool,
) -> None:
    """Migrate or remove cell and module entities with outdated unique_ids.

    Older versions created far too many cell temperature entities when
    bydhvs returned garbage values (see #25). Because the zero-padded index
    width depends on the number of cells, the valid entities also got a
    different unique_id (e.g. "..._001" instead of "..._01").

    - Entities whose index still exists are migrated to the new unique_id, so
      entity_id, history and customizations are kept. If an entity with the
      new unique_id exists as well, the old entity is kept and the duplicate
      is removed (same policy as for the serial number migration).
    - Entities whose index or module is beyond the real count are removed.
    - Module aggregate entities beyond the real module count are removed.
    """
    ent_reg = er.async_get(hass)
    prefix = f"byd_{serial}_"
    towers = data.get("tower_attributes", [])

    # (category, tower_no, module, index) -> expected unique_id
    expected: dict[tuple[str, int, int, int], str] = {}
    # (category, tower_no) -> (number of cells, highest module number)
    limits: dict[tuple[str, int], tuple[int, int]] = {}
    for category in CELL_CATEGORIES:
        for tower_index, tower in enumerate(towers):
            specs = _cell_entity_specs(
                data, tower, category, show_modules, show_reset_counter
            )
            for _cell_index, module_no, counter, width in specs:
                expected[(category, tower_index + 1, module_no, counter)] = (
                    _cell_unique_id(
                        serial, category, tower_index, module_no, counter, width
                    )
                )
            limits[(category, tower_index + 1)] = (
                len(specs),
                specs[-1][1] if specs else 0,
            )
    expected_ids = set(expected.values())
    module_counts = {
        tower_index + 1: _tower_module_count(data, tower)
        for tower_index, tower in enumerate(towers)
    }

    removed: list[str] = []

    for entry in list(
        er.async_entries_for_config_entry(ent_reg, config_entry.entry_id)
    ):
        if entry.unique_id in expected_ids or not entry.unique_id.startswith(prefix):
            continue
        suffix = entry.unique_id[len(prefix) :]

        if match := _MODULE_UNIQUE_ID_RE.match(suffix):
            tower_no, module = int(match.group(1)), int(match.group(2))
            if tower_no in module_counts and module > module_counts[tower_no]:
                ent_reg.async_remove(entry.entity_id)
                removed.append(entry.entity_id)
            continue

        if not (match := _CELL_UNIQUE_ID_RE.match(suffix)):
            continue
        category, tower_no = match.group(1), int(match.group(2))
        module, index = int(match.group(3)), int(match.group(4))
        if (category, tower_no) not in limits:
            continue  # no data for this tower, leave it alone

        new_unique_id = expected.get((category, tower_no, module, index))
        if new_unique_id is not None:
            # Same cell, only the zero padding of the index changed.
            existing_entity_id = ent_reg.async_get_entity_id(
                entry.domain, DOMAIN, new_unique_id
            )
            if existing_entity_id is not None and _prefer_existing(
                ent_reg, entry, existing_entity_id
            ):
                # Old entity is disabled, the new one works: keep the new one.
                ent_reg.async_remove(entry.entity_id)
                removed.append(entry.entity_id)
                continue
            if existing_entity_id is not None:
                ent_reg.async_remove(existing_entity_id)
                removed.append(existing_entity_id)
            _LOGGER.info(
                "Migrating %s: unique_id %s -> %s",
                entry.entity_id,
                entry.unique_id,
                new_unique_id,
            )
            _async_update_unique_id(ent_reg, entry, new_unique_id)
            continue

        count, max_module = limits[(category, tower_no)]
        if index > count or (module > 0 and module > max_module):
            ent_reg.async_remove(entry.entity_id)
            removed.append(entry.entity_id)

    if not removed:
        return
    if len(removed) <= _MAX_REMOVAL_WARNINGS:
        for entity_id in removed:
            _LOGGER.warning(
                "Removed entity %s: it does not exist on the battery (or was a "
                "duplicate of a migrated entity)",
                entity_id,
            )
    else:
        _LOGGER.warning(
            "Removed %d cell/module entities that do not exist on the battery "
            "(or were duplicates of migrated entities), e.g. %s",
            len(removed),
            ", ".join(removed[:5]),
        )


class BYDBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for BYD HVS sensors providing shared device_info."""

    def __init__(self, coordinator, battery: bydhvs.BYDHVS):
        super().__init__(coordinator)
        self._battery = battery

    @property
    def device_info(self):
        """Return consistent device information for all BYD sensors."""
        return {
            "identifiers": {(DOMAIN, self._battery.hvs_serial)},
            "name": f"BYD Battery {self._battery.hvs_serial}",
            "manufacturer": "BYD",
            "model": self._battery.hvs_batt_type_string,
            "sw_version": self._battery.hvs_bms,
        }


class BYDBatterySensor(BYDBaseSensor):
    """Representation of a BYD HVS Battery sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        sensor_type: str,
        battery,
        tower_index=1,
        cell_index=1,
        sensor_category=None,
        num_digits: int = 2,
        module: int = 0,
        reset_counter: int = 0,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator, battery)
        self._sensor_type = sensor_type
        self._tower_index = tower_index  # For cell voltages and temperatures
        self._cell_index = cell_index  # For cell voltages and temperatures
        self._sensor_category = (
            sensor_category  # e.g., "cell_voltage", "cell_temperature"
        )
        self._num_digits = num_digits
        self._module = module
        self._reset_counter = reset_counter
        module_no = ""

        if sensor_category == "cell_voltage":
            cell_index_formatted = f"{self._reset_counter:0{self._num_digits}d}"
            self._cell_index_formatted = cell_index_formatted
            if self._module > 0:
                module_no = f" Module {self._module}"
            self._name = f"""Cell Voltage Tower {tower_index + 1}{module_no} Cell {
                cell_index_formatted
            }"""
            self._icon = "mdi:current-dc"
            self._attr_native_unit_of_measurement = UnitOfElectricPotential.MILLIVOLT
            self._attr_device_class = SensorDeviceClass.VOLTAGE
        elif sensor_category == "cell_temperature":
            cell_index_formatted = f"{self._reset_counter:0{self._num_digits}d}"
            self._cell_index_formatted = cell_index_formatted
            if self._module > 0:
                module_no = f" Module {self._module}"
            self._name = f"""Cell Temperature Tower {tower_index + 1}{module_no} Cell {
                cell_index_formatted
            }"""
            self._icon = "mdi:thermometer"
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
        elif sensor_category == "tower":
            self._name = f"Tower {tower_index + 1} {TOWER_SENSOR_TYPES[sensor_type][0]}"
            self._icon = TOWER_SENSOR_TYPES[sensor_type][1]
            self._attr_native_unit_of_measurement = TOWER_SENSOR_TYPES[sensor_type][2]
            self._attr_device_class = TOWER_SENSOR_TYPES[sensor_type][3]
            if len(TOWER_SENSOR_TYPES[sensor_type]) > 4:
                self._attr_state_class = TOWER_SENSOR_TYPES[sensor_type][4]
        else:
            self._name = SENSOR_TYPES[sensor_type][0]
            self._icon = SENSOR_TYPES[sensor_type][1]
            self._attr_native_unit_of_measurement = SENSOR_TYPES[sensor_type][2]
            self._attr_device_class = SENSOR_TYPES[sensor_type][3]

        if sensor_category in CELL_CATEGORIES:
            # Integer mV / integer °C from bydhvs.
            self._attr_suggested_display_precision = 0
        elif sensor_category == "tower":
            if (precision := TOWER_SENSOR_PRECISION.get(sensor_type)) is not None:
                self._attr_suggested_display_precision = precision
        elif (precision := SENSOR_PRECISION.get(sensor_type)) is not None:
            self._attr_suggested_display_precision = precision

        if sensor_category == "tower" and sensor_type == "balancing_status":
            # Raw hex bitmask of the balancing cells, mainly for diagnostics.
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
            self._attr_entity_registry_enabled_default = False

        # Set state_class: explicit definitions take precedence over defaults
        if self._sensor_category == "tower":
            if len(TOWER_SENSOR_TYPES.get(sensor_type, [])) > 4:
                self._attr_state_class = TOWER_SENSOR_TYPES[sensor_type][4]
            elif self._attr_device_class in (
                SensorDeviceClass.BATTERY,
                SensorDeviceClass.TEMPERATURE,
                SensorDeviceClass.VOLTAGE,
                SensorDeviceClass.CURRENT,
                SensorDeviceClass.POWER,
            ):
                self._attr_state_class = SensorStateClass.MEASUREMENT
        elif sensor_type in SENSOR_TYPES and len(SENSOR_TYPES[sensor_type]) > 4:
            self._attr_state_class = SENSOR_TYPES[sensor_type][4]
        elif self._attr_device_class in (
            SensorDeviceClass.BATTERY,
            SensorDeviceClass.TEMPERATURE,
            SensorDeviceClass.VOLTAGE,
            SensorDeviceClass.CURRENT,
            SensorDeviceClass.POWER,
        ):
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"BYD {self._name}"

    @property
    def unique_id(self):
        """Return a unique ID for the sensor."""
        hvs_serial = self._battery.hvs_serial

        if self._sensor_category == "tower":
            tower_index_formatted = f"{self._tower_index + 1:01d}"
            return f"byd_{hvs_serial}_{self._sensor_type}_{tower_index_formatted}"

        if self._sensor_category:
            return _cell_unique_id(
                hvs_serial,
                self._sensor_category,
                self._tower_index,
                self._module,
                self._reset_counter,
                self._num_digits,
            )

        return f"byd_{hvs_serial}_{self._sensor_type}"

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return self._icon

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._attr_native_unit_of_measurement

    @property
    def native_value(self):
        """Return the state of the sensor."""
        data = self.coordinator.data or {}
        towers = data.get("tower_attributes", [])

        if self._sensor_category == "cell_voltage":
            if self._tower_index < len(towers):
                tower = towers[self._tower_index]
                cell_voltages = tower.get("cell_voltages", [])
                if self._cell_index < len(cell_voltages):
                    return cell_voltages[self._cell_index]
            return None

        if self._sensor_category == "cell_temperature":
            if self._tower_index < len(towers):
                tower = towers[self._tower_index]
                cell_temperatures = tower.get("cell_temperatures", [])
                if self._cell_index < len(cell_temperatures):
                    return cell_temperatures[self._cell_index]
            return None

        if self._sensor_category == "tower":
            if self._tower_index < len(towers):
                tower = towers[self._tower_index]
                if isinstance(tower, dict):
                    return tower.get(self._sensor_type)
                _LOGGER.warning(
                    "Tower data malformed for sensor '%s' (tower %d): %s",
                    self._sensor_type,
                    self._tower_index,
                    tower,
                )
            return None

        return data.get(self._sensor_type)


class BYDModuleAggregateSensor(BYDBaseSensor):
    """Aggregated module-level sensor combining voltage and temperature data."""

    def __init__(
        self,
        coordinator,
        module_index,
        tower_index,
        battery,
    ):
        super().__init__(coordinator, battery)
        self._module_index = module_index
        self._tower_index = tower_index
        self._name = f"Tower {tower_index + 1} Module {module_index + 1}"
        self._icon = "mdi:battery"
        self._attr_native_unit_of_measurement = UnitOfElectricPotential.MILLIVOLT
        self._attr_device_class = SensorDeviceClass.VOLTAGE
        self._attr_suggested_display_precision = 0  # sum of integer mV

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"BYD {self._name}"

    @property
    def unique_id(self):
        """Return a unique ID for the aggregated module sensor."""
        hvs_serial = getattr(self._battery, "hvs_serial", "unknown")
        return f"byd_{hvs_serial}_tower{self._tower_index + 1}_module{self._module_index + 1}"

    def _module_values(self, category: str) -> list:
        """Return this module's current values from the coordinator data."""
        data = self.coordinator.data or {}
        towers = data.get("tower_attributes", [])
        if self._tower_index >= len(towers):
            return []
        tower = towers[self._tower_index]
        values = tower.get(CELL_CATEGORIES[category][0], [])
        values = values[: _plausible_cell_count(data, tower, category)]
        per_module = _per_module(data, category)
        start = self._module_index * per_module
        return values[start : start + per_module]

    @property
    def _voltages(self) -> list:
        return self._module_values("cell_voltage")

    @property
    def _temperatures(self) -> list:
        return self._module_values("cell_temperature")

    @property
    def native_value(self):
        """Return the total module voltage."""
        if not self._voltages:
            return None
        return round(sum(self._voltages), 2)

    @property
    def extra_state_attributes(self):
        """Return all per-cell voltages and temperatures as attributes."""
        attrs = {}
        if self._voltages:
            attrs["cell_voltages"] = self._voltages
            attrs["max_voltage"] = max(self._voltages)
            attrs["min_voltage"] = min(self._voltages)
            if len(self._voltages) > 0:
                attrs["avg_voltage"] = round(
                    sum(self._voltages) / len(self._voltages), 3
                )
        if self._temperatures:
            attrs["cell_temperatures"] = self._temperatures
            attrs["max_temperature"] = max(self._temperatures)
            attrs["min_temperature"] = min(self._temperatures)
            if len(self._temperatures) > 0:
                attrs["avg_temperature"] = round(
                    sum(self._temperatures) / len(self._temperatures), 3
                )
        return attrs

    @property
    def icon(self):
        """Return the icon."""
        return self._icon
