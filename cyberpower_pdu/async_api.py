"""An asynchronous library for interacting with CyberPower PDU (power distribution units), allowing
a user to control outlets and banks and request information from the PDU.
"""

# Core dependencies
from abc import ABC, abstractmethod
from enum import Enum
import random
from typing import Any

# Package dependencies
from pysnmp.hlapi.asyncio import (  # type: ignore
    CommunityData,
    ContextData,
    Gauge32,
    Integer,
    Integer32,
    ObjectIdentity,
    ObjectType,
    OctetString,
    SnmpEngine,
    UdpTransportTarget,
    Unsigned32,
    getCmd,
    setCmd,
)

# The explicit imports here are required for MyPy. Do not remove them and replace them with
# `import *`, as the `pysnmp` module is untyped and will generate errors without the explicit
# imports.


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


class AsyncCyberPowerPDUHardware(AsyncCyberPowerPDU):
    """An interface for interacting with a CyberPower PDU unit. After initialization, the PDU
    automatically handles out of index bank and outlet handling, generating exceptions if a bank
    or outlet was targeted that is out of range of the number of banks or outlets on the PDU.
    """

    def __init__(self, ip_address: str) -> None:
        self.__ip_address = ip_address

        # These aren't initialized until `initialize` is called
        self.__number_of_banks: int = 0
        self.__number_of_outlets: int = 0

    async def initialize(self) -> None:
        """Initializes communication to the PDU"""
        # Grab the number of banks and outlets so that when these are passed in as indices, they
        # can be checked if they are within range or not
        self.__number_of_banks = await get_number_of_banks(self.__ip_address)
        self.__number_of_outlets = await get_number_of_outlets(self.__ip_address)

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

    async def get_bank_load(self, bank: int) -> float:
        # Check if the bank is in range or not
        if 0 < bank <= self.__number_of_banks:
            return await get_bank_load(self.__ip_address, bank)
        else:
            message = (
                f"Invalid bank value of: {bank}. "
                "Valid bank values are 1 to {self.__number_of_banks}"
            )
            raise ValueError(message)

    async def get_outlet_state(self, outlet: int) -> bool:
        """Get the outlet's state. `True` means the outlet is enabled. `False` means that the
        outlet is disabled.
        """
        if self.__valid_outlet_index(outlet):
            return await get_outlet_state(self.__ip_address, outlet)
        else:
            raise self.__get_outlet_value_error(outlet)

    async def send_outlet_command(self, outlet: int, command: OutletCommand) -> None:
        """Send a command to the outlet"""
        if self.__valid_outlet_index(outlet):
            return await send_outlet_command(self.__ip_address, outlet, command)
        else:
            raise self.__get_outlet_value_error(outlet)


############################################################
#### Low-level SNMP helper functions #######################
############################################################

# These functions provide get and set functionality as well as converting between SNMP errors
# and values to Python exceptions and data types.


def convert_snmp_type_to_python_type(
    snmp_value: Integer32 | Integer | Unsigned32 | Gauge32 | OctetString | Any,
) -> int | str:
    """Helps convert an SNMP datatype to a Python type. Currently, only integers and strings are
    supported. Anything else raises a `TypeError` exception.
    """
    match snmp_value:
        case Integer32():
            return int(snmp_value)
        case Integer():
            return int(snmp_value)
        case Unsigned32():
            return int(snmp_value)
        case Gauge32():
            return int(snmp_value)
        case OctetString():
            return str(snmp_value)
        case _:
            message = (
                "Only SNMP types of type integer and string are supported. "
                f"Received type of {type(snmp_value)}"
            )
            raise TypeError(message)


async def get_data(ip_address: str, object_identity: str) -> int | str:
    """Get the OID's value. Only integer and string values are currently supported."""
    iterator = await getCmd(
        SnmpEngine(),
        CommunityData("public", mpModel=0),
        UdpTransportTarget(transportAddr=(ip_address, 161), timeout=1, retries=0),
        ContextData(),
        ObjectType(ObjectIdentity(object_identity)),
    )

    error_indication, error_status, _error_index, variable_bindings = iterator

    if error_indication:
        raise RuntimeError(str(error_indication))
    elif error_status:
        raise RuntimeError(str(error_status))
    else:
        [variable_binding] = variable_bindings
        [_oid, value] = variable_binding
        return convert_snmp_type_to_python_type(value)


