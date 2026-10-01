# -*- coding: utf-8 -*-
import json
from copy import deepcopy
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import (QCheckBox,QComboBox,QDoubleSpinBox,QFileDialog,QFormLayout,QFrame,QGridLayout,QGroupBox,QHBoxLayout,QLabel,QLineEdit,QListWidget,QMainWindow,QMessageBox,QPushButton,QSpinBox,QStatusBar,QTabWidget,QVBoxLayout,QWidget)
from ui.robot_groups_tab import RobotGroupsTab
from ui.generation_tab import GenerationTab
from ui.ai_assistant_tab import AIAssistantTab
from machine_builder_core import (CPU_MODELS,DRIVES,I950_VARIANTS,KINEMATICS,SAFETY,TRAVERSING,calculate_feed_constant,cpu_options,drive_options,load_repository,master_options,normalize_axis)



class VisibleSpinBox(QSpinBox):
    """SpinBox entero con botones visibles e independientes del tema de Windows."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setButtonSymbols(QSpinBox.NoButtons)
        self._up_button = QPushButton("▲", self)
        self._down_button = QPushButton("▼", self)
        for button in (self._up_button, self._down_button):
            button.setObjectName("spinArrowButton")
            button.setFocusPolicy(Qt.NoFocus)
        self._up_button.clicked.connect(self.stepUp)
        self._down_button.clicked.connect(self.stepDown)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        button_width = 26
        half_height = self.height() // 2
        self._up_button.setGeometry(
            self.width() - button_width, 0, button_width, half_height
        )
        self._down_button.setGeometry(
            self.width() - button_width,
            half_height,
            button_width,
            self.height() - half_height,
        )


class VisibleDoubleSpinBox(QDoubleSpinBox):
    """SpinBox decimal con botones visibles e independientes del tema de Windows."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self._up_button = QPushButton("▲", self)
        self._down_button = QPushButton("▼", self)
        for button in (self._up_button, self._down_button):
            button.setObjectName("spinArrowButton")
            button.setFocusPolicy(Qt.NoFocus)
        self._up_button.clicked.connect(self.stepUp)
        self._down_button.clicked.connect(self.stepDown)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        button_width = 26
        half_height = self.height() // 2
        self._up_button.setGeometry(
            self.width() - button_width, 0, button_width, half_height
        )
        self._down_button.setGeometry(
            self.width() - button_width,
            half_height,
            button_width,
            self.height() - half_height,
        )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.base=Path(__file__).resolve().parent.parent
        self.repo=load_repository(self.base/'device_repository.json'); self.config_file=None
        self.axes=[]; self.axis_index=-1; self.loading_axis=False
        self.setWindowTitle('Lenze Machine Builder Desktop'); self.resize(1500,900)
        self._menu(); self._ui(); self._style(); self.setStatusBar(QStatusBar(self))
        self.refresh_cpu(); self.refresh_master(); self.add_axis()

    def _menu(self):
        m=self.menuBar().addMenu('Archivo')
        for text,shortcut,slot in [('Nuevo','Ctrl+N',self.new_config),('Abrir configuración...','Ctrl+O',self.open_config),('Guardar configuración...','Ctrl+S',self.save_config)]:
            a=QAction(text,self); a.setShortcut(shortcut); a.triggered.connect(slot); m.addAction(a)
        m.addSeparator(); a=QAction('Salir',self); a.triggered.connect(self.close); m.addAction(a)

    def _ui(self):
        c=QWidget(); self.setCentralWidget(c); root=QVBoxLayout(c)

        # Cabecera: logo a la izquierda y titulo realmente centrado.
        header=QFrame(); header.setObjectName('card')
        h=QGridLayout(header); h.setContentsMargins(18,10,18,10)
        logo=QLabel(); p=self.base/'Lenze.png'
        if p.exists():
            logo.setPixmap(QPixmap(str(p)).scaledToHeight(60,Qt.SmoothTransformation))
        logo.setMinimumWidth(230)
        title=QLabel('Lenze Machine Builder Desktop')
        title.setObjectName('title'); title.setAlignment(Qt.AlignCenter)
        right_spacer=QWidget(); right_spacer.setMinimumWidth(230)
        h.addWidget(logo,0,0,Qt.AlignLeft|Qt.AlignVCenter)
        h.addWidget(title,0,1,Qt.AlignCenter)
        h.addWidget(right_spacer,0,2)
        h.setColumnStretch(1,1)
        root.addWidget(header)

        self.tabs=QTabWidget(); root.addWidget(self.tabs,1)
        self.controller=QWidget(); self.axes_page=QWidget(); self.robot_groups_page=RobotGroupsTab(self.active_axis_names); self.generation_page=GenerationTab(self.config); self.ai_page=AIAssistantTab(self.config, self.apply_ai_proposal)
        self.tabs.addTab(self.controller,'⚙ Controlador')
        self.tabs.addTab(self.axes_page,'🔧 Ejes')
        self.tabs.addTab(self.robot_groups_page,'🤖 Robot Groups')
        self.tabs.addTab(self.generation_page,'💾 Validar y generar')
        self.tabs.addTab(self.ai_page,'✨ Asistente IA')
        self._controller_ui(); self._axes_ui()

    def _controller_ui(self):
        out=QVBoxLayout(self.controller); card=QFrame(); card.setObjectName('card'); f=QFormLayout(card)
        self.cpu=QComboBox(); self.cpu.addItems(CPU_MODELS); self.cpu.setCurrentText('c550'); self.cpu.currentTextChanged.connect(self.refresh_cpu)
        self.cpu_desc=QComboBox(); self.master_desc=QComboBox(); self.project=QLineEdit(r'C:\Temp\LenzeMachine_Auto.project')
        browse=QPushButton('Examinar...'); browse.clicked.connect(self.browse_project); row=QWidget(); rh=QHBoxLayout(row); rh.setContentsMargins(0,0,0,0); rh.addWidget(self.project,1); rh.addWidget(browse)
        f.addRow('CPU',self.cpu); f.addRow('Descriptor CPU',self.cpu_desc); f.addRow('EtherCAT Master',self.master_desc); f.addRow('Project Path',row)
        out.addWidget(card); out.addStretch()

    def _axes_ui(self):
        root=QHBoxLayout(self.axes_page)
        root.setContentsMargins(16,16,16,16); root.setSpacing(14)

        left=QGroupBox('Ejes configurados')
        left.setMinimumWidth(250); left.setMaximumWidth(340)
        lv=QVBoxLayout(left)
        self.axis_list=QListWidget()
        self.axis_list.currentRowChanged.connect(self.select_axis)
        lv.addWidget(self.axis_list,1)
        br=QHBoxLayout()
        add=QPushButton('+ Añadir eje'); rem=QPushButton('- Eliminar eje')
        add.clicked.connect(self.add_axis); rem.clicked.connect(self.remove_axis)
        br.addWidget(add); br.addWidget(rem); lv.addLayout(br)
        root.addWidget(left)

        editor=QWidget(); editor_layout=QVBoxLayout(editor)
        editor_layout.setContentsMargins(0,0,0,0); editor_layout.setSpacing(12)

        # Datos generales
        general=QGroupBox('Datos generales del eje')
        fg=QFormLayout(general)
        fg.setLabelAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.enabled=QCheckBox('Eje activo')
        self.name=QLineEdit()
        fg.addRow(self._field_label('Estado'),self.enabled)
        fg.addRow(self._field_label('Nombre IEC'),self.name)

        # Drive y EtherCAT
        ethercat=QGroupBox('Drive y configuración EtherCAT')
        fe=QFormLayout(ethercat); fe.setLabelAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.drive=QComboBox(); self.drive.addItems(DRIVES)
        self.safety=QComboBox(); self.safety.addItems(SAFETY)
        self.variant=QComboBox(); self.variant.addItems(I950_VARIANTS)
        self.drive_desc=QComboBox()
        self.alias=VisibleSpinBox(); self.alias.setRange(0,65535)
        self.alias2=VisibleSpinBox(); self.alias2.setRange(0,65535)
        self.motor=QLineEdit()
        for label,w in [('Drive',self.drive),('Safety',self.safety),('Variante i950',self.variant),
                        ('Descriptor del drive',self.drive_desc),('Station Alias',self.alias),
                        ('Second Station Alias',self.alias2),('Código de motor C86',self.motor)]:
            fe.addRow(self._field_label(label),w)

        # Cinematica
        motion=QGroupBox('Cinemática y recorrido')
        fm=QFormLayout(motion); fm.setLabelAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.kin=QComboBox(); self.kin.addItems(KINEMATICS)
        self.kparam=self._dspin()
        self.travel=QComboBox(); self.travel.addItems(TRAVERSING)
        self.feed=self._dspin(); self.cycle=self._dspin()
        calc=QPushButton('Calcular Feed Constant desde la cinemática')
        calc.clicked.connect(self.calc_feed)
        fm.addRow(self._field_label('Tipo de cinemática'),self.kin)
        fm.addRow(self._field_label('Parámetro cinemático'),self.kparam)
        fm.addRow(self._field_label('Tipo de recorrido'),self.travel)
        fm.addRow(self._field_label('Feed Constant'),self.feed)
        fm.addRow(QLabel(''),calc)
        fm.addRow(self._field_label('Cycle Length'),self.cycle)

        # Relaciones mecanicas
        gears=QGroupBox('Relaciones mecánicas')
        grid=QGridLayout(gears)
        self.z1=self._ispin(); self.z2=self._ispin(); self.z3=self._ispin(); self.z4=self._ispin()
        grid.addWidget(self._field_label('Z1'),0,0); grid.addWidget(self.z1,0,1)
        grid.addWidget(self._field_label('Z2'),0,2); grid.addWidget(self.z2,0,3)
        grid.addWidget(self._field_label('Z3'),1,0); grid.addWidget(self.z3,1,1)
        grid.addWidget(self._field_label('Z4'),1,2); grid.addWidget(self.z4,1,3)
        grid.setColumnStretch(1,1); grid.setColumnStretch(3,1)

        top=QHBoxLayout(); top.addWidget(general,1); top.addWidget(ethercat,2)
        editor_layout.addLayout(top)
        bottom=QHBoxLayout(); bottom.addWidget(motion,2); bottom.addWidget(gears,1)
        editor_layout.addLayout(bottom)
        editor_layout.addStretch()
        root.addWidget(editor,1)

        self.drive.currentTextChanged.connect(self.filter_changed)
        self.safety.currentTextChanged.connect(self.filter_changed)
        self.variant.currentTextChanged.connect(self.filter_changed)
        self.kin.currentTextChanged.connect(self.visibility)
        self.travel.currentTextChanged.connect(self.visibility)
        for w in [self.enabled,self.name,self.drive,self.safety,self.variant,self.drive_desc,self.alias,
                  self.alias2,self.motor,self.kin,self.kparam,self.z1,self.z2,self.z3,self.z4,
                  self.travel,self.feed,self.cycle]:
            sig=w.currentIndexChanged if isinstance(w,QComboBox) else w.textChanged if isinstance(w,QLineEdit) else w.toggled if isinstance(w,QCheckBox) else w.valueChanged
            sig.connect(self.store_axis)

    @staticmethod
    def _field_label(text):
        label=QLabel(text)
        label.setObjectName('fieldLabel')
        label.setMinimumWidth(135)
        return label

    def _dspin(self):
        s=VisibleDoubleSpinBox()
        s.setRange(.000001,1e9)
        s.setDecimals(6)
        return s

    def _ispin(self):
        s=VisibleSpinBox()
        s.setRange(1,1000000000)
        s.setValue(1)
        return s
    def _fill(self,combo,items,preferred=''):
        combo.blockSignals(True); combo.clear(); idx=0
        for i,x in enumerate(items): combo.addItem(f"{x.get('name','')} [{x.get('version','')}]",x); idx=i if x.get('device_id')==preferred else idx
        if items: combo.setCurrentIndex(idx)
        else: combo.addItem('Sin descriptor disponible',{})
        combo.blockSignals(False)
    def refresh_cpu(self,*_): self._fill(self.cpu_desc,cpu_options(self.repo,self.cpu.currentText()))
    def refresh_master(self): self._fill(self.master_desc,master_options(self.repo))
    def filter_changed(self,*_):
        old=self._device(self.drive_desc); self._fill(self.drive_desc,drive_options(self.repo,self.drive.currentText(),self.safety.currentText(),self.variant.currentText()),old); self.visibility(); self.store_axis()
    def _device(self,c):
        d=c.currentData(); return d.get('device_id','') if isinstance(d,dict) else ''
    def visibility(self,*_): self.safety.setEnabled(self.drive.currentText()!='i550'); self.variant.setEnabled(self.drive.currentText()=='i950'); self.kparam.setEnabled(self.kin.currentText()!='ROTARY'); self.cycle.setEnabled(self.travel.currentText()=='MODULO')
    def add_axis(self):
        # Guarda correctamente el eje actualmente seleccionado.
        self.store_axis()

        new_index = len(self.axes) + 1
        axis = normalize_axis({}, new_index)

        # Asigna inmediatamente el primer descriptor compatible.
        options = drive_options(
            self.repo,
            axis["drive_type"],
            axis["safety_variant"],
            axis["i950_variant"],
        )

        if options:
            descriptor = options[0]

            axis["device_id"] = descriptor.get(
                "device_id",
                ""
            )

            axis["descriptor_label"] = (
                f"{descriptor.get('name', '')} "
                f"[{descriptor.get('version', '')}]"
            )
        else:
            axis["device_id"] = ""
            axis["descriptor_label"] = ""

        self.axes.append(axis)

        new_row = len(self.axes) - 1

        # Reconstruye la lista.
        self.refresh_axis_list(
            selected_row=new_row
        )

        # La selección se hizo con señales bloqueadas.
        # Cargamos explícitamente el eje en el editor.
        self.select_axis(new_row)

        if hasattr(self, "robot_groups_page"):
            self.robot_groups_page.refresh_axes()

    def remove_axis(self):
        row = self.axis_list.currentRow()
        if row < 0 or row >= len(self.axes):
            return

        self.store_axis()
        self.axes.pop(row)
        self.axis_index = -1

        if not self.axes:
            self.add_axis()
            return

        target_row = min(row, len(self.axes) - 1)
        self.refresh_axis_list(selected_row=target_row)
        self.axis_list.setCurrentRow(target_row)

        if hasattr(self, "robot_groups_page"):
            self.robot_groups_page.refresh_axes()

    def refresh_axis_list(self, selected_row=None):
        if selected_row is None:
            selected_row = self.axis_index

        self.axis_list.blockSignals(True)
        self.axis_list.clear()
        for axis in self.axes:
            prefix = "● " if axis.get("enabled", True) else "○ "
            self.axis_list.addItem(prefix + axis.get("name", "Axis"))

        if 0 <= selected_row < len(self.axes):
            self.axis_list.setCurrentRow(selected_row)
        self.axis_list.blockSignals(False)

    def select_axis(self, row):
        if self.loading_axis:
            return

        # Guarda el eje anterior antes de cambiar el índice activo.
        self.store_axis()

        if row < 0 or row >= len(self.axes):
            self.axis_index = -1
            return

        self.axis_index = row
        axis = self.axes[row]
        self.loading_axis = True
        try:
            self.enabled.setChecked(axis["enabled"])
            self.name.setText(axis["name"])
            self.drive.setCurrentText(axis["drive_type"])
            self.safety.setCurrentText(axis["safety_variant"])
            self.variant.setCurrentText(axis["i950_variant"])
            self.alias.setValue(axis["station_alias"])
            self.alias2.setValue(axis["second_station_alias"])
            self.motor.setText(axis["motor_code_c86"])
            self.kin.setCurrentText(axis["kinematics"])
            self.kparam.setValue(axis["kinematic_parameter"])
            self.z1.setValue(axis["z1"])
            self.z2.setValue(axis["z2"])
            self.z3.setValue(axis["z3"])
            self.z4.setValue(axis["z4"])
            self.travel.setCurrentText(axis["traversing_range"])
            self.feed.setValue(axis["feed_constant"])
            self.cycle.setValue(axis["cycle_length"])
            self._fill(
                self.drive_desc,
                drive_options(
                    self.repo,
                    self.drive.currentText(),
                    self.safety.currentText(),
                    self.variant.currentText(),
                ),
                axis.get("device_id", ""),
            )
            self.visibility()
        finally:
            self.loading_axis = False

    def store_axis(self, *_):
        if self.loading_axis or self.axis_index < 0 or self.axis_index >= len(self.axes):
            return

        axis = self.axes[self.axis_index]
        selected_device_id = self._device(
            self.drive_desc
        )

        # Si el combo aún no tiene datos válidos, conserva
        # el descriptor previamente guardado.
        if not selected_device_id:
            selected_device_id = axis.get(
                "device_id",
                ""
            )
        axis.update(
            enabled=self.enabled.isChecked(),
            name=self.name.text().strip(),
            drive_type=self.drive.currentText(),
            safety_variant=self.safety.currentText(),
            i950_variant=self.variant.currentText(),
            descriptor_label=self.drive_desc.currentText(),
            device_id=selected_device_id,
            station_alias=self.alias.value(),
            second_station_alias=self.alias2.value(),
            motor_code_c86=self.motor.text(),
            kinematics=self.kin.currentText(),
            kinematic_parameter=self.kparam.value(),
            z1=self.z1.value(),
            z2=self.z2.value(),
            z3=self.z3.value(),
            z4=self.z4.value(),
            traversing_range=self.travel.currentText(),
            feed_constant=self.feed.value(),
            cycle_length=self.cycle.value(),
        )
        self.refresh_axis_list(selected_row=self.axis_index)

        if hasattr(self, "robot_groups_page"):
            self.robot_groups_page.refresh_axes()

    def active_axis_names(self):
        # No llama a store_axis para evitar recursión al refrescar Robot Groups.
        return [
            axis.get("name", "")
            for axis in self.axes
            if axis.get("enabled", True) and axis.get("name", "").strip()
        ]

    def calc_feed(self):
        try: self.feed.setValue(calculate_feed_constant(self.kin.currentText(),self.kparam.value()))
        except Exception as e: QMessageBox.warning(self,'Error',str(e))
    def config(self):
        self.store_axis(); c=self.cpu_desc.currentData() or {}; m=self.master_desc.currentData() or {}; return {'format':'LenzeMachineBuilderDesktop','format_version':2,'cpu_model':self.cpu.currentText(),'cpu_version':c.get('version',''),'cpu_device_id':c.get('device_id',''),'ethercat_master_version':m.get('version',''),'ethercat_master_device_id':m.get('device_id',''),'project_path':self.project.text().strip(),'axes':deepcopy(self.axes),'robot_groups':self.robot_groups_page.configuration()}
    def load_config(self,c):
        self.cpu.setCurrentText(c.get('cpu_model','c550')); self.refresh_cpu(); self._fill(self.cpu_desc,cpu_options(self.repo,self.cpu.currentText()),c.get('cpu_device_id','')); self._fill(self.master_desc,master_options(self.repo),c.get('ethercat_master_device_id','')); self.project.setText(c.get('project_path',r'C:\Temp\LenzeMachine_Auto.project')); self.axes=[normalize_axis(a,i) for i,a in enumerate(c.get('axes',[]),1)] or [normalize_axis({},1)]; self.axis_index=-1; self.refresh_axis_list(); self.axis_list.setCurrentRow(0); self.robot_groups_page.load_configuration(c.get('robot_groups',[]))
    def apply_ai_proposal(self, proposal):
        current = self.config()
        proposed_axes = proposal.get("axes")
        if isinstance(proposed_axes, list) and proposed_axes:
            current["axes"] = proposed_axes
        cpu_model = proposal.get("cpu_model")
        if cpu_model in CPU_MODELS:
            current["cpu_model"] = cpu_model
        proposed_groups = proposal.get("robot_groups")
        if isinstance(proposed_groups, list):
            current["robot_groups"] = proposed_groups
        # Conserva descriptores, ruta y Robot Groups salvo que la propuesta los incluya.
        self.load_config(current)
        self.tabs.setCurrentWidget(self.axes_page)
        self.tabs.setCurrentWidget(self.robot_groups_page)
        self.statusBar().showMessage("Propuesta del asistente aplicada")

    def new_config(self): self.load_config({})
    def open_config(self):
        fn,_=QFileDialog.getOpenFileName(self,'Abrir configuración','','JSON (*.json)')
        if fn:
            try: self.load_config(json.loads(Path(fn).read_text(encoding='utf-8'))); self.config_file=Path(fn)
            except Exception as e: QMessageBox.critical(self,'Error',str(e))
    def save_config(self):
        fn,_=QFileDialog.getSaveFileName(self,'Guardar configuración',str(self.config_file or 'machine_configuration.json'),'JSON (*.json)')
        if fn:
            if not fn.lower().endswith('.json'): fn+='.json'
            Path(fn).write_text(json.dumps(self.config(),indent=2,ensure_ascii=False),encoding='utf-8'); self.config_file=Path(fn)
    def browse_project(self):
        fn,_=QFileDialog.getSaveFileName(self,'Ruta del proyecto',self.project.text(),'Proyecto (*.project)')
        if fn: self.project.setText(fn if fn.lower().endswith('.project') else fn+'.project')
    def _style(self):
        self.setStyleSheet("""
        QMainWindow { background:#f5f7fb; }
        QFrame#card { background:white; border:1px solid #d8dee9; border-radius:8px; }
        QLabel { color:#172033; }
        QLabel#title { font-size:24px; font-weight:700; color:#172033; }
        QLabel#fieldLabel { color:#172033; font-size:10pt; font-weight:600; }
        QGroupBox {
            background:#ffffff; color:#172033; font-weight:700;
            border:1px solid #c9d1de; border-radius:8px;
            margin-top:12px; padding-top:12px;
        }
        QGroupBox::title {
            subcontrol-origin:margin; subcontrol-position:top left;
            left:12px; padding:0 7px; background:#ffffff; color:#2446db;
        }
        QTabWidget::pane { border:1px solid #c9d1de; background:#f5f7fb; }
        QTabBar::tab { color:#172033; background:#e8ecf3; padding:8px 18px; }
        QTabBar::tab:selected { background:#ffffff; color:#2446db; font-weight:700; }
        QListWidget { background:#ffffff; color:#172033; border:1px solid #bfc7d5; border-radius:5px; }
        QListWidget::item { padding:7px; }
        QListWidget::item:selected { background:#3155f5; color:#ffffff; }
        QCheckBox { color:#172033; font-weight:600; }
        QComboBox,QLineEdit {
            min-height:30px;
            background:#ffffff;
            color:#172033;
            border:1px solid #bfc7d5;
            border-radius:5px;
            padding:2px 7px;
        }
        QComboBox QAbstractItemView {  
            background:#ffffff; color:#172033;  
            selection-background-color:#3155f5; selection-color:#ffffff;  
        }
        QSpinBox,
        QDoubleSpinBox {
            min-height:30px;
            background-color:#ffffff;
            color:#172033;
            border:1px solid #bfc7d5;
            border-radius:5px;

            padding-left:6px;
            
            selection-background-color:#3155f5;
            selection-color:#ffffff;
        
            padding-right:30px;
        }
            
            
        
        
        QPushButton#spinArrowButton {
            min-width:26px;
            max-width:26px;
            min-height:0px;
            padding:0px;
            margin:0px;
            background-color:#eef1f5;
            color:#172033;
            border:0px;
            border-left:1px solid #bfc7d5;
            border-radius:0px;
            font-size:8px;
            font-weight:700;
        }
        QPushButton#spinArrowButton:hover {
            background-color:#dfe7f5;
            color:#2446db;
        }
        QPushButton#spinArrowButton:pressed {
            background-color:#cbd8ef;
        }

        QSpinBox:disabled, QDoubleSpinBox:disabled {
            background-color:#eef1f5;
            color:#70798a;
        }
        QPushButton {
            min-height:30px; padding:2px 12px; background:#ffffff; color:#172033;
            border:1px solid #9da8b8; border-radius:5px;
        }
        QPushButton:hover { border-color:#3155f5; color:#2446db; }
        """)

