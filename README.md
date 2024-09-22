# CyberPower PDU

This is a Python library for interacting with a [CyberPower Power Distribution Unit (PDU)](https://www.cyberpowersystems.com/products/pdu/).

## SNMP

To programmatically remote control a CyberPower PDU, one must use SNMP (simple network management protocol) over Ethernet. The various queries and commands that can be executed via SNMP for a given target are often included in an MIB (management information base) file. [For the CyberPower PDU, the MIB file can be found on their website](https://www.cyberpowersystems.com/products/software/mib-files/). The MIB file will contain human readable names and OID (object identifiers), which are a sequence of numbers, corresponding to the human readable names. In this library, the OIDs are directly used, which removes the need to manage the MIB file in code other than looking up various queries and commands available when developing. See the implementation for which OIDs are used, their corresponding names, and the MIB version that they were obtained from.

To view MIB files, find an MIB browser. One such browser is [MIB Browser by iReasoning](https://www.ireasoning.com/mibbrowser.shtml). Open the browser, select `File -> UnLoad MIBs` and then select all MIB files and hit `Ok`, and then select `File -> Load MIBs` and navigate to the CyberPower MIB file.

## OID listing

In SNMP communication, object identifiers (OIDs) are used to specify the specific data to get/set in an SNMP request. The following are the relevant OIDs currently used in this API. If more are added, this table should be updated. The OIDs come from the `CyberPower_MIB_v2.11.mib` file.

| OID                                          | Name                             | Value   | Type | Description |
| -------------------------------------------- | -------------------------------- | ------- | ---- | ----------- |
| `.1.3.6.1.4.1.3808.1.1.3.3.1.3.0`            | `ePDUOutletDevNumCntrlOutlets`   | n/a     | get  | Gets the number of controllable outlets on the PDU |
| `.1.3.6.1.4.1.3808.1.1.3.2.1.4.0`            | `ePDULoadDevNumBanks`            | n/a     | get  | Gets the number of power banks on the PDU. Power banks are a collection of outlets and associated with an independent power supply |
| `.1.3.6.1.4.1.3808.1.1.6.5.4.1.5.<outlet>`   | `ePDU2BankStatusLoad`            | n/a     | get  | Gets the current electrical load, in tenths of amps represented as an integer, of the given bank |
| `.1.3.6.1.4.1.3808.1.1.3.3.5.1.1.4.<outlet>` | `ePDUOutletStatusOutletState`    | n/a     | get  | Gets the enabled (i.e., on or off) of the given outlet. `<outlet>` is a 1-indexed integer value that specifies which outlet to control and runs from 1 to the number of controllable outlets. A response of `1` is on/enabled and `2` is off/disabled. |
| `.1.3.6.1.4.1.3808.1.1.3.3.3.1.1.4.<outlet>` | `ePDUOutletControlOutletCommand` | command | set  | Sets the enabled (i.e., on or off) of the given outlet. `<outlet>` is a 1-indexed integer value that specifies which outlet to control and runs from 1 to the number of controllable outlets. Values: `1` for immediate on, `2` for immediate off, `3` for immediate reboot. |

## GUI

**Note**: The GUI is not functional at the moment. Previously, the GUI was implemented using a synchronous library. Now that only an asynchronous library exists, the GUI has not been fully updated to work with this. Also, the current GUI implementation uses Qt Widgets. It is likely that when it is updated, it will be implemented using Qt Quick (QML).

The GUI implemented in `gui.py` implements the following state machine using Qt's State Machine framework. [See the documentation for PySide2](https://doc.qt.io/qtforpython-5/overviews/statemachine-api.html) since good expository documentation for PySide6 doesn't exist for the State Machine framework yet.

Run the GUI with:

```bash
poetry run python ./cyberpower-pdu/gui.py`
```

```mermaid
stateDiagram-v2
    [*] --> waiting_for_ip_address
    waiting_for_ip_address --> connecting: valid IP entered
    connecting --> waiting_for_ip_address: failed to connect\nto IP address
    connecting --> waiting_for_ip_address: IP address\nchanged
    connecting --> connected: connected to PDU\nat IP address
    connected --> waiting_for_ip_address: IP address changed
```



## SNMP library selection

Python has several SNMP libraries, but they each have their various tradeoffs.

* :white_check_mark: [`puresnmp`](https://github.com/exhuma/puresnmp): This library is a pure Python library and thus requires no external, OS-specific dependencies. It also does not interact with MIBs at all, which is a plus since MIBs cause a lot of issues, and it provides an `asyncio`-compatible interface, which is strongly desired for any network-based I/O. Lastly, the interface is very simple to use and a proper Python interface.

* :x: [`pysnmp-lextudio`](https://pypi.org/project/pysnmp-lextudio/): This library is a pure Python library, but it has an atypical Python interface. Additionally, it is extremely slow (1.2 seconds to get the status of 16 outlets on a CyberPower PDU), and it's `asyncio` interface is not properly asynchronous and will block the `asyncio` event loop for up to 100ms.

* :x: `pysnmp`: This is the package that `pysnmp-lextudio` was forked from but is no longer maintained.

* :x: `easysnmp`: Despite the name, this package returned several segmentation faults while testing the `set` functionality, which is why this library was not chosen. Additionally, it requires specific external system libraries to be installed, which makes it less portable and harder to install.

* :x: `net-snmp`: These are apparently "official" bindings for Python for SNMP, but the library is very low-level.
