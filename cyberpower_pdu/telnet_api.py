"""An asynchronous library for interacting with CyberPower PDU (power distribution units), allowing
a user to control outlets and banks and request information from the PDU.
"""

# Core dependencies
from abc import ABC, abstractmethod
from enum import Enum
import random
import re

# Package dependencies
import telnetlib3  # type: ignore[import-not-found]

############################################################
#### Data types ############################################
############################################################


class OutletCommand(Enum):
    """Represents a PDU outlet command for use when setting ePDUOutletControlOutletCommand"""

    IMMEDIATE_ON = 1
    IMMEDIATE_OFF = 2
    IMMEDIATE_REBOOT = 3
    """This reboots the outlet, which immediately turns off the outlet and then waits a configured
    amount of time before turning the outlet back on. This setting can be configured via the PDU's
    web interface.
    """

    def to_telnet_action(self) -> str:
        """Converts the command to the telnet action string that is sent to the PDU"""
        match self:
            case OutletCommand.IMMEDIATE_ON:
                return "on"
            case OutletCommand.IMMEDIATE_OFF:
                return "off"
            case OutletCommand.IMMEDIATE_REBOOT:
                return "reboot"


############################################################
#### Main class-based API ##################################
############################################################


class AsyncCyberPowerPDU(ABC):
    """Abstract class for a CyberPowerPDU. This is intended to provide a common, top-level
    interface for both a simulation and hardware implementation.
    """

    @abstractmethod
    async def initialize(self) -> None:
        """Initializes the connection to the PDU"""
        ...

    @abstractmethod
    async def get_bank_load(self, bank: int) -> float:
        """Get the total electrical load, in amps, of the given bank"""
        ...

    @abstractmethod
    async def get_outlet_state(self, outlet: int) -> bool:
        """Get the outlet's state. `True` means the outlet is enabled. `False` means that the
        outlet is disabled.
        """
        ...

    @abstractmethod
    async def send_outlet_command(self, outlet: int, command: OutletCommand) -> None:
        """Send a command to the outlet"""
        ...


class AsyncCyberPowerPDUSimulation(AsyncCyberPowerPDU):
    """A simulated PDU class primarily intended to enable GUI development without actual hardware"""

    def __init__(self) -> None:
        self.__number_of_outlets: int = 0
        self.__outlet_states: list[bool] = []

    async def initialize(self) -> None:
        self.__number_of_outlets = 16
        self.__outlet_states = [False] * self.__number_of_outlets

    async def get_bank_load(self, bank: int) -> float:
        return random.randrange(1, 5)

    async def get_outlet_state(self, outlet: int) -> bool:
        return self.__outlet_states[outlet - 1]

    async def send_outlet_command(self, outlet: int, command: OutletCommand) -> None:
        match command:
            case OutletCommand.IMMEDIATE_ON:
                self.__outlet_states[outlet - 1] = True

            case OutletCommand.IMMEDIATE_OFF:
                self.__outlet_states[outlet - 1] = False

            case OutletCommand.IMMEDIATE_REBOOT:
                self.__outlet_states[outlet - 1] = True


class AsyncTelnetCyberPowerPDUHardware(AsyncCyberPowerPDU):
    """An interface for interacting with a CyberPower PDU unit. After initialization, the PDU
    automatically handles out of index bank and outlet handling, generating exceptions if a bank
    or outlet was targeted that is out of range of the number of banks or outlets on the PDU.
    """

    def __init__(self, ip_address: str) -> None:
        self.__ip_address = ip_address

        # These aren't initialized until `initialize` is called
        self.__number_of_outlets: int = 0

        self.__reader: telnetlib3.TelnetReader
        self.__writer: telnetlib3.TelnetWriter

    async def initialize(self) -> None:
        """Initializes communication to the PDU"""

        self.__reader, self.__writer = await telnetlib3.open_connection(
            host=self.__ip_address, port=23
        )

        # Supply username
        await self.__reader.readuntil("Login Name: ".encode())
        self.__writer.write("test-username\r\n")
        await self.__writer.drain()

        # Supply password
        await self.__reader.readuntil("Login Password: ".encode())
        self.__writer.write("test-password\r\n")
        await self.__writer.drain()

        # Wait until the system is ready for commands
        await self.__reader.readuntil("CyberPower > ".encode())

        # Grab the number of outlets so that when these are passed in as indices, they
        # can be checked if they are within range or not
        self.__number_of_outlets = len(await self.get_outlet_states())

    @property
    def number_of_outlets(self) -> int:
        """The total number of controllable outlets on the PDU"""
        if self.__number_of_outlets == 0:
            raise RuntimeError(
                "The `initialize` must be called to populate the `number_of_outlets` property"
            )
        return self.__number_of_outlets

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

    async def get_outlet_state(self, outlet: int) -> bool:
        """Get the outlet's state. `True` means the outlet is enabled. `False` means that the
        outlet is disabled.
        """
        if self.__valid_outlet_index(outlet):
            return (await self.get_outlet_states())[outlet]
        else:
            raise self.__get_outlet_value_error(outlet)

    async def get_bank_load(self, bank: int) -> float:
        """Get the total electrical load, in amps, of the given bank"""
        raise NotImplementedError("This method is not implemented in the telnet API")

    async def send_outlet_command(self, outlet: int, command: OutletCommand) -> None:
        """Send a command to the outlet"""
        if self.__valid_outlet_index(outlet):
            self.__writer.write(f"oltctrl index {outlet} act {command.to_telnet_action()}\r\n")
            await self.__writer.drain()

        else:
            raise self.__get_outlet_value_error(outlet)

    async def get_outlet_states(self) -> dict[int, bool]:
        """Get the states of all the outlets on the PDU"""

        # Here's a sample of what the `oltsta` command returns:
        # """
        #     Name                                 Status         ----------------------------------------------------------------------------- # pylint: disable=line-too-long
        #     1  Outlet1                              Off
        #     2  Outlet2                              Off
        #     3  Outlet3                              Off
        #     4  Outlet4                              Off
        #     5  Outlet5                              Off
        #     6  Outlet6                              Off
        #     7  Outlet7                              Off
        #     8  Outlet8                              On

        # CyberPower >
        # """
        # This string may not be *exactly* what is returned, but it should be the same
        # modulo whitespace.

        def convert_telnet_string_to_bool(telnet_string: str) -> bool:
            match telnet_string.strip().lower():
                case "on":
                    return True
                case "off":
                    return False
                case _:
                    raise ValueError(f"Invalid telnet on/off string: {telnet_string}")

        pattern = r"(\d+)\s+\w+\d+\s+(On|Off)"

        outlet_states: dict[int, bool] = {}

        # Explicitly, not implicitly, check against an empty dictionary
        while outlet_states == {}:  # pylint: disable=use-implicit-booleaness-not-comparison
            self.__writer.write("oltsta show\r\n")
            await self.__writer.drain()
            response: str = (await self.__reader.readuntil("CyberPower > ".encode())).decode()
            matches = re.findall(pattern=pattern, string=response)

            outlet_states = {
                int(outlet): convert_telnet_string_to_bool(state) for outlet, state in matches
            }

        return outlet_states

    async def close(self) -> None:
        """Closes the underlying telnet connection to the PDU"""
        self.__writer.write("exit\r\n")
        await self.__writer.drain()

        # Read until EOF before closing the connection
        await self.__reader.read()
        self.__writer.close()
