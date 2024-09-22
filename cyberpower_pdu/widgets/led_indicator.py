# Core dependencies
from typing import Optional

# Package dependencies
from PySide6.QtCore import Property, QPointF, Qt  # type: ignore[import-not-found]
from PySide6.QtGui import (  # type: ignore[import-not-found]
    QBrush,
    QColor,
    QPainter,
    QPaintEvent,
    QPen,
    QRadialGradient,
    QResizeEvent,
)
from PySide6.QtWidgets import QAbstractButton, QWidget  # type: ignore[import-not-found]


class LedIndicator(QAbstractButton):  # type: ignore[misc]
    scaledSize = 1000.0

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        QAbstractButton.__init__(self, parent)

        self.setMinimumSize(24, 24)
        self.setCheckable(True)
        self.setDisabled(True)

        # Green
        self.on_color_1 = QColor(0, 255, 0)
        self.on_color_2 = QColor(0, 192, 0)
        self.off_color_1 = QColor(0, 28, 0)
        self.off_color_2 = QColor(0, 128, 0)

    def resizeEvent(self, _QResizeEvent: QResizeEvent) -> None:
        self.update()

    def paintEvent(self, _QPaintEvent: QPaintEvent) -> None:
        real_size = min(self.width(), self.height())

        painter = QPainter(self)
        pen = QPen(Qt.GlobalColor.black)
        pen.setWidth(1)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.scale(real_size / self.scaledSize, real_size / self.scaledSize)

        # Currently disabled this additional painting due to looks only but may bring it back
        # gradient = QRadialGradient(QPointF(-500, -500), 1500, QPointF(-500, -500))
        # gradient.setColorAt(0, QColor(224, 224, 224))
        # gradient.setColorAt(1, QColor(28, 28, 28))
        # painter.setPen(pen)
        # painter.setBrush(QBrush(gradient))
        # painter.drawEllipse(QPointF(0, 0), 500, 500)

        gradient = QRadialGradient(QPointF(500, 500), 1500, QPointF(500, 500))
        gradient.setColorAt(0, QColor(224, 224, 224))
        gradient.setColorAt(1, QColor(28, 28, 28))
        painter.setPen(pen)
        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(QPointF(0, 0), 450, 450)

        painter.setPen(pen)
        if self.isChecked():
            gradient = QRadialGradient(QPointF(-500, -500), 1500, QPointF(-500, -500))
            gradient.setColorAt(0, self.on_color_1)
            gradient.setColorAt(1, self.on_color_2)
        else:
            gradient = QRadialGradient(QPointF(500, 500), 1500, QPointF(500, 500))
            gradient.setColorAt(0, self.off_color_1)
            gradient.setColorAt(1, self.off_color_2)

        painter.setBrush(gradient)
        painter.drawEllipse(QPointF(0, 0), 400, 400)

    @Property(QColor)
    def onColor1(self):
        return self.on_color_1

    @onColor1.setter  # type: ignore[no-redef]
    def onColor1(self, color):
        self.on_color_1 = color

    @Property(QColor)
    def onColor2(self):
        return self.on_color_2

    @onColor2.setter  # type: ignore[no-redef]
    def onColor2(self, color):
        self.on_color_2 = color

    @Property(QColor)
    def offColor1(self):
        return self.off_color_1

    @offColor1.setter  # type: ignore[no-redef]
    def offColor1(self, color):
        self.off_color_1 = color

    @Property(QColor)
    def offColor2(self):
        return self.off_color_2

    @offColor2.setter  # type: ignore[no-redef]
    def offColor2(self, color):
        self.off_color_2 = color
