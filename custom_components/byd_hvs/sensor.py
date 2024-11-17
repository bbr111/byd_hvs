"""Sensor platform for the BYD HVS Battery integration."""

from datetime import timedelta  # type: ignore  # noqa: PGH003
import logging

import bydhvs

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
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
)

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    "soc": ["State of Charge", "mdi:battery", "%", None],
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
    "soh": ["State of Health", "mdi:heart-pulse", "%", None],
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
    "charge_total": ["Charge Total", "mdi:battery-charging", "Ah", None],
    "discharge_total": ["Discharge Total", "mdi:battery-charging", "Ah", None],
    "eta": ["ETA", "mdi:timer", "%", None],
    "battery_type_from_serial": [
        "Battery Type From Serial",
        "mdi:information-outline",
        None,
        None,
    ],
    "battery_type": ["Battery Type", "mdi:information-outline", None, None],
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
    "charge_total": ["Charge Total", "mdi:battery-charging", "Ah", None],
    "discharge_total": ["Discharge Total", "mdi:battery-charging", "Ah", None],
    "eta": ["ETA", "mdi:timer", "%", None],
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
    "hvs_soc_diagnosis": ["SOC Diagnosis", "mdi:battery", "%", None],
    "soh": ["State of Health", "mdi:heart-pulse", "%", None],
    "state": ["State", "mdi:information-outline", None, None],
    "state_string": ["State String", "mdi:information-outline", None, None],
}


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

    byd_hvs = bydhvs.BYDHVS(ip_address, port)

    async def async_update_data():
        """Fetch data from the BYD HVS battery."""
        _LOGGER.debug("Starting data retrieval from the BYD HVS Battery")

        def validate_data(data):
            """Validate the retrieved data."""
            if not data:
                raise UpdateFailed("No data received")

        try:
            await byd_hvs.poll()
            data = byd_hvs.get_data()
            validate_data(data)
        except ConnectionError as e:
            _LOGGER.error("Connection error: %s", e)
            raise UpdateFailed(f"Connection error: {e}") from e
        except TimeoutError as e:
            _LOGGER.error("Timeout error: %s", e)
            raise UpdateFailed(f"Timeout error: {e}") from e
        else:
            _LOGGER.debug("Data retrieval successfully completed")
            return data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="BYD HVS Battery",
        update_method=async_update_data,
        update_interval=timedelta(seconds=scan_interval),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][config_entry.entry_id]["coordinator"] = coordinator

    sensors = []

    # General sensors
    sensors.extend(
        [
            BYDBatterySensor(coordinator, sensor_type, byd_hvs)
            for sensor_type in SENSOR_TYPES
        ]
    )

    towers = coordinator.data.get("tower_attributes", [])
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

    # Cell voltage sensors
    if show_cell_voltage:
        towers = coordinator.data.get("tower_attributes", [])
        module_cell_count = coordinator.data.get("module_cell_count", 1)
        for tower_index, tower in enumerate(towers):
            cell_voltages = tower.get("cell_voltages", [])
            max_cell_index = len(cell_voltages)
            if max_cell_index >= 100:
                num_digits = 3
            else:
                num_digits = 2

            if show_reset_counter:
                num_digits = 2

            counter = 0
            for cell_index in range(len(cell_voltages)):
                module_no = 0
                counter += 1
                cell_no = cell_index + 1
                if show_reset_counter and counter > module_cell_count:
                    counter = 1

                if show_modules:
                    module_no = cell_index // module_cell_count + 1
                    cell_no = f"{module_no}_{counter}"

                sensors.extend(
                    [
                        BYDBatterySensor(
                            coordinator,
                            f"cell_voltage_{tower_index+1}_{cell_no}",
                            byd_hvs,
                            tower_index,
                            cell_index,
                            "cell_voltage",
                            num_digits,
                            module_no,
                            counter,
                        )
                    ]
                )

    # Cell temperature sensors

    if show_cell_temperature:
        towers = coordinator.data.get("tower_attributes", [])
        module_cell_temp_count = coordinator.data.get("module_cell_temp_count", 1)
        counter = 0
        for tower_index, tower in enumerate(towers):
            cell_temperatures = tower.get("cell_temperatures", [])
            max_cell_index = len(cell_temperatures)
            if max_cell_index >= 100:
                num_digits = 3
            else:
                num_digits = 2

            if show_reset_counter:
                num_digits = 2

            for cell_index in range(len(cell_temperatures)):
                module_no = 0
                counter += 1
                cell_no = cell_index + 1
                if show_reset_counter and counter > module_cell_temp_count:
                    counter = 1
                if show_modules:
                    module_no = cell_index // module_cell_temp_count + 1
                    cell_no = f"{module_no}_{counter}"

                sensors.extend(
                    [
                        BYDBatterySensor(
                            coordinator,
                            f"cell_temperature_{tower_index+1}_{cell_no}",
                            byd_hvs,
                            tower_index,
                            cell_index,
                            "cell_temperature",
                            num_digits,
                            module_no,
                            counter,
                        )
                    ]
                )

    async_add_entities(sensors)


