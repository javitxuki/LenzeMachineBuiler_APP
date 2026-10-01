# -*- coding: utf-8 -*-
"""Genera ui/robot_groups_tab_v092.py desde ui/robot_groups_tab.py actual."""
from pathlib import Path
import shutil

source = Path("ui/robot_groups_tab.py")
target = Path("ui/robot_groups_tab_v092.py")
if not source.is_file():
    raise SystemExit("No se encuentra ui/robot_groups_tab.py")
text = source.read_text(encoding="utf-8")

text = text.replace(
    "from copy import deepcopy\n",
    "from copy import deepcopy\nfrom pathlib import Path\nimport sys\n",
    1,
)
text = text.replace(
    "from PySide6.QtCore import Qt\n",
    "from PySide6.QtCore import Qt\nfrom PySide6.QtGui import QPixmap\n",
    1,
)

mapping = '''\nROBOT_IMAGES = {
    "CARTESIAN_2D": "Cartesian_2D.png",
    "CARTESIAN_3D": "Cartesian_3D.png",
    "CARTESIAN_4D": "Cartesian_4D.png",
    "PORTAL_AC_5DOF": "Portal_AC_5DOF.png",
    "BELT_2DOF": "Belt_2DOF.png",
    "SCARA_3DOF": "Scara_3DOF.png",
    "SCARA": "Scara_4DOF.png",
    "DELTA_2DOF": "Delta_2DOF.png",
    "DELTA": "Delta_3DOF.png",
    "DELTA_4DOF": "Delta_4DOF.png",
    "DELTA_5DOF": "Delta_5DOF.png",
    "LINEAR_DELTA_3DOF": "Linear_Delta_3DOF.png",
    "LINEAR_DELTA_4DOF": "Linear_Delta_4DOF.png",
    "ARTICULATED_4DOF": "Articulated_4DOF.png",
    "ARTICULATED_LINEAR_A1_4DOF": "Articulated_Linear_A1_4DOF.png",
}
'''
if "ROBOT_IMAGES = {" not in text:
    marker = "\nclass RobotGroupsTab(QWidget):"
    if marker not in text:
        raise SystemExit("No se encuentra class RobotGroupsTab")
    text = text.replace(marker, mapping + marker, 1)

preview_ui = '''        self.preview_group = QGroupBox("Vista previa del Robot")
        preview_layout = QVBoxLayout(self.preview_group)
        self.robot_image_label = QLabel("Imagen no disponible")
        self.robot_image_label.setAlignment(Qt.AlignCenter)
        self.robot_image_label.setMinimumHeight(260)
        self.robot_image_label.setStyleSheet(
            "QLabel { background:#ffffff; border:1px solid #d7dce5; "
            "border-radius:6px; color:#6b7280; padding:8px; }"
        )
        preview_layout.addWidget(self.robot_image_label)
        right_layout.addWidget(self.preview_group)

'''
anchor = '        right_layout.addWidget(self.general_group)\n'
if "self.preview_group = QGroupBox" not in text:
    if anchor not in text:
        raise SystemExit("No se encuentra el bloque general_group")
    text = text.replace(anchor, anchor + preview_ui, 1)

text = text.replace(
    "        self.axes_group.setVisible(not empty)\n",
    "        self.axes_group.setVisible(not empty)\n        self.preview_group.setVisible(not empty)\n",
    1,
)
text = text.replace(
    "            self.device_label.clear()\n",
    "            self.device_label.clear()\n            self.robot_image_label.clear()\n",
    1,
)
text = text.replace(
    "        self.update_device_label()\n        self.loading = False\n",
    "        self.update_device_label()\n        self.update_robot_preview()\n        self.loading = False\n",
    1,
)
text = text.replace(
    "        self.update_device_label()\n        self.store_current()\n",
    "        self.update_device_label()\n        self.update_robot_preview()\n        self.store_current()\n",
    1,
)

methods = '''\n    @staticmethod
    def _application_root():
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parent.parent

    def robot_image_path(self, kind):
        filename = ROBOT_IMAGES.get(kind, "")
        if not filename:
            return None
        candidates = [
            self._application_root() / "resources" / "robots" / filename,
            Path(__file__).resolve().parent / "resources" / "robots" / filename,
            Path.cwd() / "resources" / "robots" / filename,
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return candidates[0]

    def update_robot_preview(self):
        kind = self.type_combo.currentData()
        image_path = self.robot_image_path(kind)
        if not image_path or not image_path.is_file():
            self.robot_image_label.setPixmap(QPixmap())
            self.robot_image_label.setText(
                "Imagen no disponible para " + ROBOT_LABELS.get(kind, str(kind))
            )
            self.robot_image_label.setToolTip(str(image_path or ""))
            return

        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            self.robot_image_label.setPixmap(QPixmap())
            self.robot_image_label.setText("No se pudo cargar la imagen")
            self.robot_image_label.setToolTip(str(image_path))
            return

        target = self.robot_image_label.size()
        if target.width() < 100 or target.height() < 100:
            target = self.robot_image_label.minimumSize()
        scaled = pixmap.scaled(
            target,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.robot_image_label.setText("")
        self.robot_image_label.setPixmap(scaled)
        self.robot_image_label.setToolTip(
            ROBOT_LABELS.get(kind, str(kind)) + "\\n" + str(image_path)
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "robot_image_label") and self.robot_image_label.isVisible():
            self.update_robot_preview()
'''
insert_before = "\n    def validation_errors(self):"
if "def update_robot_preview(self):" not in text:
    if insert_before not in text:
        raise SystemExit("No se encuentra validation_errors")
    text = text.replace(insert_before, methods + insert_before, 1)

compile(text, str(target), "exec")
target.write_text(text, encoding="utf-8")
print("Generado:", target)
