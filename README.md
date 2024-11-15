# BYD HVS/HMS/LVS Battery Integration for Home Assistant

[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Integration-blue)](https://www.home-assistant.io)

This custom integration allows you to monitor and interact with your BYD HVS Battery system through Home Assistant. It provides real-time data on battery status, cell voltages, temperatures, and more.

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
- [Troubleshooting](#troubleshooting)
- [Known Issues](#known-issues)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Real-Time Monitoring**: Access live data from your BYD HVS Battery system, including State of Charge (SOC), voltages, currents, and temperatures.
- **Cell-Level Details**: Monitor individual cell voltages and temperatures for detailed analysis.
- **Customizable Scan Interval**: Configure how frequently the integration polls data from the battery.
- **Error Handling**: Detailed error messages and robust handling of connection issues.

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
       ├── bydhvs.py
       ├── config_flow.py
       ├── const.py
       ├── manifest.json
       ├── sensor.py
       └── translations/
           ├── de.json
           └── en.json

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
You can adjust the scan interval after setup:

Access Options:

Go to Settings > Devices & Services.
Find the BYD HVS Battery integration and click Configure.
Adjust Scan Interval:

Enter a new value for the scan interval (minimum 10 seconds).
Click Submit to save the changes.

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

## Known Issues

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
```ruff check .```

### Run Pylint
```pylint custom_components/byd_hvs```

### Run any available tests
Commit Changes: Commit your changes with a descriptive message.



```git commit -m "Added feature: Description of your feature"```

Push to GitHub:
```git push origin feature/your-feature```

Create a Pull Request: Submit a pull request to the main repository.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.


