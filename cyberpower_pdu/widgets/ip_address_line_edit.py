# Core dependencies
from typing import no_type_check

# Package dependencies
from PySide6.QtCore import QRegularExpression, Slot  # type: ignore[import-not-found]
from PySide6.QtGui import QRegularExpressionValidator, QValidator  # type: ignore[import-not-found]
from PySide6.QtWidgets import QLineEdit, QWidget  # type: ignore[import-not-found]


class IPAddressLineEdit(QLineEdit):  # type: ignore[misc]
    def __init__(self, parent: QWidget | None = None) -> None:
        QLineEdit.__init__(self, parent)

        ip_address_regex = QRegularExpression(
            r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
        )

        ip_address_validator = QRegularExpressionValidator(ip_address_regex)
        self.setValidator(ip_address_validator)
        self.textChanged.connect(self.check_ip_address)

    # The type check is ignored here because Qt is doing some dynamic lookups of the validator, stylesheets,
    # and other properties. This works as expected and could probably be fixed with some casts or other
    # type hints, but it isn't worth it.

    @Slot()
    @no_type_check
    def check_ip_address(self) -> None:
        """Checks the validity of the IP address, just the validity of the entered format, not in
        terms of any connection validity, and adjusts the background color of the control
        accordingly
        """

        sender = self.sender()
        validator = sender.validator()
        state = validator.validate(sender.text(), 0)[0]
        if state == QValidator.Acceptable:
            color = "#FFFFFF"
        else:
            color = "#F6989D"
        sender.setStyleSheet("QLineEdit { background-color: %s }" % color)
