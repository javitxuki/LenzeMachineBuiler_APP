# -*- coding: utf-8 -*-
import json
import subprocess
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths, QTimer
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from machine_builder_core import generate_plc_script, validate_config


DEFAULT_PLC_DESIGNER = Path(
    r"C:\Program Files\Lenze\PlcDesigner\4.2.0.41765"
    r"\PlcDesigner\Common\PlcDesigner.exe"
)
DEFAULT_SCRIPT_NAME = "MachineBuilder_Generated.py"
MAX_HISTORY_ENTRIES = 200


class GenerationTab(QWidget):
    """V0.8.2: generación y ejecución automática robusta en PLC Designer."""

    def __init__(self, configuration_provider, parent=None):
        super().__init__(parent)
        self.configuration_provider = configuration_provider
        self.generated_script = ""
        self.last_script_path = None
        self.settings = QSettings("Lenze", "MachineBuilderDesktop")
        self._verification_timer = QTimer(self)
        self._verification_timer.timeout.connect(self._check_project_created)
        self._expected_project_path = None
        self._verification_checks = 0
        self.history_entries = self._load_history()
        self._restore_last_script_path()
        self._build_ui()
        self._restore_last_script_preview()
        self._refresh_history_view()
        self._refresh_plc_status()
        self._trace("INFO", "Pestaña de generación V0.8.1 iniciada", persist=False)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        validation = QGroupBox("Validación y generación")
        validation_layout = QVBoxLayout(validation)
        self.validation_label = QLabel(
            "Pulsa Validar para comprobar la configuración completa."
        )
        self.validation_label.setWordWrap(True)
        validation_layout.addWidget(self.validation_label)

        buttons = QHBoxLayout()
        validate_button = QPushButton("Validar configuración")
        generate_button = QPushButton("Generar script PLC Designer")
        export_button = QPushButton("Guardar script como...")
        validate_button.clicked.connect(self.validate)
        generate_button.clicked.connect(self.generate)
        export_button.clicked.connect(self.export_script)
        buttons.addWidget(validate_button)
        buttons.addWidget(generate_button)
        buttons.addStretch()
        buttons.addWidget(export_button)
        validation_layout.addLayout(buttons)
        root.addWidget(validation)

        plc_group = QGroupBox("PLC Designer V0.8.2")
        plc_layout = QVBoxLayout(plc_group)
        plc_form = QFormLayout()

        self.plc_path_edit = QLineEdit(
            self.settings.value(
                "plcdesigner/executable",
                str(DEFAULT_PLC_DESIGNER),
                type=str,
            )
        )
        self.plc_path_edit.editingFinished.connect(self._save_plc_path)
        browse_plc_button = QPushButton("Examinar...")
        browse_plc_button.clicked.connect(self.browse_plcdesigner)
        executable_row = self._path_row(self.plc_path_edit, browse_plc_button)
        plc_form.addRow("Ejecutable", executable_row)

        default_script_dir = self._default_script_directory()
        self.script_directory_edit = QLineEdit(
            self.settings.value(
                "plcdesigner/script_directory",
                str(default_script_dir),
                type=str,
            )
        )
        self.script_directory_edit.editingFinished.connect(
            self._save_script_directory
        )
        browse_script_button = QPushButton("Examinar...")
        browse_script_button.clicked.connect(self.browse_script_directory)
        script_row = self._path_row(
            self.script_directory_edit,
            browse_script_button,
        )
        plc_form.addRow("Carpeta del script", script_row)
        plc_layout.addLayout(plc_form)

        self.plc_status_label = QLabel()
        self.plc_status_label.setWordWrap(True)
        plc_layout.addWidget(self.plc_status_label)

        plc_buttons = QHBoxLayout()
        open_button = QPushButton("Abrir PLC Designer")
        automatic_button = QPushButton("Generar y ejecutar proyecto PLC")
        open_folder_button = QPushButton("Abrir carpeta del script")
        open_button.clicked.connect(self.open_plcdesigner)
        automatic_button.clicked.connect(self.generate_and_open)
        open_folder_button.clicked.connect(self.open_script_directory)
        plc_buttons.addWidget(open_button)
        plc_buttons.addWidget(automatic_button)
        plc_buttons.addStretch()
        plc_buttons.addWidget(open_folder_button)
        plc_layout.addLayout(plc_buttons)
        root.addWidget(plc_group)

        content_row = QHBoxLayout()

        preview = QGroupBox("Vista previa del script generado")
        preview_layout = QVBoxLayout(preview)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText(
            "Aquí aparecerá el script para ejecutar en PLC Designer."
        )
        self.preview.setLineWrapMode(QPlainTextEdit.NoWrap)
        preview_layout.addWidget(self.preview)
        content_row.addWidget(preview, 2)

        trace_group = QGroupBox("Trazabilidad")
        trace_layout = QVBoxLayout(trace_group)
        self.history_view = QPlainTextEdit()
        self.history_view.setReadOnly(True)
        self.history_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.history_view.setPlaceholderText("El historial de operaciones aparecerá aquí.")
        trace_layout.addWidget(self.history_view)

        trace_buttons = QHBoxLayout()
        export_trace_button = QPushButton("Exportar historial...")
        clear_trace_button = QPushButton("Limpiar historial")
        export_trace_button.clicked.connect(self.export_history)
        clear_trace_button.clicked.connect(self.clear_history)
        trace_buttons.addWidget(export_trace_button)
        trace_buttons.addStretch()
        trace_buttons.addWidget(clear_trace_button)
        trace_layout.addLayout(trace_buttons)
        content_row.addWidget(trace_group, 1)

        root.addLayout(content_row, 1)

        help_label = QLabel(
            "V0.8.2: genera el script, inicia PLC Designer con --runscript y verifica "
            "la creación del proyecto. Si el proyecto ya existe permite sobrescribir, "
            "crear una copia numerada o cancelar."
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color:#5b6475;")
        root.addWidget(help_label)

    @staticmethod
    def _path_row(line_edit, button):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(line_edit, 1)
        layout.addWidget(button)
        return widget

    def current_configuration(self):
        return self.configuration_provider()

    def validate(self):
        try:
            errors = validate_config(self.current_configuration())
        except Exception as error:
            self._set_validation_error(str(error))
            self._trace("ERROR", f"Error durante la validación: {error}")
            return False

        if errors:
            self.validation_label.setText("⚠ " + "\n⚠ ".join(errors))
            self.validation_label.setStyleSheet(
                "color:#a13d00;font-weight:600;"
            )
            self._trace(
                "WARNING",
                "Validación con errores: " + " | ".join(errors),
            )
            return False

        self.validation_label.setText(
            "✓ Configuración válida para generar el script."
        )
        self.validation_label.setStyleSheet(
            "color:#16713b;font-weight:600;"
        )
        self._trace("SUCCESS", "Configuración validada correctamente")
        return True

    def generate(self):
        try:
            config = self.current_configuration()
            self.generated_script = generate_plc_script(config)
            self.preview.setPlainText(self.generated_script)
            self.validation_label.setText("✓ Script generado correctamente.")
            self.validation_label.setStyleSheet(
                "color:#16713b;font-weight:600;"
            )
            self._trace(
                "SUCCESS",
                f"Script generado en memoria ({len(self.generated_script)} caracteres)",
            )
            return True
        except Exception as error:
            self.generated_script = ""
            self.preview.clear()
            self._set_validation_error(str(error))
            self._trace("ERROR", f"No se pudo generar el script: {error}")
            QMessageBox.warning(
                self,
                "No se pudo generar el script",
                str(error),
            )
            return False

    def export_script(self):
        if not self.generated_script and not self.generate():
            return

        initial_path = self._script_directory() / DEFAULT_SCRIPT_NAME
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar script PLC Designer",
            str(initial_path),
            "Script Python (*.py)",
        )
        if not filename:
            self._trace("INFO", "Guardado manual del script cancelado")
            return
        if not filename.lower().endswith(".py"):
            filename += ".py"

        try:
            saved_path = self._write_script(Path(filename))
            self._trace("SUCCESS", f"Script guardado manualmente: {saved_path}")
            QMessageBox.information(
                self,
                "Script guardado",
                f"Script guardado en:\n{saved_path}",
            )
        except Exception as error:
            self._trace("ERROR", f"Error al guardar el script: {error}")
            QMessageBox.critical(self, "Error al guardar", str(error))

    def browse_plcdesigner(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar PlcDesigner.exe",
            self.plc_path_edit.text().strip(),
            "PLC Designer (PlcDesigner.exe);;Ejecutables (*.exe)",
        )
        if filename:
            self.plc_path_edit.setText(filename)
            self._save_plc_path()
            self._trace("INFO", f"Ruta de PLC Designer actualizada: {filename}")
            self._refresh_plc_status()

    def browse_script_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Seleccionar carpeta para el script",
            self.script_directory_edit.text().strip(),
        )
        if directory:
            self.script_directory_edit.setText(directory)
            self._save_script_directory()
            self._trace("INFO", f"Carpeta de scripts actualizada: {directory}")
            self._refresh_plc_status()

    def open_plcdesigner(self, show_success=True):
        executable = self._plc_executable()
        if not executable.is_file():
            message = f"No existe el ejecutable: {executable}"
            self._trace("ERROR", message)
            QMessageBox.critical(
                self,
                "PLC Designer no encontrado",
                message,
            )
            self._refresh_plc_status()
            return False

        try:
            subprocess.Popen(
                [str(executable)],
                cwd=str(executable.parent),
            )
            self.settings.setValue(
                "plcdesigner/last_opened_at",
                self._timestamp(),
            )
            self._trace("SUCCESS", f"PLC Designer iniciado: {executable}")
            if show_success:
                QMessageBox.information(
                    self,
                    "PLC Designer",
                    "PLC Designer se ha abierto correctamente.",
                )
            self._refresh_plc_status("PLC Designer iniciado.")
            return True
        except Exception as error:
            self._trace("ERROR", f"No se pudo abrir PLC Designer: {error}")
            QMessageBox.critical(
                self,
                "No se pudo abrir PLC Designer",
                str(error),
            )
            self._refresh_plc_status("Error al iniciar PLC Designer.")
            return False

    def generate_and_open(self):
        self._trace("INFO", "Inicio del flujo automático V0.8.2")

        original_config = self.current_configuration()
        config = deepcopy(original_config)
        errors = validate_config(config)
        if errors:
            self.validation_label.setText("⚠ " + "\n⚠ ".join(errors))
            self.validation_label.setStyleSheet("color:#a13d00;font-weight:600;")
            self._trace("WARNING", "Flujo detenido por validación: " + " | ".join(errors))
            return

        project_path = self._resolve_project_path(config)
        if project_path is None:
            self._trace("INFO", "Generación cancelada por el usuario")
            return
        config["project_path"] = str(project_path)

        try:
            self.generated_script = generate_plc_script(config)
            self.preview.setPlainText(self.generated_script)
            script_path = self._write_script(
                self._script_directory() / DEFAULT_SCRIPT_NAME
            )
            self._trace("SUCCESS", f"Script V0.8.2 guardado: {script_path}")
        except Exception as error:
            self._trace("ERROR", f"No se pudo generar o guardar el script: {error}")
            QMessageBox.critical(self, "No se pudo generar el script", str(error))
            return

        if not self._launch_plcdesigner_with_script(script_path):
            return

        self._expected_project_path = project_path
        self._verification_checks = 0
        self._verification_timer.start(1000)
        self.validation_label.setText(
            "PLC Designer está ejecutando el script. Verificando el proyecto..."
        )
        self.validation_label.setStyleSheet("color:#2446db;font-weight:600;")
        self._trace("INFO", f"Verificación iniciada para: {project_path}")

    def _resolve_project_path(self, config):
        raw_path = str(config.get("project_path", "")).strip()
        if not raw_path:
            QMessageBox.warning(
                self,
                "Ruta de proyecto vacía",
                "Define Project Path en la pestaña Controlador.",
            )
            return None

        project_path = Path(raw_path)
        if not project_path.exists():
            return project_path

        message = QMessageBox(self)
        message.setIcon(QMessageBox.Warning)
        message.setWindowTitle("El proyecto ya existe")
        message.setText(f"El proyecto ya existe:\n{project_path}")
        message.setInformativeText(
            "Elige si quieres sobrescribirlo, crear una copia numerada o cancelar."
        )
        overwrite_button = message.addButton("Sobrescribir", QMessageBox.DestructiveRole)
        copy_button = message.addButton("Crear copia", QMessageBox.AcceptRole)
        cancel_button = message.addButton("Cancelar", QMessageBox.RejectRole)
        message.setDefaultButton(copy_button)
        message.exec()

        clicked = message.clickedButton()
        if clicked is cancel_button:
            return None
        if clicked is copy_button:
            copy_path = self._next_project_copy(project_path)
            self._trace("INFO", f"Se usará una copia numerada: {copy_path}")
            return copy_path

        if clicked is overwrite_button:
            try:
                if project_path.is_dir():
                    raise IsADirectoryError(
                        "La ruta de proyecto es una carpeta; no se eliminará automáticamente."
                    )
                project_path.unlink()
                self._trace("INFO", f"Proyecto anterior eliminado: {project_path}")
                return project_path
            except Exception as error:
                QMessageBox.critical(
                    self,
                    "No se pudo sobrescribir",
                    f"No se pudo eliminar el proyecto existente:\n{error}",
                )
                self._trace("ERROR", f"No se pudo eliminar {project_path}: {error}")
                return None
        return None

    @staticmethod
    def _next_project_copy(project_path):
        parent = project_path.parent
        suffix = project_path.suffix or ".project"
        stem = project_path.stem
        index = 1
        while True:
            candidate = parent / f"{stem}_{index:03d}{suffix}"
            if not candidate.exists():
                return candidate
            index += 1

    def _launch_plcdesigner_with_script(self, script_path):
        executable = self._plc_executable()
        if not executable.is_file():
            message = f"No existe el ejecutable: {executable}"
            self._trace("ERROR", message)
            QMessageBox.critical(self, "PLC Designer no encontrado", message)
            return False
        if not Path(script_path).is_file():
            message = f"No existe el script: {script_path}"
            self._trace("ERROR", message)
            QMessageBox.critical(self, "Script no encontrado", message)
            return False

        command = [str(executable), f"--runscript={script_path}"]
        try:
            subprocess.Popen(command, cwd=str(executable.parent))
            self.settings.setValue("plcdesigner/last_opened_at", self._timestamp())
            self.settings.setValue("plcdesigner/last_runscript", str(script_path))
            self.settings.sync()
            self._trace("SUCCESS", "PLC Designer iniciado con --runscript")
            self._trace("INFO", "Comando: " + " ".join(command))
            return True
        except Exception as error:
            self._trace("ERROR", f"No se pudo ejecutar PLC Designer: {error}")
            QMessageBox.critical(
                self,
                "No se pudo ejecutar PLC Designer",
                str(error),
            )
            return False

    def _check_project_created(self):
        self._verification_checks += 1
        project_path = self._expected_project_path
        if project_path and Path(project_path).exists():
            self._verification_timer.stop()
            self.validation_label.setText(
                f"✓ Proyecto generado correctamente:\n{project_path}"
            )
            self.validation_label.setStyleSheet("color:#16713b;font-weight:600;")
            self._trace("SUCCESS", f"Proyecto verificado: {project_path}")
            self._refresh_plc_status(f"Proyecto generado: {project_path}")
            QMessageBox.information(
                self,
                "Proyecto PLC generado",
                f"El proyecto se ha creado correctamente:\n{project_path}",
            )
            self._expected_project_path = None
            return

        if self._verification_checks >= 120:
            self._verification_timer.stop()
            self.validation_label.setText(
                "No se ha podido verificar la creación del proyecto. "
                "Revisa los mensajes de PLC Designer y la trazabilidad."
            )
            self.validation_label.setStyleSheet("color:#a13d00;font-weight:600;")
            self._trace(
                "WARNING",
                f"No se verificó el proyecto esperado: {project_path}",
            )
            self._expected_project_path = None

    def open_script_directory(self):
        directory = self._script_directory()
        try:
            directory.mkdir(parents=True, exist_ok=True)
            subprocess.Popen(["explorer", str(directory)])
            self._trace("INFO", f"Carpeta de scripts abierta: {directory}")
        except Exception as error:
            self._trace("ERROR", f"No se pudo abrir la carpeta: {error}")
            QMessageBox.critical(
                self,
                "No se pudo abrir la carpeta",
                str(error),
            )

    def export_history(self):
        default_name = self._trace_directory() / "MachineBuilder_Trace.log"
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar historial",
            str(default_name),
            "Archivo de log (*.log);;Archivo de texto (*.txt)",
        )
        if not filename:
            return
        try:
            Path(filename).write_text(
                self._history_as_text(),
                encoding="utf-8",
            )
            self._trace("SUCCESS", f"Historial exportado: {filename}")
        except Exception as error:
            QMessageBox.critical(self, "Error al exportar", str(error))

    def clear_history(self):
        answer = QMessageBox.question(
            self,
            "Limpiar historial",
            "¿Quieres eliminar todo el historial de trazabilidad?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.history_entries = []
        self._save_history()
        self._refresh_history_view()
        self._trace("INFO", "Historial reiniciado")

    def _plc_executable(self):
        return Path(self.plc_path_edit.text().strip()).expanduser()

    def _script_directory(self):
        text = self.script_directory_edit.text().strip()
        directory = Path(text or str(self._default_script_directory())).expanduser()
        return directory

    @staticmethod
    def _default_script_directory():
        documents = QStandardPaths.writableLocation(
            QStandardPaths.DocumentsLocation
        )
        base = Path(documents) if documents else Path.home()
        return base / "LenzeMachineBuilder"

    @staticmethod
    def _trace_directory():
        app_data = QStandardPaths.writableLocation(
            QStandardPaths.AppDataLocation
        )
        base = Path(app_data) if app_data else Path.home() / ".lenze_machine_builder"
        return base / "logs"

    def _write_script(self, destination):
        if not self.generated_script:
            raise ValueError("No hay ningún script generado.")
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            self.generated_script,
            encoding="ascii",
            errors="strict",
        )
        self.last_script_path = destination
        self.settings.setValue("plcdesigner/last_script", str(destination))
        self.settings.setValue(
            "plcdesigner/last_script_at",
            self._timestamp(),
        )
        self.settings.sync()
        self._refresh_plc_status()
        return destination

    def _restore_last_script_path(self):
        value = self.settings.value(
            "plcdesigner/last_script",
            "",
            type=str,
        )
        if value:
            self.last_script_path = Path(value)

    def _restore_last_script_preview(self):
        if not self.last_script_path or not self.last_script_path.is_file():
            return
        try:
            self.generated_script = self.last_script_path.read_text(
                encoding="ascii"
            )
            self.preview.setPlainText(self.generated_script)
        except Exception:
            self.generated_script = ""

    def _save_plc_path(self):
        self.settings.setValue(
            "plcdesigner/executable",
            self.plc_path_edit.text().strip(),
        )
        self.settings.sync()
        self._refresh_plc_status()

    def _save_script_directory(self):
        self.settings.setValue(
            "plcdesigner/script_directory",
            self.script_directory_edit.text().strip(),
        )
        self.settings.sync()
        self._refresh_plc_status()

    def _set_validation_error(self, message):
        self.validation_label.setText("⚠ " + message)
        self.validation_label.setStyleSheet(
            "color:#a13d00;font-weight:600;"
        )

    def _refresh_plc_status(self, extra_message=""):
        if not hasattr(self, "plc_status_label"):
            return
        executable = self._plc_executable()
        script_directory = self._script_directory()

        if executable.is_file():
            status = "✓ Ejecutable de PLC Designer localizado."
            colour = "#16713b"
        else:
            status = "⚠ No se encuentra PlcDesigner.exe en la ruta configurada."
            colour = "#a13d00"

        status += f"\nCarpeta del script: {script_directory}"
        if self.last_script_path:
            status += f"\nÚltimo script: {self.last_script_path}"
        last_script_at = self.settings.value(
            "plcdesigner/last_script_at",
            "",
            type=str,
        )
        if last_script_at:
            status += f"\nÚltima generación: {last_script_at}"
        if extra_message:
            status += f"\n{extra_message}"

        self.plc_status_label.setText(status)
        self.plc_status_label.setStyleSheet(
            f"color:{colour};font-weight:600;"
        )

    def _trace(self, level, message, persist=True):
        entry = {
            "timestamp": self._timestamp(),
            "level": str(level),
            "message": str(message),
        }
        self.history_entries.append(entry)
        self.history_entries = self.history_entries[-MAX_HISTORY_ENTRIES:]
        if persist:
            self._save_history()
            self._append_trace_file(entry)
        if hasattr(self, "history_view"):
            self._refresh_history_view()

    def _load_history(self):
        raw = self.settings.value(
            "trace/history",
            "[]",
            type=str,
        )
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data[-MAX_HISTORY_ENTRIES:]
        except Exception:
            pass
        return []

    def _save_history(self):
        self.settings.setValue(
            "trace/history",
            json.dumps(self.history_entries, ensure_ascii=False),
        )
        self.settings.sync()

    def _append_trace_file(self, entry):
        try:
            directory = self._trace_directory()
            directory.mkdir(parents=True, exist_ok=True)
            log_path = directory / "MachineBuilder_Trace.log"
            line = self._format_history_entry(entry) + "\n"
            with log_path.open("a", encoding="utf-8") as stream:
                stream.write(line)
        except Exception:
            pass

    def _refresh_history_view(self):
        self.history_view.setPlainText(self._history_as_text())
        scroll_bar = self.history_view.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())

    def _history_as_text(self):
        return "\n".join(
            self._format_history_entry(entry)
            for entry in self.history_entries
        )

    @staticmethod
    def _format_history_entry(entry):
        return (
            f"{entry.get('timestamp', '')} "
            f"[{entry.get('level', 'INFO')}] "
            f"{entry.get('message', '')}"
        )

    @staticmethod
    def _timestamp():
        return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
