"""Tests for the CyberPower PDU library"""

# Core dependencies
import time

# Package dependencies
from pysnmp.hlapi import Bits, Gauge32, Integer, Integer32, OctetString, Unsigned32
import pytest

# Project dependencies
from cyberpower_pdu.sync_api import *

# Note: this should be placed in a configuration file somewhere
ip_address = "192.168.20.177"


def test_converting_snmp_data_to_python_data():
    assert convert_snmp_type_to_python_type(Integer32(-1000)) == -1000
    assert convert_snmp_type_to_python_type(Integer(32)) == 32
    assert convert_snmp_type_to_python_type(Integer(-17)) == -17
    assert convert_snmp_type_to_python_type(Unsigned32(32)) == 32
    assert convert_snmp_type_to_python_type(Gauge32(45)) == 45
    assert convert_snmp_type_to_python_type(OctetString("test")) == "test"

    # Check that exceptions are raised on data other than SNMP integers and strings
    with pytest.raises(TypeError):
        convert_snmp_type_to_python_type(20.12)

    with pytest.raises(TypeError):
        convert_snmp_type_to_python_type(Bits.withNamedBits(a=0, b=1, c=2))


@pytest.mark.requires_hardware
def test_getting_number_of_banks():
    assert get_number_of_banks(ip_address) >= 1


@pytest.mark.requires_hardware
def test_getting_number_of_outlets():
    assert get_number_of_outlets(ip_address) >= 1


@pytest.mark.requires_hardware
def test_getting_and_setting_outlet_state():
    for outlet in [1, get_number_of_outlets(ip_address)]:
        send_outlet_command(ip_address, outlet, OutletCommand.IMMEDIATE_OFF)

        time.sleep(1)

        assert get_outlet_state(ip_address, outlet) == False

        send_outlet_command(ip_address, outlet, OutletCommand.IMMEDIATE_ON)

        time.sleep(1)

        assert get_outlet_state(ip_address, outlet) == True
