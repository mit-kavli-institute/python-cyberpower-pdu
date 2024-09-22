"""Implements a simple control panel for a CyberPower PDU. See the README.md for a diagram of
the state machine that is implemented here using Qt's State Machine framework.
"""

# Core dependencies
import asyncio
import sys
from typing import Callable, no_type_check

# Package dependencies
import PySide6.QtAsyncio as QtAsyncio  # type: ignore[import-not-found]
from PySide6.QtCore import (  # type: ignore[import-not-found]
    Qt,
    QTimer,
    Signal,
    SignalInstance,
    Slot,
)
from PySide6.QtStateMachine import QState, QStateMachine  # type: ignore[import-not-found]
from PySide6.QtWidgets import (  # type: ignore[import-not-found]
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# Project dependencies
from cyberpower_pdu import CyberPowerPDU, OutletCommand
from cyberpower_pdu.widgets.ip_address_line_edit import IPAddressLineEdit
from cyberpower_pdu.widgets.led_indicator import LedIndicator


SIMULATE_HARDWARE = True


class OutletControl(QMainWindow):  # type: ignore[misc]
    """Provides a custom widget that is a vertical stack of an LED indicator, an on button, and an
    off button, stacked top to bottom.
    """

    def __init__(self, outlet: int) -> None:
        super().__init__()
        self.__outlet = outlet
        self.__layout = QVBoxLayout()
        self.__layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.__label = QLabel(str(outlet))
        self.__label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.__led = LedIndicator()
        self.__led.setEnabled(False)

        self.__on_button = QPushButton("On")
        self.__on_button.setFixedWidth(50)

        self.__off_button = QPushButton("Off")
        self.__off_button.setFixedWidth(50)

        self.__layout.addWidget(self.__label)
        self.__layout.addWidget(self.__led)
        self.__layout.addWidget(self.__on_button)
        self.__layout.addWidget(self.__off_button)

        self.setContentsMargins(0, 0, 0, 0)

        self.setLayout(self.__layout)

    @property
    def outlet(self) -> int:
        """Returns whether the outlet is powered on (`True`) or not (`False`)"""
        return self.__outlet

    @property
    def on_button_clicked(self) -> SignalInstance:
        """Returns the signal emitted when the on button is clicked"""
        return self.__on_button.clicked

    @property
    def off_button_clicked(self) -> SignalInstance:
        """Returns the signal emitted when the off button is clicked"""
        return self.__off_button.clicked

    @property
    def led_slot(self) -> Slot | Callable[[bool], None]:
        """Returns a slot to set the outlet control's LED indicator state"""
        return self.__led.setChecked

    @property
    def checked(self) -> bool:
        """Returns whether the LED is on (`True`) or off (`False`)"""
        return bool(self.__led.isChecked())

    @checked.setter
    def checked(self, value: bool) -> None:
        """Settable property for whether the LED should be on (`True`) or off (`False`)"""
        self.__led.setChecked(value)


class MainWindow(QWidget):  # type: ignore[misc]
    """This is the main GUI window for the application"""

    signal_connected_to_ip_address = Signal()
    signal_failed_to_connect_to_ip_address = Signal()

    def __init__(self) -> None:
        """Initialize the window"""

        super().__init__()
        self.__number_of_outlets = 0

        self.__pdu: CyberPowerPDU

    @Slot()
    @no_type_check
    async def try_ip_address(self) -> None:
        """Try the entered IP address. It is a valid IP but may not actually connect to
        a CyberPower PDU.
        """

        ip_address = self.__ip_address.text()
        self.__label.setText("Trying IP address: " + str(ip_address))

        self.__pdu = CyberPowerPDU(ip_address=ip_address, simulate=SIMULATE_HARDWARE)

        try:
            await self.__pdu.initialize()
            self.__number_of_outlets = self.__pdu.number_of_outlets

            # We index here because we create a total of 16 outlet controls, but the PDU may
            # support less than that. This is as opposed to dynamically creating outlet controls.

            for index in range(0, self.__number_of_outlets):
                self.__outlet_controls[index].setEnabled(True)

            # Emit signal to go to connected state
            self.signal_connected_to_ip_address.emit()

        except Exception:  # pylint: disable=broad-exception-caught
            # Emit signal to go to waiting on IP address state
            self.signal_failed_to_connect_to_ip_address.emit()

    @Slot()
    @no_type_check
    async def get_outlet_statuses(self) -> None:
        """Retrieves the status of all outlets by setting the outlet controls' LED indicators
        directly. This can take up to 1.2 seconds or so, so use it carefully since it could
        potentially lock up the GUI or thread that it is running on.
        """

        # We index here because we create a total of 16 outlet controls, but the PDU may
        # support less than that.

        for index in range(0, self.__number_of_outlets):
            outlet_control = self.__outlet_controls[index]
            outlet_control.checked = await self.__pdu.get_outlet_state(outlet_control.outlet)

    @Slot(OutletControl)
    @no_type_check
    async def send_outlet_command(self, outlet_control: OutletControl, state: bool) -> None:
        """Forward on the command to the outlet control's underlying outlet on the PDU"""

        if state:
            command = OutletCommand.IMMEDIATE_ON
        else:
            command = OutletCommand.IMMEDIATE_OFF

        await self.__pdu.send_outlet_command(outlet_control.outlet, command)

        # Since it takes a long time (approximately 1.2 seconds) to query the state of up to
        # 16 outlets, we simply fire off two state checks for the outlet that was commanded.
        # The state checks are sent 0.5 seconds and 1 second after the command is sent, as it
        # can take the PDU some time to actually physically toggle the state and return the
        # state correctly in the SNMP response. This of course leaves open the possibility of
        # the state taking longer than 1 second to update or an outlet changing state outside
        # of this GUI, but this is currently not handled in this GUI implementation.

        QTimer.singleShot(
            500,
            lambda outlet_control=outlet_control: asyncio.ensure_future(
                self.get_outlet_status(outlet_control)
            ),
        )
        QTimer.singleShot(
            1000,
            lambda outlet_control=outlet_control: asyncio.ensure_future(
                self.get_outlet_status(outlet_control)
            ),
        )

    @Slot(OutletControl)
    @no_type_check
    async def get_outlet_status(self, outlet_control: OutletControl) -> None:
        """Retrieve the state of the outlet assigned to the outlet control and set the outlet
        control's checked property
        """

        outlet_control.checked = await self.__pdu.get_outlet_state(outlet_control.outlet)

    async def initialize(self) -> None:  # pylint: disable=too-many-statements
        """Initialize the GUI widgets and state machine"""

        self.setWindowTitle("CyberPower PDU outlet controller")

        main_layout = QVBoxLayout()
        connection_row_layout = QHBoxLayout()
        outlet_row_layout = QHBoxLayout()
        main_layout.addLayout(connection_row_layout)
        main_layout.addLayout(outlet_row_layout)

        connection_row_layout.addWidget(QLabel("IP address: "))

        machine = QStateMachine(parent=self)
        state_waiting_for_ip_address = QState(machine)
        state_connecting = QState(machine)
        state_connected = QState(machine)
        machine.setInitialState(state_waiting_for_ip_address)

        label = QLabel()
        self.__label = label
        label.setFixedWidth(200)

        ip_address = IPAddressLineEdit()
        self.__ip_address = ip_address
        ip_address.setFixedWidth(130)
        is_connected_indicator = LedIndicator()
        is_connected_indicator.setChecked(False)
        connection_row_layout.addWidget(ip_address)
        connection_row_layout.addWidget(is_connected_indicator)
        connection_row_layout.addWidget(label)
        connection_row_layout.addStretch()

        outlet_controls = []

        for outlet in range(1, 17):
            outlet_control = OutletControl(outlet)
            outlet_control.setEnabled(False)
            outlet_row_layout.addWidget(outlet_control)

            # Create vertical separators between the outlets
            if outlet != 16:
                separator = QFrame()
                separator.setFrameShape(QFrame.Shape.VLine)
                separator.setFrameShadow(QFrame.Shadow.Sunken)
                outlet_row_layout.addWidget(separator)

            outlet_controls.append(outlet_control)

        state_waiting_for_ip_address.addTransition(ip_address.editingFinished, state_connecting)
        state_connecting.addTransition(ip_address.textChanged, state_waiting_for_ip_address)
        state_connected.addTransition(ip_address.textChanged, state_waiting_for_ip_address)
        state_connecting.addTransition(self.signal_connected_to_ip_address, state_connected)
        state_connecting.addTransition(
            self.signal_failed_to_connect_to_ip_address, state_waiting_for_ip_address
        )

        state_connecting.entered.connect(lambda: asyncio.ensure_future(self.try_ip_address()))
        state_connected.entered.connect(lambda: asyncio.ensure_future(self.get_outlet_statuses()))

        state_waiting_for_ip_address.assignProperty(ip_address, "enabled", True)
        state_waiting_for_ip_address.assignProperty(is_connected_indicator, "checked", False)
        state_connecting.assignProperty(is_connected_indicator, "checked", False)
        state_connecting.assignProperty(ip_address, "enabled", False)
        state_connected.assignProperty(ip_address, "enabled", True)
        state_connected.assignProperty(is_connected_indicator, "checked", False)
        state_connected.assignProperty(is_connected_indicator, "checked", True)

        for outlet_control in outlet_controls:
            state_waiting_for_ip_address.assignProperty(outlet_control, "checked", False)
            state_waiting_for_ip_address.assignProperty(outlet_control, "enabled", False)
            state_connecting.assignProperty(outlet_control, "checked", False)
            state_connecting.assignProperty(outlet_control, "enabled", False)

            # We need to tell MyPy to ignore these lines because we need to indicate the `[bool]`
            # type of the instance. If we do not, then we receive the error:
            #     TypeError: MainWindow.initialize.<locals>.<lambda>() missing 1 required
            #     positional argument: 'state'
            # If we remove the type ignore comment, then we receive the following MyPy error:
            #     error: Value of type "SignalInstance" is not indexable  [index]
            # It is possible that this is solvable, but for right now, we ignore the MyPy check

            outlet_control.on_button_clicked[bool].connect(
                lambda state, outlet_control=outlet_control: asyncio.ensure_future(
                    self.send_outlet_command(outlet_control, True)
                )
            )

            outlet_control.off_button_clicked[bool].connect(
                lambda state, outlet_control=outlet_control: asyncio.ensure_future(
                    self.send_outlet_command(outlet_control, False)
                )
            )

        self.__outlet_controls = outlet_controls

        state_waiting_for_ip_address.assignProperty(label, "text", "Waiting for valid IP address")
        state_connecting.assignProperty(label, "text", "Connecting to PDU")
        state_connected.assignProperty(label, "text", "Connected")

        self.setLayout(main_layout)

        # Disable the user being able to resize the window, as the window is fixed by the
        # auto-layout of the controls and resizing adjustments are not explicitly implemented
        main_layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

        machine.start()

        self.show()


async def main() -> None:
    application = QApplication(sys.argv)
    window = MainWindow()
    await window.initialize()


if __name__ == "__main__":
    QtAsyncio.run(main())