class BYDBatterySensor(CoordinatorEntity, SensorEntity):
    """Representation of a BYD HVS Battery sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        sensor_type: str,
        battery: bydhvs.BYDHVS,
        tower_index=None,
        cell_index=None,
        sensor_category=None,
        num_digits: int = 2,
        module: int = 0,
        reset_counter: int = 0,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator)
        self._battery = battery
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
            self._name = f"""Cell Voltage Tower {tower_index+1}{
                module_no} Cell {cell_index_formatted}"""
            self._icon = "mdi:current-dc"
            self._attr_native_unit_of_measurement = UnitOfElectricPotential.MILLIVOLT
            self._attr_device_class = SensorDeviceClass.VOLTAGE
        elif sensor_category == "cell_temperature":
            cell_index_formatted = f"{self._reset_counter:0{self._num_digits}d}"
            self._cell_index_formatted = cell_index_formatted
            if self._module > 0:
                module_no = f" Module {self._module}"
            self._name = f"""Cell Temperature Tower {tower_index+1}{
                module_no} Cell {cell_index_formatted}"""
            self._icon = "mdi:thermometer"
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
        elif sensor_category == "tower":
            self._name = f"Tower {tower_index+1} {TOWER_SENSOR_TYPES[sensor_type][0]}"
            self._icon = TOWER_SENSOR_TYPES[sensor_type][1]
            self._attr_native_unit_of_measurement = TOWER_SENSOR_TYPES[sensor_type][2]
            self._attr_device_class = TOWER_SENSOR_TYPES[sensor_type][3]
        else:
            self._name = SENSOR_TYPES[sensor_type][0]
            self._icon = SENSOR_TYPES[sensor_type][1]
            self._attr_native_unit_of_measurement = SENSOR_TYPES[sensor_type][2]
            self._attr_device_class = SENSOR_TYPES[sensor_type][3]

        if self._attr_device_class in (
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
            tower_index_formatted = f"{self._tower_index+1:01d}"
            return f"byd_{hvs_serial}_{self._sensor_type}_{tower_index_formatted}"

        if self._sensor_category:
            # Format tower index as needed (assuming towers are less than 10)
            tower_index_formatted = f"{self._tower_index+1:01d}"
            return (
                f"byd_{hvs_serial}_{self._sensor_category}_"
                f"""{tower_index_formatted}_{self._module}_{
                    self._cell_index_formatted}"""
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
        data = self.coordinator.data
        towers = data.get("tower_attributes", [])
        if self._sensor_category == "cell_voltage" and self._tower_index < len(towers):
            tower = towers[self._tower_index]
            cell_voltages = tower.get("cell_voltages", [])
            if self._cell_index < len(cell_voltages):
                return cell_voltages[self._cell_index]
        elif self._sensor_category == "cell_temperature" and self._tower_index < len(
            towers
        ):
            tower = towers[self._tower_index]
            cell_temperatures = tower.get("cell_temperatures", [])
            if self._cell_index < len(cell_temperatures):
                return cell_temperatures[self._cell_index]
        elif self._sensor_category == "tower" and self._tower_index < len(towers):
            tower = towers[self._tower_index]
            return tower[self._sensor_type]
        elif self._sensor_type in data:
            return data[self._sensor_type]
        return None

    @property
    def device_info(self):
        """Return device information about this BYD battery."""
        return {
            "identifiers": {(DOMAIN, self._battery.hvs_serial)},
            "name": f"BYD Battery {self._battery.hvs_serial}",
            "manufacturer": "BYD",
            "model": self._battery.hvs_batt_type_from_serial,
            "sw_version": self._battery.hvs_bms,
        }
