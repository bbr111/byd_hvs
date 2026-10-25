# BYD HVS/HMS/LVS Battery Integration for Home Assistant

[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Integration-blue)](https://www.home-assistant.io)

This custom integration allows you to monitor and interact with your BYD HVS Battery system through Home Assistant. It provides real-time data on battery status, cell voltages, temperatures, and more.

> [!IMPORTANT]
> **Updated to 0.4.14?** Some entities may show **"Disabled by device"** or now have a `_2` suffix in their entity ID (e.g. `sensor.byd_battery_temperature_2`), including cell voltage and cell temperature sensors. Please update to **0.4.15** or later, see [Upgrading from 0.4.14](#upgrading-from-0414).

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
  - [Manual Installation](#manual-installation)
  - [Installation via HACS](#installation-via-hacs)
- [Configuration](#configuration)
  - [Setup via the User Interface](#setup-via-the-user-interface)
  - [Options](#options)
- [Provided Sensors](#provided-sensors)
- [Firmware Update Check](#firmware-update-check)
- [Network / Privacy](#network--privacy)
- [Troubleshooting](#troubleshooting)
- [Upgrading from 0.4.14](#upgrading-from-0414)
- [Entity names and entity IDs](#entity-names-and-entity-ids)
- [Cleanup of Duplicate Entities](#cleanup-of-duplicate-entities)
- [Known Issues](#known-issues)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Real-Time Monitoring**: Access live data from your BYD HVS Battery system, including State of Charge (SOC), voltages, currents, and temperatures.
- **Cell-Level Details**: Monitor individual cell voltages and temperatures for detailed analysis.
- **Customizable Scan Interval**: Configure how frequently the integration polls data from the battery.
- **Error Handling**: Detailed error messages and robust handling of connection issues.
- **Firmware Update Check (optional)**: Two update entities show whether BYD offers newer BMU/BMS firmware. They are disabled by default; enabling them makes Home Assistant contact a BYD server once a day, see [Network / Privacy](#network--privacy).
- **Module Aggregation (new)**
  Each module is represented as a **single entity** containing all cell values as attributes:
  - **State:** Total summed module voltage (mV)
  - **Attributes:**
    - `cell_voltages`: list of all cell voltages
    - `cell_temperatures`: list of all cell temperatures
    - `max_voltage`, `min_voltage`, `avg_voltage`
    - `max_temperature`, `min_temperature`, `avg_temperature`

## Prerequisites

- **Home Assistant**: Ensure that Home Assistant is installed and running.
- **BYD HVS Battery System**: This integration is designed specifically for BYD HVS Battery systems with network connectivity.

## Installation

### Manual Installation

1. **Download the Integration**: Clone or download the contents of this repository.

2. **Copy to Custom Components**: Copy the `byd_hvs` directory into the `custom_components` directory of your Home Assistant installation:

   ```bash
   custom_components/
   └── byd_hvs/
       ├── __init__.py
       ├── config_flow.py
       ├── const.py
       ├── manifest.json
       ├── sensor.py
       └── translations/
           ├── de.json
           └── en.json
   ```

Restart Home Assistant: Restart Home Assistant to recognize the new integration.

### Installation via HACS

Install HACS: If you haven't already, install the Home Assistant Community Store (HACS).

Add Custom Repository:

In the Home Assistant UI, navigate to HACS.
Click on the Integrations tab.
Click the three dots in the top right corner and select Custom repositories.
Add the URL of this repository and select Integration as the category.
Install the Integration:

Search for BYD HVS Battery in HACS.
Click Install to add the integration.
Restart Home Assistant: Restart your Home Assistant instance.

## Configuration

### Setup via the User Interface

Add Integration:

In the Home Assistant UI, navigate to Settings > Devices & Services.
Click Add Integration.
Search for BYD HVS Battery and select it.
Enter Connection Details:

IP Address: Enter the IP address of your BYD HVS Battery system.
Port: Default is 8080. Change if your system uses a different port.
Scan Interval: Set the polling interval in seconds (minimum 10 seconds).
Complete Setup:

Click Submit to complete the setup.
If the connection is successful, the integration will be added, and the sensors will be available.

### Options

The integration offers several configuration options that can be adjusted at any time from the **Home Assistant UI**
(Settings → Devices & Services → BYD HVS Battery → Configure).

| **Option**                        | **Description**                                                                                                                                                                       | **Default** |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- |
| **Scan Interval (seconds)**       | Defines how often the integration polls the BYD HVS Battery for new data. The minimum recommended value is **10 seconds** to avoid overloading the system.                            | `10`        |
| **Show Cell Voltages**            | Enables detailed sensor entities for each **individual cell voltage**. Disable this if you prefer a cleaner setup or use the new aggregated module view.                              | `True`      |
| **Show Cell Temperatures**        | Enables detailed sensor entities for each **individual cell temperature**.                                                                                                            | `True`      |
| **Show Modules**                  | Adds the **module number** as part of the cell sensor names (e.g., “Tower 1 Module 2 Cell 05”). Helpful for identifying the module-to-cell mapping.                                   | `False`     |
| **Reset Cell Counter per Module** | Resets the internal cell numbering after each module. For example, Cell 01–Cell 08 will repeat for each module.                                                                       | `False`     |
| **Show Towers**                   | Displays **tower-level diagnostic sensors**, such as balancing status, max/min cell voltages, and temperature statistics. Disable this if you only need overall battery data.         | `True`      |
| **Aggregate Modules**             | Creates **one summarized entity per module** that includes all cell voltages and temperatures as attributes. Each aggregated entity shows the total module voltage as its main value. | `False`     |

#### 💡 Usage Tips

- For **detailed analysis**, keep **Show Cell Voltages** and **Show Cell Temperatures** enabled.
- For a **cleaner setup** with fewer entities, enable **Aggregate Modules** and disable the individual cell options.
- If you only want general system data (SOC, Power, etc.), disable **Show Towers** and **Aggregate Modules** entirely.

## Provided Sensors

The integration provides the following sensors:

- State of Charge (SOC)
- Battery Voltage
- Current
- Power
- Maximum Cell Voltage
- Minimum Cell Voltage
- Maximum Cell Temperature
- Minimum Cell Temperature
- Cell Voltages: Individual voltages for each cell.
- Cell Temperatures: Individual temperatures for each cell.
- Error Messages
- ETA (charge/discharge efficiency, total and per tower), shown with 1 decimal
- All numeric sensors come with a default display precision that matches the resolution delivered by the battery (e.g. cell voltages in whole mV, temperatures in whole °C, current 0.1 A). You can change it per entity in the entity settings.
- Tower Balancing Status: hex bitmask of the cells that are currently balancing (one bit per cell). It is a **diagnostic** entity and disabled by default for new installations; the Balancing Count sensor shows the number of balancing cells.

## Firmware Update Check

The integration provides two **update** entities on the battery device:

| Entity | Installed version | Latest version |
|---|---|---|
| `update.byd_bmu_firmware` (BYD Battery <serial> BMU Firmware) | BMU firmware read from the battery | newest BMU firmware offered by BYD |
| `update.byd_bms_firmware` (BYD Battery <serial> BMS Firmware) | BMS firmware read from the battery | newest BMS firmware offered by BYD |

- Both entities are **diagnostic** entities and **disabled by default**. Enable them under *Settings → Devices & Services → BYD HVS Battery → device → Entities* (show disabled entities). **Enabling an entity is the opt-in for the online check** described in [Network / Privacy](#network--privacy). While both entities are disabled, no request is sent.
- The installed version is shown without the flash bank suffix: `V3.31-B` is shown as `3.31`. `A`/`B` is the active firmware bank of the battery, not a different firmware.
- The latest version is taken from the firmware line that matches the installed one (`3.x` for HVS/HVM/HVL, `1.x` for LVS/LVL) and compared numerically.
- The firmware **cannot be installed from Home Assistant**. Updates are only possible with the BYD **Be Connect** app (or the Be Connect Plus PC tool) while connected to the battery.
- **Before updating**, ask your installer and check the community, e.g. the [BYD HVS Firmware-Update thread on photovoltaikforum.com](https://www.photovoltaikforum.com/thread/150898-byd-hvs-firmware-update/). Since BMS 3.31 there are reports of more aggressive cell balancing, and not every inverter manufacturer officially supports the newest firmware. BYD does not publish changelogs.
- If the BYD server cannot be reached, the last known version is kept (also across restarts) and a single warning is logged. If no version is known yet, the entity state is *unknown*.
- The attribute `last_check` shows the time of the last **successful** check (ISO timestamp in UTC). It is not updated by failed attempts.
- To check immediately instead of waiting for the daily check, call the action `homeassistant.update_entity` with `update.byd_bmu_firmware` or `update.byd_bms_firmware` as target (e.g. in *Developer tools → Actions*, a script or a dashboard button).
- Battery-Box HVS+/HVB are not covered (different firmware line).

## Network / Privacy

- **By default the integration only talks to your battery in your local network** (TCP, port 8080). Nothing is sent to the internet.
- **Only if you enable at least one firmware update entity** ([Firmware Update Check](#firmware-update-check)), Home Assistant additionally sends **one HTTPS request per day** (plus at most one after a restart if the last check is older than 24 hours, and one per manual check) to BYD:
  - `POST https://deapp.byd.com/api/V1/Http2/GetFileNewLink` with the fixed body `{"SoftVersion":"V1.0"}`
  - The response is the list of firmware files BYD offers for download. Only the version numbers are read; no firmware is downloaded.
  - **No serial number, no device data and no measurements are sent.** BYD can see the public IP address of your Home Assistant, as with any internet request.
- This is the server the BYD Be Connect apps use. It is **not an official, documented API**. BYD may change or remove it at any time; the entities then keep the last known version.
- To stop the online check, disable both firmware update entities again.

## Troubleshooting

### Common Issues and Solutions

1. Failed to Connect
   Symptoms: The integration cannot connect to the battery; error message "Failed to connect".
   Solution:
   Verify the IP address and port.
   Ensure the battery system is reachable over the network.
   Check firewall settings that might be blocking the connection.
2. Connection Timed Out
   Symptoms: Error message "Connection timed out".
   Solution:
   Check network stability.
   Ensure the battery system is powered on and responsive.
   Increase the scan interval to reduce network load if necessary.
3. Invalid Scan Interval
   Symptoms: Error message "Value is too low (minimum 10 seconds)" when setting the scan interval.
   Solution:
   Ensure the scan interval is set to 10 seconds or higher.
   Adjust the value in the options accordingly.
   Logging and Debugging
   To enable debug logging for this integration:

Update Configuration:

Add the following to your configuration.yaml:

yaml
Code kopieren
logger:
default: warning
logs:
custom_components.byd_hvs: debug
Restart Home Assistant: Restart your instance to apply the changes.

Check Logs: Review detailed logs in the Home Assistant log file.

## Upgrading from 0.4.14

The duplicate entity cleanup in 0.4.14 could keep an old, **disabled** entity and remove the working one ([#47](https://github.com/bbr111/byd_hvs/issues/47)). This happened if the old device "BYD Battery " without a serial number had been disabled. Affected entities, including cell voltage and cell temperature sensors, show **"Disabled by device"**, and some entity IDs got a `_2` suffix.

Update to **0.4.15** or later and restart Home Assistant:

- Affected entities are **re-enabled automatically** on startup (a warning in the log shows how many). Entities you disabled yourself stay disabled.
- The empty device "BYD Battery " without a serial number is removed.
- Entity IDs with a `_2` suffix are **not** renamed automatically. To reconnect dashboards, automations and history, rename them back manually: Settings → Devices & Services → Entities → select the entity → ⚙️ Settings → **Entity ID** (e.g. `sensor.byd_battery_temperature_2` → `sensor.byd_battery_temperature`).

## Entity names and entity IDs

Since Home Assistant 2026.4, entities of integrations that do not use the modern naming scheme get the device name in front of their name. This led to doubled names such as "BYD Battery P030… BYD Battery Temperature" and, for newly created entities, doubled entity IDs such as `sensor.byd_battery_byd_battery_temperature` or `sensor.byd_battery_p030…_byd_battery_temperature`.

The integration now uses the modern naming scheme:

- **Friendly names** are "<device name> <sensor name>", e.g. "BYD Battery P030… Temperature", "BYD Battery P030… Cell Voltage Tower 1 Cell 01". Names you set yourself are kept.
- **Entity IDs of existing entities do not change.** New entities get the historic scheme `sensor.byd_<name>`, e.g. `sensor.byd_battery_temperature`, `sensor.byd_cell_voltage_tower_1_cell_01`. A second battery gets Home Assistant's `_2` suffix.
- **Doubled entity IDs are repaired automatically** on startup: `sensor.byd_battery_byd_<name>` and `sensor.byd_battery_<serial>_byd_<name>` are renamed back to `sensor.byd_<name>` if that ID is free (the log shows a warning per renamed entity). Because the old history is still stored under the historic ID, it is connected again. Entity IDs you customized are never touched.

> [!WARNING]
> Automations, templates or cards that match entities by their **friendly name** (e.g. "BYD Battery Temperature") need to be updated. References by entity ID keep working.

## Cleanup of Duplicate Entities

Older versions could register sensors without the battery serial number (unique_id `byd__<sensor>`) when the battery was not reachable during startup, and register them again with the serial number after a later restart. This left orphaned duplicates behind; the newer entities usually got a `_2` suffix (e.g. `sensor.byd_state_of_charge_2`).

On startup, once the serial number is known, the integration now cleans these up automatically:

- Without a duplicate, the old entity is migrated to the new unique_id. Its entity_id, history and customizations are kept.
- If a duplicate with the serial number exists as well, the entity that still has the historic entity ID (`sensor.byd_<name>`, without `_2` suffix) is kept and the other one is removed. If neither has it, an enabled entity is preferred over a disabled one, and otherwise the entity with the serial number is kept (orphans created by Home Assistant 2026.4+ have doubled entity IDs and are not the originals). A warning in the log names the removed and the kept entity_id.

If automations, scripts or dashboards referenced the removed `_2` entity, update them to the original entity_id named in the log. The history recorded only on the `_2` entity is not carried over.

### Bogus cell temperature and module entities

Older versions could create far more cell temperature entities than the battery has (100+ instead of e.g. 8, 16 or 24) and too many module aggregate entities, see [#25](https://github.com/bbr111/byd_hvs/issues/25). On startup these are now cleaned up automatically:

- Entities for cells that really exist are migrated to the new unique_id (the index padding changes, e.g. `..._001` -> `..._01`). Their entity_id, history and customizations are kept. If an entity with the new unique_id already exists, the old one is kept and the duplicate is removed (since 0.4.15: unless the old one is disabled and the duplicate is enabled).
- Cell and module aggregate entities beyond the real number of cells/modules are removed. The log contains a warning with the number of removed entities.

## Known Issues

### Battery box resets its Ethernet link every minute without Internet access

If the BYD battery box (BMU/BMS) is blocked from accessing the Internet, its firmware drops the Ethernet link roughly every 60 seconds for about 20 seconds and then requests a new DHCP lease. This is behavior of the BYD firmware, not of this integration: it also happens with other tools (ioBroker, Be Connect) and regardless of the polling interval. See [#30](https://github.com/bbr111/byd_hvs/issues/30) and the [Photovoltaikforum thread](https://www.photovoltaikforum.com/thread/179268-byd-per-ethernet-in-lan-verbinden/?pageNo=4) (German).

The integration tolerates these interruptions: if a poll fails, the last known values are kept until the next successful update.

Workarounds reported by users:

- Allow outgoing connections from the battery box on ports 443 (HTTPS) and 1883 (MQTT); with these open the link stays stable.
- Instead of blocking the box completely in the firewall, block unwanted destinations via DNS (e.g. Pi-hole or AdGuard Home).

## Contributing

Contributions are welcome! Please follow these steps:

Fork the Repository: Create your own fork of the repository.

Create a Branch: Create a new branch for your changes.

bash
Code kopieren
git checkout -b feature/your-feature
Make Changes: Implement your feature or bug fix.

Run Linters and Tests: Ensure code quality by running linter tools.

bash
Code kopieren

### Run Ruff linter

`ruff check .`

### Run Pylint

`pylint custom_components/byd_hvs`

### Run any available tests

Commit Changes: Commit your changes with a descriptive message.

`git commit -m "Added feature: Description of your feature"`

Push to GitHub:
`git push origin feature/your-feature`

Create a Pull Request: Submit a pull request to the main repository.

## License

This project is licensed under the GNU General Public License v3.0. See the [LICENSE](LICENSE) file for details.
