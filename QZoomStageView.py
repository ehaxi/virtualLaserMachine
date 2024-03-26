from math import floor, log10
from typing import Tuple

from PyQt6.QtCore import QSize, Qt, QPoint, QPointF, QRectF, QObject, pyqtSignal, QTimer
from PyQt6.QtGui import QImage, QResizeEvent, QPaintEvent, QPainter, QMatrix4x4, QTransform, QPen, QMouseEvent, \
    QWheelEvent, QStaticText, QColor, QBrush
from PyQt6.QtWidgets import QWidget
from MarkerState import MarkerState
from LaserMachine import LaserMachine

class StageViewSignals(QObject):
        mouseStageClicked = pyqtSignal(QPoint)
class QZoomStageView(QWidget):
    def __init__(self):
        super(QWidget, self).__init__()
        self.__zoom = 1
        self.__oldMousePosition = QPoint()
        self.setMouseTracking(True)
        self.__isInDragMode = False
        self.canvas = QImage()
        self.init_image(self.size())
        self.__markerPoint = QPoint()
        self.__markerState = MarkerState.OFF
        self.__cameraPosition = QPoint()
        self.__grid_size_ws = 1
        self.stageLimits = QSize(500, 500)
        self.signals = StageViewSignals()
        self.__holdTimer = QTimer()
        self.__holdTimer.setInterval(250)
        self.__holdTimer.timeout.connect(self.__hold_timer_timeout)
        self.points = []
        self.set_zoom(1)
        self.pos_x = 0

    def showEvent(self, e) -> None:
        self.__cameraPosition = QPointF(10, 40)  # QPointF(self.frameSize().width() * 0.5, self.frameSize().height() * 0.5)
        self.set_zoom(10)

    def setStageLimits(self, limits: QSize):
        self.stageLimits = limits
        self.init_image(limits)
        self.update()

    def setCurrentPosition(self, position: QPoint):
        self.__markerPoint = position
        self.points.append(position)
        self.update()

    def init_image(self, size: QSize):
        self.image = QImage(size.width(), size.height(), QImage.Format.Format_ARGB32)



    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.__oldMousePosition = e.position().toPoint()
            self.__holdTimer.start()

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            if not self.__isInDragMode:
                self.moveToClick(e.pos())
            self.__holdTimer.stop()
            self.__isInDragMode = False


    def moveToClick(self, e: QPoint):
        matrix = QTransform()
        matrix.scale(self.__zoom, self.__zoom)  # инвертируем для привычной сетки осей
        matrix.translate(self.__cameraPosition.x(), self.__cameraPosition.y())  # - т.к зумили в -1 по y
        inverted, result = matrix.inverted()
        wx, wy = inverted.map(e.x(), e.y())
        self.signals.mouseStageClicked.emit(QPoint(wx, -wy))


    def __hold_timer_timeout(self):
        self.__isInDragMode = True

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if self.__isInDragMode:
            deltaX = e.position().x() - self.__oldMousePosition.x()
            deltaY = e.position().y() - self.__oldMousePosition.y()
            self.__cameraPosition = self.__cameraPosition + QPointF(deltaX, deltaY) / self.__zoom
            self.update()
            self.__oldMousePosition = e.position().toPoint()

    def wheelEvent(self, e: QWheelEvent) -> None:
        steps = e.angleDelta().y()
        vector = steps and steps // abs(steps)
        self.set_zoom(max(0.1, self.__zoom * (1.1 if vector > 0 else 0.9)))
        self.update()

    def resizeEvent(self, e: QResizeEvent):
        self.init_image(e.size())

    def set_zoom(self, zoom):
        if zoom <= 0.1:
            zoom = 0.1
        old_zoom = self.__zoom
        self.__zoom = zoom

        matrix = QTransform()
        matrix.scale(self.__zoom, -self.__zoom)  # инвертируем для привычной сетки осей
        matrix.translate(self.__cameraPosition.x(), -self.__cameraPosition.y())  # - т.к зумили в -1 по y
        inverted, result = matrix.inverted()
        viewport_rect = self.rect()
        world_rect = inverted.mapRect(viewport_rect)
        top = world_rect.top()
        bottom = world_rect.bottom()
        left = world_rect.left()
        right = world_rect.right()

        length = min(max(self.stageLimits.width(), self.stageLimits.height()),
                     max(abs(top - bottom), abs(left - right)))
        major_step = 10
        self.__grid_size_ws, calculated_step = self.calc_step_size(length, major_step)
        # self.__grid_size_ws = 10

    @staticmethod
    def calc_step_size(range, targetSteps) -> tuple[float, float | int]:
        tempStep = range / targetSteps
        mag = floor(log10(tempStep))
        magPow = 10.0 ** mag

        magMsd = int(tempStep / magPow + .5)

        if magMsd > 5.0:
            magMsd = 10.0
        elif magMsd > 2.0:
            magMsd = 5.0
        elif magMsd > 1.0:
            magMsd = 2.0

        return magMsd * magPow, magMsd

    def clamp(self, value, minvalue, maxvalue) -> float:
        return max(minvalue, min(value, maxvalue))

    def is_change(self):
        pos = LaserMachine()

    def paintEvent(self, e: QPaintEvent):
        painter = QPainter(self)
        painter.fillRect(e.rect(), QColor(0,33,55))
        painter.save()
        matrix = QTransform()
        matrix.scale(self.__zoom, self.__zoom)  # инвертируем для привычной сетки осей
        matrix.translate(self.__cameraPosition.x(), self.__cameraPosition.y())  # - т.к зумили в -1 по y
        painter.setWorldMatrixEnabled(True)
        painter.setWorldTransform(matrix, False)
        painter.setClipping(False)
        painter.setPen(QPen(QColor(0,123,168), 2.0 / self.__zoom))
        inverted, result = matrix.inverted()
        world_rect = inverted.mapRect(self.rect().toRectF())
        verticalBoundsTop = QPointF(0, world_rect.top())
        verticalBoundsBottom = QPointF(0, world_rect.bottom())
        horizontalBoundsLeft = QPointF(world_rect.left(), 0)
        horizontalBoundsRight = QPointF(world_rect.right(), 0)
        painter.drawLine(verticalBoundsTop, verticalBoundsBottom)  # vertical
        painter.drawLine(horizontalBoundsLeft, horizontalBoundsRight)  # horizontal

        painter.setPen(QPen(QColor(0,123,168), 1.0 / self.__zoom))

        max_h_limit = min(self.stageLimits.width(), world_rect.right())
        min_h_limit = max(0, world_rect.left())
        max_v_limit = max(-self.stageLimits.height(), world_rect.top())
        min_v_limit = min(0, world_rect.bottom())
        font = painter.font()

        font.setPointSizeF(12 / self.__zoom if self.__zoom > 1 else 12)
        painter.setFont(font)
        x = -500
        while x <= max_h_limit:  # vertical lines
            start = QPointF(x, -500)
            end = QPointF(x, 500)
            painter.drawLine(start, end)

            text = QStaticText(x.__str__())
            if x == 0:
                painter.drawStaticText(QPointF(x - 30.0 / (self.__zoom * 15), 0), text)
            else:
                painter.drawStaticText(QPointF(x - text.size().width() * 0.5 / (self.__zoom * 15), 0), text)
            x += self.__grid_size_ws

        y = 500
        while y >= max_v_limit:
            start = QPointF(-500, y)
            end = QPointF(500, y)
            painter.drawLine(start, end)

            text = QStaticText((-y).__str__())
            if y != 0:
                painter.drawStaticText(QPointF(-text.size().width() * 17.5 / (self.__zoom * 15),
                                               y - text.size().width() * 0.5 / (self.__zoom * 15)), text)
            y -= self.__grid_size_ws



        marker_size = int(max(1, 10 // (self.__zoom * 20)))

        # for p in self.points:
        #     painter.fillRect(p.x(), p.y(), int(1), int(1), Qt.GlobalColor.yellow)

        painter.translate(-0.5 * marker_size, -0.5 * marker_size)
        print(f"mp: {self.__markerPoint}")
        if self.__markerState != MarkerState.HIDE:
            if self.__markerState == MarkerState.ON:
                markerColor: QColor = Qt.GlobalColor.red
            else:
                markerColor: QColor = Qt.GlobalColor.yellow
            painter.setBrush(QBrush(markerColor))
            painter.drawEllipse(int(self.__markerPoint.x()), int(self.__markerPoint.y()), marker_size, marker_size)
        painter.translate(0.5 * marker_size, 0.5 * marker_size)
        painter.restore()
        painter.setPen(QPen(Qt.GlobalColor.white, 2))
        painter.drawStaticText(QPointF(5, 5), QStaticText(f"Zoom: {self.__zoom : .2f}"))

        pos_x = self.__markerPoint.x()
        pos_y = self.__markerPoint.y()
        painter.drawStaticText(QPointF(5, 20), QStaticText(f"Marker position: x = {pos_x}, y = {pos_y}"))
        painter.drawStaticText(QPointF(5, 35), QStaticText(f"State: {str(self.__markerState)[12:]}"))

