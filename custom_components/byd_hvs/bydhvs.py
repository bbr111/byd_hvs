"""Module for communicating with the BYD HVS Battery system.

This module provides the BYDHVS class, which handles communication with
the BYD HVS Battery over TCP/IP sockets. It implements methods to connect
to the battery, send requests, receive and parse responses, and retrieve
data for use in Home Assistant.
"""

import asyncio
import logging

_LOGGER = logging.getLogger(__name__)


class BYDHVSError(Exception):
    """Base exception for BYD HVS Battery errors."""


class BYDHVSConnectionError(BYDHVSError):
    """Exception raised when there is a connection error."""


class BYDHVSTimeoutError(BYDHVSError):
    """Exception raised when a timeout occurs during communication."""


class BYDHVS:
    """Class to communicate with the BYD HVS Battery system."""

    def __init__(self, ip_address: str, port: int = 8080) -> None:
        """Initialize the BYDHVS communication class."""
        self.ip_address = ip_address
        self.port = port
        self.reader = None
        self.writer = None
        self.myState = 0
        self.hvsSOC = None
        self.hvsMaxVolt = None
        self.hvsMinVolt = None
        self.hvsSOH = None
        self.hvsSerial = ""
        self.hvsBMU = ""
        self.hvsBMUA = ""
        self.hvsBMUB = ""
        self.hvsBMS = ""
        self.hvsModules = 0
        self.hvsTowers = 0
        self.hvsGrid = ""
        self.hvsA = 0
        self.hvsBattVolt = 0
        self.hvsMaxTemp = 0
        self.hvsMinTemp = 0
        self.hvsBatTemp = 0
        self.hvsError = 0
        self.hvsParamT = ""
        self.hvsOutVolt = 0
        self.hvsPower = 0
        self.hvsDiffVolt = 0
        self.hvsErrorString = ""
        self.hvsChargeTotal = 0
        self.hvsDischargeTotal = 0
        self.hvsETA = 0
        self.hvsBattType_fromSerial = ""
        self.hvsBattType = ""
        self.hvsInvType = ""
        self.hvsNumCells = 0
        self.hvsNumTemps = 0
        self.towerAttributes = [{}]
        self.myNumberforDetails = 0
        self.FirstRun = True
        self.cellVoltages = []
        self.cellTemperatures = []
        self.balancingStatus = ""
        self.balancingCount = 0
        self.hvsInvType_String = ""
        self.maxCellVoltage_mV = 0
        self.minCellVoltage_mV = 0
        self.maxCellVoltageCell = 0
        self.minCellVoltageCell = 0
        self.maxCellTempCell = 0
        self.minCellTempCell = 0

        # Initialize the requests
        self.myRequests = [
            bytes.fromhex("010300000066c5e0"),  # 0
            bytes.fromhex("01030500001984cc"),  # 1
            bytes.fromhex("010300100003040e"),  # 2
            bytes.fromhex("0110055000020400018100f853"),  # 3 Start measurement
            bytes.fromhex("010305510001d517"),  # 4
            bytes.fromhex("01030558004104e5"),  # 5
            bytes.fromhex("01030558004104e5"),  # 6
            bytes.fromhex("01030558004104e5"),  # 7
            bytes.fromhex("01030558004104e5"),  # 8
            # Switching for more than 4 modules
            bytes.fromhex("01100100000306444542554700176f"),  # 9 Switch to second pass
            bytes.fromhex(
                "0110055000020400018100f853"
            ),  # 10 Start measurement of remaining cells
            bytes.fromhex("010305510001d517"),  # 11
            bytes.fromhex("01030558004104e5"),  # 12
            bytes.fromhex("01030558004104e5"),  # 13
            bytes.fromhex("01030558004104e5"),  # 14
            bytes.fromhex("01030558004104e5"),  # 15
            bytes.fromhex("01100550000204000281000853"),  # 16 - Switch to Box 2
        ]

        self.myErrors = [
            "High temperature during charging (cells)",
            "Low temperature during charging (cells)",
            "Overcurrent during discharging",
            "Overcurrent during charging",
            "Main circuit failure",
            "Short circuit alarm",
            "Cell imbalance",
            "Current sensor error",
            "Battery overvoltage",
            "Battery undervoltage",
            "Cell overvoltage",
            "Cell undervoltage",
            "Voltage sensor error",
            "Temperature sensor error",
            "High temperature during discharging (cells)",
            "Low temperature during discharging (cells)",
        ]

        self.myINVs = [
            "Fronius HV",  # 0
            "Goodwe HV",  # 1
            "Fronius HV",  # 2
            "Kostal HV",  # 3
            "Goodwe HV",  # 4
            "SMA SBS3.7/5.0",  # 5
            "Kostal HV",  # 6
            "SMA SBS3.7/5.0",  # 7
            "Sungrow HV",  # 8
            "Sungrow HV",  # 9
            "Kaco HV",  # 10
            "Kaco HV",  # 11
            "Ingeteam HV",  # 12
            "Ingeteam HV",  # 13
            "SMA SBS 2.5 HV",  # 14
            "undefined",  # 15
            "SMA SBS 2.5 HV",  # 16
            "Fronius HV",  # 17
            "undefined",  # 18
            "SMA STP",  # 19
        ]

    async def connect(self) -> None:
        """Establish a connection to the battery."""
        try:
            reader, writer = await asyncio.open_connection(self.ip_address, self.port)
            self.reader = reader
            self.writer = writer
            _LOGGER.debug("Connected to %s:%s", self.ip_address, self.port)
            self.myState = 2  # Next state
        except TimeoutError as e:
            _LOGGER.error(
                "Timeout connecting to %s:%s - %s", self.ip_address, self.port, e
            )
            raise BYDHVSTimeoutError(
                f"Timeout connecting to {self.ip_address}:{self.port}"
            ) from e
        except OSError as e:
            _LOGGER.error(
                "OS error connecting to %s:%s - %s", self.ip_address, self.port, e
            )
            raise BYDHVSConnectionError(
                f"OS error connecting to {self.ip_address}:{self.port}"
            ) from e

    async def send_request(self, request: bytes) -> None:
        """Send a request to the battery."""
        if self.writer:
            try:
                self.writer.write(request)
                await self.writer.drain()
            except (ConnectionResetError, BrokenPipeError, OSError) as e:
                _LOGGER.error("Error sending data: %s", e)
                self.myState = 0
            else:
                _LOGGER.debug("Sent: %s", request.hex())
        else:
            _LOGGER.error("No connection available")

    async def receive_response(self) -> bytes:
        """Receive a response from the battery."""
        if self.reader:
            try:
                data = await self.reader.read(1024)
            except TimeoutError:
                _LOGGER.error("Socket timeout")
                self.myState = 0
            except asyncio.IncompleteReadError as e:
                _LOGGER.error("Incomplete read error: %s", e)
                self.myState = 0
            except (ConnectionResetError, OSError) as e:
                _LOGGER.error("Error receiving data: %s", e)
                self.myState = 0
            else:
                _LOGGER.debug("Received: %s", data.hex())
                return data
        else:
            _LOGGER.error("No connection available")
        return None

    def crc16_modbus(self, data: bytes) -> int:
        """Calculate the Modbus CRC16 of the given data."""
        crc = 0xFFFF
        for pos in data:
            crc ^= pos
            for _ in range(8):
                if crc & 1:
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        return crc

    def check_packet(self, data: bytes) -> bool:
        """Check if the received packet is valid."""
        if len(data) < 5:
            return False
        if data[0] != 1:
            return False
        function_code = data[1]
        data_length = data[2]
        packet_length = data_length + 5  # 3 Header, 2 CRC
        if function_code == 3:
            if packet_length != len(data):
                return False
        elif function_code != 16:
            return False
        crc = self.crc16_modbus(data)
        return crc == 0

    def buf2int16SI(self, data: bytes, pos: int) -> int:
        """Convert buffer to signed 16-bit integer."""
        result = data[pos] * 256 + data[pos + 1]
        if result > 32768:
            result -= 65536
        return result

    def buf2int16US(self, data: bytes, pos: int) -> int:
        """Convert buffer to unsigned 16-bit integer."""
        return data[pos] * 256 + data[pos + 1]

    def buf2int32US(self, data: bytes, pos: int) -> int:
        """Convert buffer to unsigned 32-bit integer."""
        return (
            data[pos + 2] * 16777216
            + data[pos + 3] * 65536
            + data[pos] * 256
            + data[pos + 1]
        )

    def parse_packet0(self, data: bytes) -> None:
        """Parse packet 0 containing serial number and firmware versions."""
        byteArray = data
        # Serial number
        hvsSerial = ""
        for i in range(3, 22):
            hvsSerial += chr(byteArray[i])
        self.hvsSerial = hvsSerial.strip()

        # Hardware type
        if byteArray[5] == 51:
            self.hvsBattType_fromSerial = "HVS"
        if byteArray[5] == 50:
            self.hvsBattType_fromSerial = "LVS"
        if byteArray[5] == 49:
            self.hvsBattType_fromSerial = "LVS"

        # Firmware versions
        hvsBMUA = "V" + str(byteArray[27]) + "." + str(byteArray[28])
        hvsBMUB = "V" + str(byteArray[29]) + "." + str(byteArray[30])
        if byteArray[33] == 0:
            hvsBMU = hvsBMUA + "-A"
        else:
            hvsBMU = hvsBMUB + "-B"
        hvsBMS = (
            "V"
            + str(byteArray[31])
            + "."
            + str(byteArray[32])
            + "-"
            + chr(byteArray[34] + 65)
        )
        self.hvsBMU = hvsBMU
        self.hvsBMUA = hvsBMUA
        self.hvsBMUB = hvsBMUB
        self.hvsBMS = hvsBMS

        # Number of towers and modules
        hvsModules = byteArray[36] % 16
        hvsTowers = byteArray[36] // 16
        self.hvsModules = hvsModules
        self.hvsTowers = hvsTowers

        # Grid type
        if byteArray[38] == 0:
            self.hvsGrid = "OffGrid"
        elif byteArray[38] == 1:
            self.hvsGrid = "OnGrid"
        elif byteArray[38] == 2:
            self.hvsGrid = "Backup"
        else:
            self.hvsGrid = "Unknown"

    def parse_packet1(self, data: bytes) -> None:
        """Parse packet 1 containing battery status information."""
        byteArray = data
        hvsSOC = self.buf2int16SI(byteArray, 3)
        hvsMaxVolt = round(self.buf2int16SI(byteArray, 5) * 1.0 / 100.0, 2)
        hvsMinVolt = round(self.buf2int16SI(byteArray, 7) * 1.0 / 100.0, 2)
        hvsSOH = self.buf2int16SI(byteArray, 9)
        hvsA = round(self.buf2int16SI(byteArray, 11) * 1.0 / 10.0, 1)
        hvsBattVolt = round(self.buf2int16US(byteArray, 13) * 1.0 / 100.0, 1)
        hvsMaxTemp = self.buf2int16SI(byteArray, 15)
        hvsMinTemp = self.buf2int16SI(byteArray, 17)
        hvsBatTemp = self.buf2int16SI(byteArray, 19)
        hvsError = self.buf2int16SI(byteArray, 29)
        hvsParamT = str(byteArray[31]) + "." + str(byteArray[32])
        hvsOutVolt = round(self.buf2int16US(byteArray, 35) * 1.0 / 100.0, 1)
        hvsPower = round(hvsA * hvsOutVolt, 2)
        hvsDiffVolt = round(hvsMaxVolt - hvsMinVolt, 2)
        hvsErrorString = ""

        for j in range(16):
            if ((1 << j) & hvsError) != 0:
                if len(hvsErrorString) > 0:
                    hvsErrorString += "; "
                hvsErrorString += self.myErrors[j]
        if len(hvsErrorString) == 0:
            hvsErrorString = "No Error"

        hvsChargeTotal = self.buf2int32US(byteArray, 37) / 10
        hvsDischargeTotal = self.buf2int32US(byteArray, 41) / 10
        hvsETA = hvsDischargeTotal / hvsChargeTotal if hvsChargeTotal != 0 else 0

        # Store variables
        self.hvsSOC = hvsSOC
        self.hvsMaxVolt = hvsMaxVolt
        self.hvsMinVolt = hvsMinVolt
        self.hvsSOH = hvsSOH
        self.hvsA = hvsA
        self.hvsBattVolt = hvsBattVolt
        self.hvsMaxTemp = hvsMaxTemp
        self.hvsMinTemp = hvsMinTemp
        self.hvsBatTemp = hvsBatTemp
        self.hvsError = hvsError
        self.hvsParamT = hvsParamT
        self.hvsOutVolt = hvsOutVolt
        self.hvsPower = hvsPower
        self.hvsDiffVolt = hvsDiffVolt
        self.hvsErrorString = hvsErrorString
        self.hvsChargeTotal = hvsChargeTotal
        self.hvsDischargeTotal = hvsDischargeTotal
        self.hvsETA = hvsETA

    def parse_packet2(self, data: bytes) -> None:
        """Parse packet 2 containing battery type and inverter information."""
        byteArray = data
        self.hvsBattType = byteArray[5]
        self.hvsInvType = byteArray[3]
        if self.hvsBattType == 0:  # HVL
            self.hvsNumCells = 0
            self.hvsNumTemps = 0
        elif self.hvsBattType == 1:  # HVM
            self.hvsNumCells = self.hvsModules * 16
            self.hvsNumTemps = self.hvsModules * 8
        elif self.hvsBattType == 2:  # HVS
            self.hvsNumCells = self.hvsModules * 32
            self.hvsNumTemps = self.hvsModules * 12
        else:
            self.hvsNumCells = 0
            self.hvsNumTemps = 0

        if self.hvsBattType_fromSerial == "LVS":
            self.hvsBattType = "LVS"
            self.hvsNumCells = self.hvsModules * 7
            self.hvsNumTemps = 0

        if self.hvsBattType_fromSerial == "LVS":
            if self.hvsInvType < len(self.myINVs):
                self.hvsInvType_String = self.myINVs[self.hvsInvType]
            else:
                self.hvsInvType_String = "undefined"
        elif self.hvsInvType < len(self.myINVs):
            self.hvsInvType_String = self.myINVs[self.hvsInvType]
        else:
            self.hvsInvType_String = "undefined"

        self.hvsNumCells = min(self.hvsNumCells, 160)
        self.hvsNumTemps = min(self.hvsNumTemps, 64)

        _LOGGER.debug(
            "Number of cells: %s, Number of temperatures: %s, Modules: %s",
            self.hvsNumCells,
            self.hvsNumTemps,
            self.hvsModules,
        )

    def parse_packet5(self, data: bytes) -> None:
        """Parse packet 5 containing cell voltage and balancing status.

        Args:
            data (bytes): The received data packet.

        """
        byteArray = data
        self.maxCellVoltage_mV = self.buf2int16SI(byteArray, 5)
        self.minCellVoltage_mV = self.buf2int16SI(byteArray, 7)
        self.maxCellVoltageCell = byteArray[9]
        self.minCellVoltageCell = byteArray[10]
        self.maxCellTempCell = byteArray[15]
        self.minCellTempCell = byteArray[16]

        # Balancing flags (Bytes 17 to 32)
        self.balancingStatus = data[17:33].hex()
        self.balancingCount = self.count_set_bits(self.balancingStatus)

        # Cell voltages (Bytes 101 to 132) for cells 1 to 16
        self.cellVoltages = []
        for i in range(16):
            voltage = self.buf2int16SI(byteArray, 101 + i * 2)
            self.cellVoltages.append(voltage)

    def parse_packet6(self, data: bytes) -> None:
        """Parse packet 6 containing additional cell voltages.

        Args:
            data (bytes): The received data packet.

        """
        byteArray = data
        # Voltages for cells 17 and above
        max_cells = min(self.hvsNumCells - 16, 64)  # Maximum 64 cells in this packet
        for i in range(max_cells):
            voltage = self.buf2int16SI(byteArray, 5 + i * 2)
            self.cellVoltages.append(voltage)

    def parse_packet7(self, data: bytes) -> None:
        """Parse packet 7 containing more cell voltages and temperatures.

        Args:
            data (bytes): The received data packet.

        """
        byteArray = data
        # Voltages for cells 81 and above
        max_cells = min(self.hvsNumCells - 80, 48)  # Maximum 48 cells in this packet
        for i in range(max_cells):
            voltage = self.buf2int16SI(byteArray, 5 + i * 2)
            self.cellVoltages.append(voltage)

        # Temperatures for cells 1 to 30 (Bytes 103 to 132)
        self.cellTemperatures = []
        max_temps = min(self.hvsNumTemps, 30)
        for i in range(max_temps):
            temp = byteArray[103 + i]
            self.cellTemperatures.append(temp)

    def parse_packet8(self, data: bytes) -> None:
        """Parse packet 8 containing additional cell temperatures.

        Args:
            data (bytes): The received data packet.

        """
        byteArray = data
        # Temperatures for cells 31 and above (Bytes starting from 5)
        max_temps = min(self.hvsNumTemps - 30, 34)
        for i in range(max_temps):
            temp = byteArray[5 + i]
            self.cellTemperatures.append(temp)

    def count_set_bits(self, hex_string: str) -> int:
        """Count the number of set bits in a hex string.

        Args:
            hex_string (str): The hex string to analyze.

        Returns:
            int: The number of bits set to 1.

        """
        binary_string = bin(int(hex_string, 16))[2:]
        return binary_string.count("1")

    async def close(self) -> None:
        """Close the connection to the battery."""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
            self.reader = None
            self.writer = None
            _LOGGER.debug("Connection closed")

    async def poll(self) -> None:
        """Perform a polling cycle to retrieve data from the battery."""
        if self.myState != 0:
            _LOGGER.warning("Already polling")
            return
        self.myState = 1
        await self.connect()
        if self.myState == 0:
            return  # Connection failed

        # Initialize tower attributes
        self.towerAttributes = [{} for _ in range(1)]  # Adjust for multiple towers

        # State 2: Send request 0
        await self.send_request(self.myRequests[0])
        data = await self.receive_response()
        if data and self.check_packet(data):
            self.parse_packet0(data)
            self.myState = 3
        else:
            _LOGGER.error("Invalid or no data received in state 2")
            self.myState = 0
            await self.close()
            return

        # State 3: Send request 1
        await self.send_request(self.myRequests[1])
        data = await self.receive_response()
        if data and self.check_packet(data):
            self.parse_packet1(data)
            self.myState = 4
        else:
            _LOGGER.error("Invalid or no data received in state 3")
            self.myState = 0
            await self.close()
            return

        # State 4: Send request 2
        await self.send_request(self.myRequests[2])
        data = await self.receive_response()
        if data and self.check_packet(data):
            self.parse_packet2(data)
            # Decide whether to continue with detailed query
            if self.hvsNumCells > 0 and self.hvsNumTemps > 0:
                self.myState = 5
            else:
                self.myState = 0  # End polling if no detailed data available
        else:
            _LOGGER.error("Invalid or no data received in state 4")
            self.myState = 0
            await self.close()
            return

        # Continue with detailed query
        if self.myState == 5:
            # State 5: Start measurement
            await self.send_request(self.myRequests[3])
            data = await self.receive_response()
            if data and self.check_packet(data):
                # Wait time as per original code (e.g., 8 seconds)
                await asyncio.sleep(8)
                self.myState = 6
            else:
                _LOGGER.error("Invalid or no data received in state 5")
                self.myState = 0
                await self.close()
                return

            # State 6: Send request 4
            await self.send_request(self.myRequests[4])
            data = await self.receive_response()
            if data and self.check_packet(data):
                self.myState = 7
            else:
                _LOGGER.error("Invalid or no data received in state 6")
                self.myState = 0
                await self.close()
                return

            # State 7: Send request 5 and parse with parse_packet5
            await self.send_request(self.myRequests[5])
            data = await self.receive_response()
            if data and self.check_packet(data):
                self.parse_packet5(data)
                self.myState = 8
            else:
                _LOGGER.error("Invalid or no data received in state 7")
                self.myState = 0
                await self.close()
                return

            # State 8: Send request 6 and parse with parse_packet6
            await self.send_request(self.myRequests[6])
            data = await self.receive_response()
            if data and self.check_packet(data):
                self.parse_packet6(data)
                self.myState = 9
            else:
                _LOGGER.error("Invalid or no data received in state 8")
                self.myState = 0
                await self.close()
                return

            # State 9: Send request 7 and parse with parse_packet7
            await self.send_request(self.myRequests[7])
            data = await self.receive_response()
            if data and self.check_packet(data):
                self.parse_packet7(data)
                self.myState = 10
            else:
                _LOGGER.error("Invalid or no data received in state 9")
                self.myState = 0
                await self.close()
                return

            # State 10: Send request 8 and parse with parse_packet8
            await self.send_request(self.myRequests[8])
            data = await self.receive_response()
            if data and self.check_packet(data):
                self.parse_packet8(data)
                self.myState = 0  # Polling completed
            else:
                _LOGGER.error("Invalid or no data received in state 10")
                self.myState = 0
                await self.close()
                return

        # Close the connection
        await self.close()
        self.myState = 0

    def get_data(self) -> dict:
        """Retrieve the collected data."""
        return {
            "serial_number": self.hvsSerial,
            "bmu_firmware": self.hvsBMU,
            "bms_firmware": self.hvsBMS,
            "modules": self.hvsModules,
            "towers": self.hvsTowers,
            "grid_type": self.hvsGrid,
            "soc": self.hvsSOC,
            "max_voltage": self.hvsMaxVolt,
            "min_voltage": self.hvsMinVolt,
            "soh": self.hvsSOH,
            "current": self.hvsA,
            "battery_voltage": self.hvsBattVolt,
            "max_temperature": self.hvsMaxTemp,
            "min_temperature": self.hvsMinTemp,
            "battery_temperature": self.hvsBatTemp,
            "voltage_difference": self.hvsDiffVolt,
            "power": self.hvsPower,
            "error": self.hvsErrorString,
            "cell_voltages": self.cellVoltages,
            "cell_temperatures": self.cellTemperatures,
            "balancing_status": self.balancingStatus,
            "balancing_count": self.balancingCount,
            # Additional data can be added here if needed
        }