async def get_integer_data(ip_address: str, object_identity: str) -> int:
    """An integer-typed version of `get_data`"""
    response = await get_data(ip_address, object_identity)
    match response:
        case int():
            return response
        case _:
            raise ValueError(f"Expected an integer response and received `{response}` instead")


async def get_string_data(ip_address: str, object_identity: str) -> str:
    """A string-typed version of `get_data`"""
    response = await get_data(ip_address, object_identity)
    match response:
        case str():
            return response
        case _:
            raise ValueError(f"Expected a string response and received `{response}` instead")


async def set_data(ip_address: str, object_identity: str, value: Any) -> None:
    """Set the OID value. The `value` parameter should be an SNMP type defined by `pysnmp.hlapi`."""
    iterator = await setCmd(
        SnmpEngine(),
        CommunityData("private", mpModel=0),
        UdpTransportTarget(transportAddr=(ip_address, 161), timeout=1, retries=0),
        ContextData(),
        ObjectType(ObjectIdentity(object_identity), value),
    )

    error_indication, error_status, _error_index, _variable_bindings = iterator

    if error_indication:
        raise RuntimeError(str(error_indication))
    elif error_status:
        raise RuntimeError(str(error_status))
    else:
        return None


############################################################
#### Specific SNMP get and set functions ###################
############################################################

# Note: If new commands are added here, their OID description should be added to the "OID listing"
# section of the README.md.


async def get_number_of_outlets(ip_address: str) -> int:
    """Get the number of controllable outlets on the PDU"""
    # The OID corresponds to ePDUOutletDevNumCntrlOutlets in the CyberPower_MIB_v2.11.mib file
    return await get_integer_data(ip_address, ".1.3.6.1.4.1.3808.1.1.3.3.1.3.0")


async def get_number_of_banks(ip_address: str) -> int:
    """Get the number of banks, usually a collection of 8 outlets, on the PDU. A bank corresponds
    to an independent power supply on the PDU
    """
    # The OID corresponds to ePDULoadDevNumBanks in the CyberPower_MIB_v2.11.mib file
    return await get_integer_data(ip_address, ".1.3.6.1.4.1.3808.1.1.3.2.1.4.0")


async def get_outlet_state(ip_address: str, outlet: int) -> bool:
    """Get the enabled state of the outlet. `True` means the outlet is enabled and
    `False` means the outlet is disabled.
    """
    # This OID corresponds to ePDUOutletStatusOutletState in the CyberPower_MIB_v2.11.mib file
    oid = f".1.3.6.1.4.1.3808.1.1.3.3.5.1.1.4.{outlet}"
    response = await get_integer_data(ip_address, oid)
    match response:
        case 1:
            return True
        case 2:
            return False
        case _:
            raise ValueError(f"Received unexpected value for outlet state: {response}")


async def send_outlet_command(ip_address: str, outlet: int, command: OutletCommand) -> None:
    """Set the enabled state of the outlet. `True` means the outlet will be enabled and
    `False` means that the outlet will be disabled.
    """
    # This OID corresponds to ePDUOutletControlOutletCommand in the CyberPower_MIB_v2.11.mib file
    oid = f".1.3.6.1.4.1.3808.1.1.3.3.3.1.1.4.{outlet}"
    await set_data(ip_address, oid, Integer(command.value))


async def get_bank_load(ip_address: str, bank: int) -> float:
    """Get the load, in amps, of the bank"""
    # The OID corresponds to ePDU2BankStatusLoad in the CyberPower_MIB_v2.11.mib file
    tenths_of_amps = await get_integer_data(ip_address, f".1.3.6.1.4.1.3808.1.1.6.5.4.1.5.{bank}")

    # The data is returned as an integer in tenths of amps, so we convert to a float and divide
    # by 10.0 to convert to decimal amps.
    return float(tenths_of_amps) / 10.0
