"""Participant presentation UI for the adult-only standalone Study Runner."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QCheckBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QSlider, QStackedWidget, QVBoxLayout, QWidget,
)

from .core import BLOCK_TYPE, ResponseStore, StudyPackage, Stimulus
from .scale import PaceScale


STYLE = """
QWidget { background: #f4f5f7; color: #202124; font-size: 18px; }
QLabel#title { font-size: 30px; font-weight: 600; }
QLabel#question { font-size: 26px; font-weight: 600; }
QLabel#muted { color: #59636e; font-size: 15px; }
QPushButton { min-height: 46px; padding: 5px 18px; }
QPushButton#primary { background: #1769c2; color: white; border-radius: 6px; }
QVideoWidget { background: black; }
"""


class StudyRunnerWindow(QMainWindow):
    def __init__(self, package: StudyPackage, data_dir: Path) -> None:
        super().__init__()
        self.package = package
        self.data_dir = data_dir
        self.store: ResponseStore | None = None
        self.order: tuple[Stimulus, ...] = ()
        self.trial_index = 0
        self.block_type = BLOCK_TYPE
        self.current_rating: int | None = None
        self.play_started = False
        self.awaiting_rating = False
        self.technical_restart_allowed = False
        # Qt Multimedia may emit the same backend error again when `stop()` is
        # called from the error handler. Treat one playback failure as one
        # interruption; otherwise the handler can recursively checkpoint and
        # reopen its modal forever.
        self._handling_media_error = False

        self.setWindowTitle(package.title)
        self.resize(1080, 760)
        self.setStyleSheet(STYLE)
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self._build_setup()
        self._build_instructions()
        self._build_practice()
        self._build_video()
        self._build_rating()
        self._build_done()
        self.stack.setCurrentWidget(self.setup_page)

    def _page(self) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(70, 50, 70, 50)
        lay.setSpacing(20)
        return page, lay

    def _build_setup(self) -> None:
        self.setup_page, lay = self._page()
        title = QLabel("Researcher session setup")
        title.setObjectName("title")
        lay.addWidget(title)
        note = QLabel(
            "Complete this screen before handing the computer to the participant. "
            "The runner assigns the next order automatically.")
        note.setWordWrap(True)
        note.setObjectName("muted")
        lay.addWidget(note)
        form = QFormLayout()
        self.participant_id = QLineEdit()
        self.participant_id.setPlaceholderText("Anonymous numeric code only")
        form.addRow("Participant ID", self.participant_id)
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(100)
        self.volume_value = QLabel("100%")
        volume_row = QHBoxLayout()
        volume_row.addWidget(self.volume, 1)
        volume_row.addWidget(self.volume_value)
        form.addRow("Calibrated volume", volume_row)
        lay.addLayout(form)
        self.age_confirmed = QCheckBox(
            "I confirmed that the participant is age 18 or older.")
        self.consent_confirmed = QCheckBox(
            "The participant completed informed consent and had an opportunity to ask questions.")
        lay.addWidget(self.age_confirmed)
        lay.addWidget(self.consent_confirmed)
        lay.addStretch(1)
        status = QLabel(
            f"Package: {self.package.study_id} · {self.package.status.upper()} · "
            f"{self.package.package_hash[:12]}")
        status.setObjectName("muted")
        lay.addWidget(status)
        start = QPushButton("Begin participant instructions")
        start.setObjectName("primary")
        start.clicked.connect(self._start_session)
        lay.addWidget(start, alignment=Qt.AlignRight)
        self.volume.valueChanged.connect(
            lambda value: self.volume_value.setText(f"{value}%"))
        self.stack.addWidget(self.setup_page)

    def _build_instructions(self) -> None:
        self.instructions_page, lay = self._page()
        title = QLabel("Before you begin")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)
        for instruction in self.package.instructions:
            label = QLabel(f"• {instruction}")
            label.setWordWrap(True)
            lay.addWidget(label)
        lay.addStretch(1)
        button = QPushButton("Try the practice question")
        button.setObjectName("primary")
        button.clicked.connect(self._show_practice)
        lay.addWidget(button, alignment=Qt.AlignRight)
        self.stack.addWidget(self.instructions_page)

    def _build_practice(self) -> None:
        self.practice_page, lay = self._page()
        title = QLabel("Practice")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)
        prompt = QLabel(self.package.practice_prompt)
        prompt.setObjectName("question")
        prompt.setWordWrap(True)
        prompt.setAlignment(Qt.AlignCenter)
        lay.addWidget(prompt)
        self.practice_feedback = QLabel(
            "This practice response is not saved with study responses.")
        self.practice_feedback.setObjectName("muted")
        self.practice_feedback.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.practice_feedback)
        lay.addStretch(1)
        self.practice_scale = PaceScale(self.package.anchors)
        self.practice_scale.valueChanged.connect(self._practice_selected)
        lay.addWidget(self.practice_scale, 2)
        lay.addStretch(1)
        self.practice_continue = QPushButton("Begin the study")
        self.practice_continue.setObjectName("primary")
        self.practice_continue.setEnabled(False)
        self.practice_continue.clicked.connect(self._begin_trials)
        lay.addWidget(self.practice_continue, alignment=Qt.AlignRight)
        self.stack.addWidget(self.practice_page)

    def _build_video(self) -> None:
        self.video_page, lay = self._page()
        self.video_heading = QLabel("Watch the clip")
        self.video_heading.setObjectName("title")
        self.video_heading.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.video_heading)
        self.video = QVideoWidget()
        lay.addWidget(self.video, 1)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(1.0)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video)
        self.player.mediaStatusChanged.connect(self._media_status)
        self.player.errorOccurred.connect(self._media_error)
        actions = QHBoxLayout()
        self.stop_video_button = QPushButton("Stop participating")
        self.stop_video_button.clicked.connect(self._withdraw_session)
        actions.addWidget(self.stop_video_button)
        actions.addStretch(1)
        self.play_button = QPushButton("Play clip")
        self.play_button.setObjectName("primary")
        self.play_button.clicked.connect(self._play)
        actions.addWidget(self.play_button)
        lay.addLayout(actions)
        self.stack.addWidget(self.video_page)

    def _build_rating(self) -> None:
        self.rating_page, lay = self._page()
        self.question = QLabel(self.package.question)
        self.question.setObjectName("question")
        self.question.setWordWrap(True)
        self.question.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.question)
        hint = QLabel("Choose one. You can change your answer until you continue.")
        hint.setObjectName("muted")
        hint.setAlignment(Qt.AlignCenter)
        lay.addWidget(hint)
        lay.addStretch(1)
        self.scale = PaceScale(self.package.anchors)
        self.scale.valueChanged.connect(self._rating_selected)
        lay.addWidget(self.scale, 2)
        lay.addStretch(1)
        self.rating_shortcuts = []
        for value in range(1, 6):
            shortcut = QShortcut(QKeySequence(str(value)), self.rating_page)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(
                lambda v=value: self.scale.set_value(v, focus=True))
            self.rating_shortcuts.append(shortcut)
        actions = QHBoxLayout()
        stop = QPushButton("Stop participating")
        stop.clicked.connect(self._withdraw_session)
        actions.addWidget(stop)
        self.skip_button = QPushButton("Skip this question")
        self.skip_button.clicked.connect(self._skip_rating)
        actions.addWidget(self.skip_button)
        actions.addStretch(1)
        self.lock_button = QPushButton("Lock response and continue")
        self.lock_button.setObjectName("primary")
        self.lock_button.setEnabled(False)
        self.lock_button.clicked.connect(self._lock_rating)
        actions.addWidget(self.lock_button)
        lay.addLayout(actions)
        self.stack.addWidget(self.rating_page)

    def _build_done(self) -> None:
        self.done_page, lay = self._page()
        lay.addStretch(1)
        self.done_title = QLabel("You are finished")
        self.done_title.setObjectName("title")
        self.done_title.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.done_title)
        self.done_message = QLabel(self.package.debrief)
        self.done_message.setAlignment(Qt.AlignCenter)
        self.done_message.setWordWrap(True)
        lay.addWidget(self.done_message)
        lay.addStretch(1)
        self.stack.addWidget(self.done_page)

    def _start_session(self) -> None:
        participant_id = self.participant_id.text().strip()
        if not self.age_confirmed.isChecked() or not self.consent_confirmed.isChecked():
            QMessageBox.warning(
                self, "Eligibility and consent required",
                "Confirm adult eligibility and completed consent before starting.")
            return
        try:
            self.store = ResponseStore(self.data_dir, self.package, participant_id)
            self.order = self.package.order(self.store.condition)
        except (ValueError, OSError) as exc:
            QMessageBox.critical(self, "Cannot start session", str(exc))
            return
        self.audio.setVolume(self.volume.value() / 100)
        self.trial_index = 0
        self.stack.setCurrentWidget(self.instructions_page)

    def _show_practice(self) -> None:
        self.practice_scale.clear()
        self.practice_continue.setEnabled(False)
        self.practice_feedback.setText(
            "This practice response is not saved with study responses.")
        self.stack.setCurrentWidget(self.practice_page)

    def _practice_selected(self, rating: int) -> None:
        expected = self.package.practice_expected_rating
        if rating == expected:
            self.practice_feedback.setText(
                "That is correct. You are ready to begin.")
            self.practice_continue.setEnabled(True)
        else:
            self.practice_feedback.setText(
                "Please try again. Choose the option described in the practice prompt.")
            self.practice_continue.setEnabled(False)

    def _begin_trials(self) -> None:
        if not self.practice_continue.isEnabled():
            return
        self._show_video()

    def _show_video(self) -> None:
        stimulus = self.order[self.trial_index]
        self.video_heading.setText("Watch the clip")
        self.play_button.setText("Play clip")
        self.play_button.setEnabled(True)
        self._handling_media_error = False
        self.player.setSource(QUrl.fromLocalFile(str(stimulus.path)))
        self.play_started = False
        self.awaiting_rating = False
        self.technical_restart_allowed = False
        self.stack.setCurrentWidget(self.video_page)

    def _play(self) -> None:
        if self.play_started and not self.technical_restart_allowed:
            return
        if self.technical_restart_allowed:
            self.player.setPosition(0)
            self._handling_media_error = False
        self.play_started = True
        self.technical_restart_allowed = False
        self.play_button.setEnabled(False)
        self.play_button.setText("Playing…")
        self.player.play()

    def _media_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.EndOfMedia and not self.awaiting_rating:
            self.awaiting_rating = True
            self.player.stop()
            self._show_rating()

    def _media_error(self, _error, message: str) -> None:
        if (not message or self.store is None
                or self._handling_media_error):
            return
        self._handling_media_error = True
        self.player.stop()
        self.technical_restart_allowed = True
        self.store.checkpoint(status="technical_interruption",
                              next_trial=self.trial_index + 1,
                              next_block=BLOCK_TYPE)
        QMessageBox.critical(
            self, "Playback error",
            f"{message}\n\nAsk the researcher for help. The clip may be restarted "
            "from the beginning because playback was technically interrupted.")
        self.play_button.setText("Restart after technical interruption")
        self.play_button.setEnabled(True)

    def _show_rating(self) -> None:
        self.question.setText(self.package.question)
        self.current_rating = None
        self.scale.clear()
        self.lock_button.setEnabled(False)
        self.stack.setCurrentWidget(self.rating_page)

    def _rating_selected(self, rating: int) -> None:
        self.current_rating = rating
        self.lock_button.setEnabled(True)

    def _lock_rating(self) -> None:
        if self.current_rating is None or self.store is None:
            return
        stimulus = self.order[self.trial_index]
        try:
            self.store.append_rating(
                stimulus=stimulus, trial_order=self.trial_index + 1,
                rating=self.current_rating)
        except (ValueError, OSError) as exc:
            QMessageBox.critical(self, "Response was not saved", str(exc))
            return
        self._advance_trial()

    def _skip_rating(self) -> None:
        if self.store is None:
            return
        answer = QMessageBox.question(
            self, "Skip this question?",
            "No pacing rating will be recorded for this clip. Continue?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        stimulus = self.order[self.trial_index]
        try:
            self.store.append_skip(
                stimulus=stimulus, trial_order=self.trial_index + 1)
        except (ValueError, OSError) as exc:
            QMessageBox.critical(self, "Skip was not saved", str(exc))
            return
        self._advance_trial()

    def _advance_trial(self) -> None:
        if self.store is None:
            return
        self.trial_index += 1
        if self.trial_index >= len(self.order):
            self.store.checkpoint(status="complete",
                                  next_trial=len(self.order) + 1)
            self.done_title.setText("You are finished")
            self.done_message.setText(self.package.debrief)
            self.stack.setCurrentWidget(self.done_page)
        else:
            self.store.checkpoint(status="in_progress",
                                  next_trial=self.trial_index + 1,
                                  next_block=BLOCK_TYPE)
            self._show_video()

    def _withdraw_session(self) -> None:
        if self.store is None:
            return
        answer = QMessageBox.question(
            self, "Stop participating?",
            "Participation will stop now. Responses from this identifiable "
            "session will be removed.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        try:
            self.player.stop()
            self.store.withdraw()
        except (ValueError, OSError) as exc:
            QMessageBox.critical(self, "Withdrawal could not be completed", str(exc))
            return
        self.done_title.setText("The session has stopped")
        self.done_message.setText(
            "Your study responses were removed. Please tell the researcher "
            "that you stopped the session.")
        self.stack.setCurrentWidget(self.done_page)

    def closeEvent(self, event) -> None:
        active = (self.store is not None
                  and self.stack.currentWidget() is not self.done_page)
        if active:
            answer = QMessageBox.question(
                self, "Close this active session?",
                "The session is not complete. Closing now marks a technical "
                "termination; already recorded responses remain secured.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            self.store.checkpoint(status="technical_termination",
                                  next_trial=self.trial_index + 1,
                                  next_block=BLOCK_TYPE)
        # A closed QMainWindow is hidden, not necessarily destroyed. Disconnect
        # before stopping so queued backend errors cannot keep acting on a
        # participant session after its window has closed.
        try:
            self.player.mediaStatusChanged.disconnect(self._media_status)
            self.player.errorOccurred.disconnect(self._media_error)
        except (RuntimeError, TypeError):
            pass
        self.player.stop()
        self.player.setSource(QUrl())
        event.accept()
