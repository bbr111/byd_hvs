"""Sensor platform for the BYD HVS Battery integration."""

from datetime import timedelta
import logging

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
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import entity_registry as er
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
    num_modules = data.get("modules") or 0
    module_cell_count = data.get("module_cell_count") or 1
    module_cell_temp_count = data.get("module_cell_temp_count") or 1

    def _cell_count(tower: dict) -> int:
        return _plausible_count(
            len(tower.get("cell_voltages", [])),
            data.get("number_of_cells"),
            data.get("module_cell_count"),
            num_modules,
        )

    def _temp_count(tower: dict) -> int:
        return _plausible_count(
            len(tower.get("cell_temperatures", [])),
            data.get("number_of_temperatures"),
            data.get("module_cell_temp_count"),
            num_modules,
        )

    # Cell voltage sensors
    if show_cell_voltage:
        towers = coordinator.data.get("tower_attributes", [])
        for tower_index, tower in enumerate(towers):
            max_cell_index = _cell_count(tower)
            if max_cell_index >= 100:
                num_digits = 3
            else:
                num_digits = 2

            if show_reset_counter:
                num_digits = 2

            counter = 0
            for cell_index in range(max_cell_index):
                module_no = 0
                counter += 1
                cell_no = cell_index + 1
                if show_reset_counter and counter > module_cell_count:
                    counter = 1

                if show_modules:
                    module_no = cell_index // module_cell_count + 1
                    cell_no = f"{module_no}_{counter}"

                sensors.append(
                    BYDBatterySensor(
                        coordinator,
                        f"cell_voltage_{tower_index + 1}_{cell_no}",
                        byd_hvs,
                        tower_index,
                        cell_index,
                        "cell_voltage",
                        num_digits,
                        module_no,
                        counter,
                    )
                )

    # Cell temperature sensors

    if show_cell_temperature:
        towers = coordinator.data.get("tower_attributes", [])
        for tower_index, tower in enumerate(towers):
            counter = 0
            max_cell_index = _temp_count(tower)
            if max_cell_index >= 100:
                num_digits = 3
            else:
                num_digits = 2

            if show_reset_counter:
                num_digits = 2

            for cell_index in range(max_cell_index):
                module_no = 0
                counter += 1
                cell_no = cell_index + 1
                if show_reset_counter and counter > module_cell_temp_count:
                    counter = 1
                if show_modules:
                    module_no = cell_index // module_cell_temp_count + 1
                    cell_no = f"{module_no}_{counter}"

                sensors.append(
                    BYDBatterySensor(
                        coordinator,
                        f"cell_temperature_{tower_index + 1}_{cell_no}",
                        byd_hvs,
                        tower_index,
                        cell_index,
                        "cell_temperature",
                        num_digits,
                        module_no,
                        counter,
                    )
                )

    if aggregate_modules:
        _LOGGER.debug(
            "Aggregate enabled: %s | Towers found: %s",
            aggregate_modules,
            len(coordinator.data.get("tower_attributes", [])),
        )
        towers = coordinator.data.get("tower_attributes", [])

        for tower_index, tower in enumerate(towers):
            cell_voltages = tower.get("cell_voltages", [])[: _cell_count(tower)]
            cell_temps = tower.get("cell_temperatures", [])[: _temp_count(tower)]
            # Use the module count reported by the BMU; only derive it from
            # the list lengths if the library did not report one.
            tower_modules = num_modules or max(
                len(cell_voltages) // module_cell_count,
                len(cell_temps) // module_cell_temp_count,
                1,
            )

            for module_index in range(tower_modules):
                start_v = module_index * module_cell_count
                end_v = start_v + module_cell_count
                module_voltages = cell_voltages[start_v:end_v]

                start_t = module_index * module_cell_temp_count
                end_t = start_t + module_cell_temp_count
                module_temps = cell_temps[start_t:end_t]

                if not module_voltages and not module_temps:
                    continue

                sensors.append(
                    BYDModuleAggregateSensor(
                        coordinator,
                        module_index,
                        tower_index,
                        byd_hvs,
                        module_voltages,
                        module_temps,
                    )
                )

    async_add_entities(sensors)


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

    for entry in er.async_entries_for_config_entry(ent_reg, config_entry.entry_id):
        if not entry.unique_id.startswith(ORPHAN_UNIQUE_ID_PREFIX):
            continue

        new_unique_id = new_prefix + entry.unique_id[len(ORPHAN_UNIQUE_ID_PREFIX) :]
        existing_entity_id = ent_reg.async_get_entity_id(
            entry.domain, DOMAIN, new_unique_id
        )

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
        ent_reg.async_update_entity(entry.entity_id, new_unique_id=new_unique_id)


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
            # Format tower index as needed (assuming towers are less than 10)
            tower_index_formatted = f"{self._tower_index + 1:01d}"
            return f"byd_{hvs_serial}_{self._sensor_category}_{tower_index_formatted}_{self._module}_{self._cell_index_formatted}"

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
        voltages,
        temperatures,
    ):
        super().__init__(coordinator, battery)
        self._module_index = module_index
        self._tower_index = tower_index
        self._voltages = voltages or []
        self._temperatures = temperatures or []
        self._name = f"Tower {tower_index + 1} Module {module_index + 1}"
        self._icon = "mdi:battery"
        self._attr_native_unit_of_measurement = UnitOfElectricPotential.MILLIVOLT
        self._attr_device_class = SensorDeviceClass.VOLTAGE

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"BYD {self._name}"

    @property
    def unique_id(self):
        """Return a unique ID for the aggregated module sensor."""
        hvs_serial = getattr(self._battery, "hvs_serial", "unknown")
        return f"byd_{hvs_serial}_tower{self._tower_index + 1}_module{self._module_index + 1}"

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
