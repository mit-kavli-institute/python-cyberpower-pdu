"""An asynchronous library for interacting with CyberPower PDU (power distribution units), allowing
a user to control outlets and banks and request information from the PDU.
"""

# Core dependencies
from enum import Enum
import logging
from typing import override

# Package dependencies
from puresnmp import V2C, Client, PyWrapper  # type: ignore[import-not-found]
from puresnmp.types import Integer  # type: ignore[import-not-found]


logger = logging.getLogger("CyberPowerPDU")


############################################################
#### Data types ############################################
############################################################


class OutletCommand(Enum):
    """Represents a PDU outlet command for use when setting the state of an outlet"""

    IMMEDIATE_ON = 1
    """Commands the outlet to turn on immediately"""

    IMMEDIATE_OFF = 2
    """Commands the outlet to turn off immediately"""

    IMMEDIATE_REBOOT = 3
    """This reboots the outlet, which immediately turns off the outlet and then waits a configured
    amount of time before turning the outlet back on. This setting can be configured via the PDU's
    web interface.
    """


############################################################
#### Main class-based API ##################################
############################################################


class CyberPowerPDU:
    """Abstract class for a CyberPowerPDU. This is intended to provide a common, top-level
    interface for both a simulation and hardware implementation.
    """

    def __init__(self, ip_address: str, port: int = 161, simulate: bool = False) -> None:
        """Initializes the `CyberPowerPDU` object. If `simulate` is `True`, then the hardware is
        not connected to and is instead simulated.
        """
        # Note: Port 161 is the default SNMP port
        self.__session: CyberPowerPDU

        if simulate:
            self.__session = CyberPowerPDUSimulation()
        else:
            self.__session = CyberPowerPDUHardware(ip_address=ip_address, port=port)

    @property
    def number_of_outlets(self) -> int:
        """The total number of controllable outlets on the PDU"""
        return self.__session.number_of_outlets

    async def initialize(self) -> None:
        """Initializes the connection to the PDU"""
        await self.__session.initialize()

    async def close(self) -> None:
        """Closes the connection to the PDU"""
        await self.__session.close()

    async def get_all_outlet_states(self) -> list[bool]:
        """Get the state of all outlets. Each index of the returned list corresponds to an outlet.
        The index is one less than the outlet number. For example, index 0 corresponds to outlet 1.
        `True` means the outlet is enabled. `False` means the outlet is disabled.
        """
        return await self.__session.get_all_outlet_states()

    async def get_outlet_state(self, outlet: int) -> bool:
        """Get the outlet's state. `True` means the outlet is enabled. `False` means that the
        outlet is disabled. The outlet number should range between 1 and the total number of
        outlets on the PDU.
        """
        return await self.__session.get_outlet_state(outlet)

    async def send_outlet_command(self, outlet: int, command: OutletCommand) -> None:
        """Send a command to the outlet. The outlet number should range between 1 and the total
        number of outlets on the PDU.
        """
        await self.__session.send_outlet_command(outlet, command)


############################################################
#### Simulated PDU #########################################
############################################################


class CyberPowerPDUSimulation(CyberPowerPDU):
    """A simulated PDU class primarily intended to enable GUI development without actual hardware"""

    def __init__(self) -> None:
        self.__number_of_outlets: int = 0
        self.__outlet_states: list[bool] = []

    @property
    def number_of_outlets(self) -> int:
        if self.__number_of_outlets == 0:
            raise RuntimeError(
                "The `initialize` must be called to populate the `number_of_outlets` property"
            )
        return self.__number_of_outlets

    @override
    async def initialize(self) -> None:
        self.__number_of_outlets = 16
        self.__outlet_states = [False] * self.__number_of_outlets
        logger.info("Simulated initialization complete")

    @override
    async def close(self) -> None:
        logger.info("Simulated connection closed")
        pass

    @override
    async def get_all_outlet_states(self) -> list[bool]:
        return self.__outlet_states

    @override
    async def get_outlet_state(self, outlet: int) -> bool:
        return self.__outlet_states[outlet - 1]

    @override
    async def send_outlet_command(self, outlet: int, command: OutletCommand) -> None:
        match command:
            case OutletCommand.IMMEDIATE_ON:
                logger.info(f"Simulated outlet {outlet} turned on")
                self.__outlet_states[outlet - 1] = True

            case OutletCommand.IMMEDIATE_OFF:
                logger.info(f"Simulated outlet {outlet} turned off")
                self.__outlet_states[outlet - 1] = False

            case OutletCommand.IMMEDIATE_REBOOT:
                logger.info(f"Simulated outlet {outlet} rebooted")
                self.__outlet_states[outlet - 1] = True


############################################################
#### Hardware PDU ##########################################
############################################################


