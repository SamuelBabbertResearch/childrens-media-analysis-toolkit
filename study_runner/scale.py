"""The adult participant-facing 1-5 pace scale: labelled turtle to rabbit.

The same widget is used for the unrecorded practice item and every adult
self-perception rating, so participants practise on the response format used
for the study trials.

The design and the evidence behind each constraint are in
STUDY_RATING_SCALE_DESIGN.md. The four that this module exists to enforce:

* **Every point is worded.** The turtle and the rabbit are end anchors sitting
  beside the scale, never a replacement for the five verbal labels.
* **Nothing is selected until the participant selects it.** No default, and no
  pre-highlighted midpoint for them to argue with.
* **Order is carried four times over** — position, number, word and a
  single-hue lightness ramp — and the SELECTED state is an outline plus an
  underline mark, so it never depends on colour.
* **The whole step is the target**, at least 78 px tall and 64 px wide.

The steps are painted rather than styled so that their appearance is fixed for
every participant regardless of the Windows theme in use on the study computer.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QSizePolicy, QWidget

from ui.tokens import PACE_SCALE, PACE_STEP_COLORS

# Floors, not the drawn size: the steps expand to fill the participant screen.
MIN_STEP_WIDTH = 64
MIN_STEP_HEIGHT = 78

_ICON_BOX = (60.0, 46.0)   # the coordinate space both creatures are drawn in


def _relative_font(base: QFont, factor: float, *, floor_px: int) -> QFont:
    """Scale a font whether the stylesheet set it in pixels or in points.

    The runner's stylesheet sets `font-size` in px, so `pointSizeF()` comes
    back as -1 and arithmetic on it silently produces a tiny font.
    """
    font = QFont(base)
    if base.pixelSize() > 0:
        font.setPixelSize(max(floor_px, int(round(base.pixelSize() * factor))))
    else:
        points = base.pointSizeF() if base.pointSizeF() > 0 else 12.0
        font.setPointSizeF(max(floor_px * 0.75, points * factor))
    return font


class _Creature(QWidget):
    """A turtle or a rabbit, painted flat and without a face.

    Deliberately expressionless. Face scales import affect the study did not
    ask about (Chambers et al., 2005); these two denote speed, and any smile,
    frown or motion line would put feeling back on the screen.
    """

    def __init__(self, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if kind not in ("turtle", "rabbit"):
            raise ValueError(f"unknown creature {kind!r}")
        self.kind = kind
        self.setFixedSize(92, 72)
        self.setAccessibleName(
            "The slow end of the scale" if kind == "turtle"
            else "The fast end of the scale")

    def _path(self) -> QPainterPath:
        path = QPainterPath()
        if self.kind == "turtle":
            shell = QRectF(14, 13, 30, 34)
            path.arcMoveTo(shell, 0)
            path.arcTo(shell, 0, 180)
            path.moveTo(11, 30)
            path.lineTo(47, 30)
            path.moveTo(18, 30)            # legs
            path.lineTo(18, 37)
            path.moveTo(40, 30)
            path.lineTo(40, 37)
            path.addEllipse(QRectF(45, 24, 12, 10))    # head, facing the fast end
            path.moveTo(11, 30)            # tail
            path.cubicTo(7, 31, 5, 29, 6, 27)
            path.moveTo(17, 24)            # shell plates
            path.lineTo(41, 24)
            path.moveTo(23, 16)
            path.lineTo(23, 30)
            path.moveTo(35, 16)
            path.lineTo(35, 30)
        else:
            path.moveTo(37, 20)            # near ear
            path.cubicTo(33, 10, 35, 2, 38, 3)
            path.cubicTo(41, 4, 41, 13, 40, 19)
            path.moveTo(43, 20)            # far ear
            path.cubicTo(43, 11, 46, 4, 49, 6)
            path.cubicTo(51, 8, 47, 16, 46, 21)
            path.addEllipse(QRectF(35, 18, 13, 13))    # head, facing the fast end
            path.addEllipse(QRectF(10, 21, 28, 18))    # body
            path.addEllipse(QRectF(6, 25, 7, 7))       # tail
            path.moveTo(18, 39)            # feet
            path.lineTo(18, 43)
            path.moveTo(30, 39)
            path.lineTo(30, 43)
        return path

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        scale = min(self.width() / _ICON_BOX[0], self.height() / _ICON_BOX[1])
        painter.translate((self.width() - _ICON_BOX[0] * scale) / 2,
                          (self.height() - _ICON_BOX[1] * scale) / 2)
        painter.scale(scale, scale)
        pen = QPen(QColor(PACE_SCALE["creature"]), 3.0)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(self._path())
        painter.end()


class _Step(QAbstractButton):
    """One response option: a number, its verbal label, and a ramp colour."""

    def __init__(self, value: int, anchor: str, scale: "PaceScale") -> None:
        super().__init__(scale)
        self.value = value
        self.anchor = anchor
        self._scale = scale
        self.setCheckable(True)
        self.setAutoExclusive(False)          # PaceScale owns exclusivity
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(MIN_STEP_WIDTH, MIN_STEP_HEIGHT)
        self.setText(f"{value}. {anchor}")
        self.setAccessibleName(f"{value}, {anchor}")

    def sizeHint(self) -> QSize:
        return QSize(150, 124)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        ink = QColor(PACE_SCALE["step_ink"])
        selected = QColor(PACE_SCALE["selected"])
        body = QRectF(self.rect()).adjusted(4, 4, -4, -4)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(PACE_STEP_COLORS[self.value - 1]))
        painter.drawRoundedRect(body, 6, 6)

        if self.isChecked():
            pen = QPen(selected, 4.0)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(body.adjusted(2, 2, -2, -2), 5, 5)
        elif self.underMouse() and self.isEnabled():
            painter.setPen(QPen(QColor(PACE_SCALE["creature"]), 2.0))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(body.adjusted(1, 1, -1, -1), 5, 5)

        if self.hasFocus():
            pen = QPen(selected, 2.0, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1),
                                    8, 8)

        number_font = _relative_font(self.font(), 2.0, floor_px=26)
        number_font.setBold(True)
        word_font = _relative_font(self.font(), 0.82, floor_px=13)
        word_font.setBold(True)

        painter.setPen(ink)
        number_height = body.height() * 0.46
        number_rect = QRectF(body.left(), body.top() + body.height() * 0.16,
                             body.width(), number_height)
        painter.setFont(number_font)
        painter.drawText(number_rect, Qt.AlignHCenter | Qt.AlignBottom,
                         str(self.value))

        if self.isChecked():
            # The second, colour-free signal that this is the recorded answer.
            metrics = painter.fontMetrics()
            half = metrics.horizontalAdvance(str(self.value)) / 2 + 3
            centre = body.center().x()
            painter.setPen(QPen(ink, 3.0))
            y = number_rect.bottom() + 4
            painter.drawLine(int(centre - half), int(y),
                             int(centre + half), int(y))

        painter.setPen(ink)
        painter.setFont(word_font)
        word_rect = QRectF(body.left() + 4, number_rect.bottom() + 8,
                           body.width() - 8,
                           body.bottom() - number_rect.bottom() - 12)
        painter.drawText(word_rect, Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap,
                         self.anchor)
        painter.end()

    def keyPressEvent(self, event) -> None:
        if not self._scale.handle_key(event):
            super().keyPressEvent(event)


class PaceScale(QWidget):
    """Horizontal 1-5 labelled ramp with turtle and rabbit end anchors.

    `value()` is None until the participant answers; `valueChanged` carries
    1-5. Nothing here writes a response — the window records only when the
    participant confirms, so a mis-click never becomes data.
    """

    valueChanged = Signal(int)

    def __init__(self, anchors, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        anchors = tuple(anchors)
        if len(anchors) != 5:
            raise ValueError("the pace scale takes exactly five verbal anchors")
        self._value: int | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        self.turtle = _Creature("turtle", self)
        layout.addWidget(self.turtle, 0, Qt.AlignVCenter)

        self.steps: list[_Step] = []
        for value, anchor in enumerate(anchors, 1):
            step = _Step(value, anchor, self)
            # These are answer *choices*, not the irreversible confirmation.
            # Commit the highlight on press instead of waiting for the release:
            # custom-painted QAbstractButtons otherwise feel laggy when someone
            # taps quickly, and can look as though the first tap was ignored.
            # The participant can still change the highlighted choice until the
            # separate "Lock response and continue" action.
            step.pressed.connect(
                lambda _checked=False, v=value: self.set_value(v))
            layout.addWidget(step, 1)
            self.steps.append(step)

        self.rabbit = _Creature("rabbit", self)
        layout.addWidget(self.rabbit, 0, Qt.AlignVCenter)
        self.setFocusProxy(self.steps[0])

    # -- state ---------------------------------------------------------------

    def value(self) -> int | None:
        """The chosen 1-5, or None while the participant has not answered."""
        return self._value

    def clear(self) -> None:
        """Return to no answer. Called before every trial: never a default."""
        self._value = None
        for step in self.steps:
            step.setChecked(False)
            step.update()

    def set_value(self, value: int, *, focus: bool = False) -> None:
        if not 1 <= value <= 5:
            return
        self._value = value
        for step in self.steps:
            step.setChecked(step.value == value)
            step.update()
        if focus:
            self.steps[value - 1].setFocus(Qt.ShortcutFocusReason)
        self.valueChanged.emit(value)

    # -- keyboard ------------------------------------------------------------

    def handle_key(self, event) -> bool:
        """1-5 answer directly; arrows move; Home/End jump. True if consumed.

        Adults rate 24 times in a sitting and will use the number keys; the
        window binds them again as shortcuts so they work while focus is on
        the confirm button.
        """
        text = event.text()
        if text in ("1", "2", "3", "4", "5"):
            self.set_value(int(text), focus=True)
            return True
        key = event.key()
        current = self._value
        if key in (Qt.Key_Right, Qt.Key_Down):
            self.set_value(1 if current is None else min(5, current + 1),
                           focus=True)
            return True
        if key in (Qt.Key_Left, Qt.Key_Up):
            self.set_value(5 if current is None else max(1, current - 1),
                           focus=True)
            return True
        if key == Qt.Key_Home:
            self.set_value(1, focus=True)
            return True
        if key == Qt.Key_End:
            self.set_value(5, focus=True)
            return True
        return False

    def keyPressEvent(self, event) -> None:
        if not self.handle_key(event):
            super().keyPressEvent(event)
