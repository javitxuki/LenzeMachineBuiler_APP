# -*- coding: utf-8 -*-
from copy import deepcopy

from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QGroupBox, QHBoxLayout, QLabel, QMessageBox,
    QPlainTextEdit, QPushButton, QTextBrowser, QVBoxLayout, QWidget
)

from ai_parser import interpret, transcribe_audio
from ui.voice_recorder import MicrophoneRecorder


class InterpretWorker(QObject):
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(self, prompt, axes, config):
        super().__init__()
        self.prompt, self.axes, self.config = prompt, axes, config

    @Slot()
    def run(self):
        try:
            self.finished.emit(interpret(self.prompt, self.axes, self.config))
        except Exception as error:
            self.failed.emit(str(error))


class TranscriptionWorker(QObject):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, audio_bytes, engine):
        super().__init__()
        self.audio_bytes = audio_bytes
        self.engine = engine

    @Slot()
    def run(self):
        try:
            self.finished.emit(
                transcribe_audio(self.audio_bytes, filename="machine_builder_voice.wav", engine=self.engine)
            )
        except Exception as error:
            self.failed.emit(str(error))


class AIAssistantTab(QWidget):
    """Asistente por texto y voz. Las propuestas requieren aceptación explícita."""

    def __init__(self, configuration_provider, proposal_applier, parent=None):
        super().__init__(parent)
        self.configuration_provider = configuration_provider
        self.proposal_applier = proposal_applier
        self.pending_proposal = None
        self.thread = None
        self.worker = None
        self.recorder = MicrophoneRecorder()
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        chat = QGroupBox("Machine Builder Assistant")
        chat_layout = QVBoxLayout(chat)
        self.history = QTextBrowser()
        self.history.setPlaceholderText(
            "Puedes escribir o dictar una configuración completa de CPU, ejes y Robot Groups."
        )
        chat_layout.addWidget(self.history, 1)

        self.prompt = QPlainTextEdit()
        self.prompt.setPlaceholderText("Describe o dicta los cambios que quieres realizar...")
        self.prompt.setMaximumHeight(110)
        chat_layout.addWidget(self.prompt)

        voice_row = QHBoxLayout()
        self.record_button = QPushButton("🎤 Grabar")
        self.stop_button = QPushButton("■ Detener y transcribir")
        self.cancel_button = QPushButton("Cancelar grabación")
        self.stop_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.engine_combo = QComboBox()
        self.engine_combo.addItem("Whisper local", "local")
        self.engine_combo.addItem("OpenAI", "openai")
        self.auto_interpret = QCheckBox("Interpretar después de transcribir")
        self.auto_interpret.setChecked(True)
        self.recording_label = QLabel("Micrófono preparado")
        self.recording_label.setStyleSheet("color:#5b6475;")
        self.record_button.clicked.connect(self.start_recording)
        self.stop_button.clicked.connect(self.stop_recording)
        self.cancel_button.clicked.connect(self.cancel_recording)
        voice_row.addWidget(self.record_button)
        voice_row.addWidget(self.stop_button)
        voice_row.addWidget(self.cancel_button)
        voice_row.addSpacing(12)
        voice_row.addWidget(QLabel("Transcripción:"))
        voice_row.addWidget(self.engine_combo)
        voice_row.addWidget(self.auto_interpret)
        voice_row.addStretch()
        chat_layout.addLayout(voice_row)
        chat_layout.addWidget(self.recording_label)

        send_row = QHBoxLayout()
        self.source_label = QLabel("IA: OpenAI con respaldo local")
        self.source_label.setStyleSheet("color:#5b6475;")
        self.send_button = QPushButton("Interpretar propuesta")
        self.send_button.clicked.connect(self.interpret_prompt)
        send_row.addWidget(self.source_label)
        send_row.addStretch()
        send_row.addWidget(self.send_button)
        chat_layout.addLayout(send_row)
        root.addWidget(chat, 2)

        proposal = QGroupBox("Propuesta pendiente")
        proposal_layout = QVBoxLayout(proposal)
        self.proposal_text = QPlainTextEdit()
        self.proposal_text.setReadOnly(True)
        self.proposal_text.setPlaceholderText("No hay propuesta pendiente.")
        proposal_layout.addWidget(self.proposal_text)
        actions = QHBoxLayout()
        self.discard_button = QPushButton("Descartar")
        self.apply_button = QPushButton("Aplicar propuesta")
        self.discard_button.setEnabled(False)
        self.apply_button.setEnabled(False)
        self.discard_button.clicked.connect(self.discard_proposal)
        self.apply_button.clicked.connect(self.apply_proposal)
        actions.addStretch()
        actions.addWidget(self.discard_button)
        actions.addWidget(self.apply_button)
        proposal_layout.addLayout(actions)
        root.addWidget(proposal, 1)

    def start_recording(self):
        try:
            self.recorder.start()
            self.record_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.cancel_button.setEnabled(True)
            self.engine_combo.setEnabled(False)
            self.recording_label.setText("● Grabando... Habla con normalidad.")
            self.recording_label.setStyleSheet("color:#b42318;font-weight:700;")
        except Exception as error:
            QMessageBox.critical(self, "Micrófono", str(error))

    def stop_recording(self):
        try:
            audio_bytes = self.recorder.stop()
        except Exception as error:
            self._reset_voice_controls()
            QMessageBox.warning(self, "Grabación", str(error))
            return
        self.stop_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.recording_label.setText("Transcribiendo audio...")
        self.recording_label.setStyleSheet("color:#2446db;font-weight:600;")
        self._start_transcription(audio_bytes, self.engine_combo.currentData())

    def cancel_recording(self):
        self.recorder.cancel()
        self._reset_voice_controls()
        self.recording_label.setText("Grabación cancelada.")

    def _start_transcription(self, audio_bytes, engine):
        self.thread = QThread(self)
        self.worker = TranscriptionWorker(audio_bytes, engine)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._transcription_ready)
        self.worker.failed.connect(self._transcription_failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    @Slot(str)
    def _transcription_ready(self, text):
        self.prompt.setPlainText(text)
        self.history.append(f"<b>Transcripción:</b> {self._html(text)}")
        self.recording_label.setText("Transcripción completada.")
        self._reset_voice_controls(keep_status=True)
        if self.auto_interpret.isChecked():
            self.interpret_prompt()

    @Slot(str)
    def _transcription_failed(self, error):
        self.recording_label.setText("No se pudo transcribir.")
        self._reset_voice_controls(keep_status=True)
        QMessageBox.warning(self, "Transcripción", error)

    def _reset_voice_controls(self, keep_status=False):
        self.record_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.engine_combo.setEnabled(True)
        if not keep_status:
            self.recording_label.setStyleSheet("color:#5b6475;")

    def interpret_prompt(self):
        text = self.prompt.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Asistente IA", "Escribe o graba una instrucción.")
            return
        config = deepcopy(self.configuration_provider())
        axes = deepcopy(config.get("axes", []))
        self.history.append(f"<b>Tú:</b> {self._html(text)}")
        self.send_button.setEnabled(False)
        self.send_button.setText("Interpretando...")
        self.pending_proposal = None
        self.apply_button.setEnabled(False)
        self.discard_button.setEnabled(False)

        self.thread = QThread(self)
        self.worker = InterpretWorker(text, axes, config)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._proposal_ready)
        self.worker.failed.connect(self._proposal_failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    @Slot(dict)
    def _proposal_ready(self, result):
        self.pending_proposal = result
        summary = str(result.get("summary", "Propuesta preparada."))
        changes = [str(x) for x in result.get("changes", [])]
        warnings = [str(x) for x in result.get("warnings", [])]
        lines = [summary]
        if changes:
            lines += ["", "Cambios:"] + [f"• {x}" for x in changes]
        if warnings:
            lines += ["", "Avisos:"] + [f"• {x}" for x in warnings]
        self.proposal_text.setPlainText("\n".join(lines))
        self.history.append(f"<b>Asistente:</b> {self._html(summary)}")
        self.source_label.setText(f"Motor utilizado: {result.get('source', 'local')}")
        self.apply_button.setEnabled(True)
        self.discard_button.setEnabled(True)
        self._finish_interpretation()

    @Slot(str)
    def _proposal_failed(self, error):
        self.proposal_text.setPlainText("No se pudo preparar la propuesta:\n" + error)
        self.history.append(f"<b>Asistente:</b> Error: {self._html(error)}")
        self._finish_interpretation()

    def _finish_interpretation(self):
        self.send_button.setEnabled(True)
        self.send_button.setText("Interpretar propuesta")

    def apply_proposal(self):
        if not self.pending_proposal:
            return
        try:
            self.proposal_applier(deepcopy(self.pending_proposal))
            self.history.append("<b>Sistema:</b> Propuesta aplicada a la configuración.")
            self.prompt.clear()
            self.discard_proposal(announce=False)
        except Exception as error:
            QMessageBox.critical(self, "No se pudo aplicar", str(error))

    def discard_proposal(self, announce=True):
        self.pending_proposal = None
        self.proposal_text.clear()
        self.apply_button.setEnabled(False)
        self.discard_button.setEnabled(False)
        self.source_label.setText("IA: OpenAI con respaldo local")
        if announce:
            self.history.append("<b>Sistema:</b> Propuesta descartada.")

    def closeEvent(self, event):
        self.recorder.cancel()
        super().closeEvent(event)

    @staticmethod
    def _html(text):
        return (str(text).replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace("\n", "<br>"))