class CyberPowerPDUHardware(CyberPowerPDU):
    """An interface for interacting with a CyberPower PDU unit. After initialization, the PDU
    automatically handles out of index bank and outlet handling, generating exceptions if a bank
    or outlet was targeted that is out of range of the number of banks or outlets on the PDU.
    """

    def __init__(self, ip_address: str, port: int = 161) -> None:
        self.__ip_address = ip_address

        # These aren't initialized until `initialize` is called
        self.__number_of_outlets: int = 0

        # This is initialized in the `initialize` method
        self.__client: PyWrapper

    ############################################################
    #### Properties ############################################
    ############################################################

    @property
    def number_of_outlets(self) -> int:
        """The total number of controllable outlets on the PDU"""
        if self.__number_of_outlets == 0:
            raise RuntimeError(
                "The `initialize` must be called to populate the `number_of_outlets` property"
            )
        return self.__number_of_outlets

    ############################################################
    #### Override methods ######################################
    ############################################################

    @override
    async def initialize(self) -> None:
        """Initializes communication to the PDU"""

        self.__client = PyWrapper(
            Client(ip=self.__ip_address, port=161, credentials=V2C("private"))
        )

        # Grab the number of banks and outlets so that when these are passed in as indices, they
        # can be checked if they are within range or not
        self.__number_of_outlets = await self.__get_number_of_outlets()
        logger.debug(f"Successfully connected to {self.__number_of_outlets} outlets")

    @override
    async def close(self) -> None:
        # There is no close needed for SNMP. This override is here to be explicit.
        logger.debug("Closing connection")

    @override
    async def get_all_outlet_states(self) -> list[bool]:
        return [
            await self.get_outlet_state(outlet) for outlet in range(1, self.number_of_outlets + 1)
        ]

    @override
    async def get_outlet_state(self, outlet: int) -> bool:
        if self.__valid_outlet_index(outlet):
            # This OID corresponds to ePDUOutletStatusOutletState in the CyberPower_MIB_v2.11.mib file
            response = await self.__client.get(oid=f".1.3.6.1.4.1.3808.1.1.3.3.5.1.1.4.{outlet}")

            match int(response):
                case 1:
                    return True
                case 2:
                    return False
                case _:
                    raise ValueError(f"Received unexpected value for outlet state: {response}")
        else:
            raise self.__get_outlet_value_error(outlet)

    @override
    async def send_outlet_command(self, outlet: int, command: OutletCommand) -> None:
        if self.__valid_outlet_index(outlet):
            logger.debug(f"Sending {command.name.lower()} to outlet {outlet}")
            # This OID corresponds to ePDUOutletControlOutletCommand in the CyberPower_MIB_v2.11.mib file
            oid = f".1.3.6.1.4.1.3808.1.1.3.3.3.1.1.4.{outlet}"
            await self.__client.set(oid=oid, value=Integer(command.value))

        else:
            raise self.__get_outlet_value_error(outlet)

    ############################################################
    #### Private methods #######################################
    ############################################################

    async def __get_number_of_outlets(self) -> int:
        # The OID corresponds to ePDUOutletDevNumCntrlOutlets in the CyberPower_MIB_v2.11.mib file
        return int(await self.__client.get(oid=".1.3.6.1.4.1.3808.1.1.3.3.1.3.0"))

    async def __get_number_of_banks(self) -> int:
        """Get the number of banks, usually a collection of 8 outlets, on the PDU. A bank corresponds
        to an independent power supply on the PDU
        """
        # The OID corresponds to ePDULoadDevNumBanks in the CyberPower_MIB_v2.11.mib file
        return int(await self.__client.get(oid=".1.3.6.1.4.1.3808.1.1.3.2.1.4.0"))

    async def __get_bank_load(self, bank: int) -> float:
        """Get the load, in amps, of the bank"""
        # The OID corresponds to ePDU2BankStatusLoad in the CyberPower_MIB_v2.11.mib file
        tenths_of_amps = float(
            await self.__client.get(oid=f".1.3.6.1.4.1.3808.1.1.6.5.4.1.5.{bank}")
        )

        # The data is returned as an integer in tenths of amps, so we convert to a float and divide
        # by 10.0 to convert to decimal amps.
        return float(tenths_of_amps) / 10.0

    def __valid_outlet_index(self, outlet: int) -> bool:
        """Returns whether the outlet is in range or not"""
        return 0 < outlet <= self.number_of_outlets

    def __get_outlet_value_error(self, outlet: int) -> ValueError:
        """Returns a `ValueError` exception to be raised in the event of an outlet being
        out of range
        """

        message = (
            f"Invalid outlet value of: {outlet}. Valid outlet values "
            f"are 1 to {self.number_of_outlets}"
        )
        return ValueError(message)
