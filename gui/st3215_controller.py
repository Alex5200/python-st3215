"""
ST3215 Servo Controller GUI with Block Programming Interface.

A PyQt6-based desktop application for controlling up to 6 ST3215 servos
with visual block programming, min/max limits, and boundary testing.
"""

import sys
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict


from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QSpinBox, QGroupBox, QGridLayout,
    QComboBox, QMessageBox, QFileDialog, QScrollArea,
    QFrame, QTextEdit, QStatusBar,
    QCheckBox, QDialog, QDialogButtonBox,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QAction, QColor, QPalette

# Try to import the ST3215 library
try:
    from src.python_st3215.st3215 import ST3215
    ST3215_AVAILABLE = True
except ImportError:
    ST3215_AVAILABLE = False
    print("Warning: ST3215 library not available. Running in simulation mode.")


@dataclass
class ServoLimits:
    """Min/max position limits for a single servo."""
    min_position: int = 0
    max_position: int = 4095
    enabled: bool = True


@dataclass
class ServoConfig:
    """Configuration for a single servo axis."""
    servo_id: int = 1
    name: str = "Axis 1"
    limits: ServoLimits = field(default_factory=ServoLimits)
    current_position: int = 0
    target_position: int = 0
    speed: int = 100
    acceleration: int = 50
    enabled: bool = True


@dataclass
class BlockCommand:
    """A single command block in the program."""
    block_type: str  # 'move', 'move_all', 'wait', 'set_speed', 'set_limits', 'test_boundaries'
    axis: int = 0  # 0-5 for individual axis, -1 for all
    position: int = 0
    speed: int = 100
    acceleration: int = 50
    wait_time: float = 0.0  # seconds
    parameters: dict = field(default_factory=dict)


class ServoControllerBackend(QObject):
    """Backend for ST3215 servo control."""

    position_updated = pyqtSignal(int, int)  # servo_id, position
    temperature_updated = pyqtSignal(int, float)  # servo_id, temperature
    error_occurred = pyqtSignal(str)  # error message
    connection_status_changed = pyqtSignal(bool)  # connected

    def __init__(self):
        super().__init__()
        self.servo_bus: Optional[ST3215] = None
        self.connected = False
        self.port = ""
        self.servo_configs: dict[int, ServoConfig] = {}

    def connect(self, port: str) -> bool:
        """Connect to servo bus."""
        if not ST3215_AVAILABLE:
            self.error_occurred.emit("ST3215 library not available")
            return False

        try:
            self.servo_bus = ST3215(port)
            self.connected = True
            self.port = port
            self.connection_status_changed.emit(True)
            return True
        except Exception as e:
            self.error_occurred.emit(f"Connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from servo bus."""
        if self.servo_bus:
            try:
                self.servo_bus.close()
            except:
                pass
        self.servo_bus = None
        self.connected = False
        self.connection_status_changed.emit(False)

    def move_servo(self, servo_id: int, position: int, speed: int = 100,
                   acc: int = 50, check_limits: bool = True) -> bool:
        """Move a single servo to position with limits checking."""
        if not self.connected:
            self.error_occurred.emit("Not connected to servo bus")
            return False

        config = self.servo_configs.get(servo_id)

        # Check limits if enabled
        if check_limits and config and config.limits.enabled:
            if position < config.limits.min_position:
                self.error_occurred.emit(
                    f"Position {position} below minimum {config.limits.min_position} "
                    f"for {config.name}"
                )
                return False
            if position > config.limits.max_position:
                self.error_occurred.emit(
                    f"Position {position} above maximum {config.limits.max_position} "
                    f"for {config.name}"
                )
                return False

        try:
            self.servo_bus.MoveTo(servo_id, position, speed=speed, acc=acc, wait=False)
            return True
        except Exception as e:
            self.error_occurred.emit(f"Move failed: {e}")
            return False

    def move_all_servos(self, positions: dict[int, int], speed: int = 100,
                        acc: int = 50) -> bool:
        """Move multiple servos simultaneously."""
        if not self.connected:
            self.error_occurred.emit("Not connected to servo bus")
            return False

        success = True
        for servo_id, position in positions.items():
            if not self.move_servo(servo_id, position, speed, acc):
                success = False
        return success

    def read_position(self, servo_id: int) -> Optional[int]:
        """Read current position from servo."""
        if not self.connected:
            return None
        try:
            return self.servo_bus.ReadPosition(servo_id)
        except Exception as e:
            self.error_occurred.emit(f"Read position failed: {e}")
            return None

    def read_temperature(self, servo_id: int) -> Optional[float]:
        """Read temperature from servo."""
        if not self.connected:
            return None
        try:
            return self.servo_bus.ReadTemperature(servo_id)
        except Exception:
            return None

    def test_boundaries(self, servo_id: int, min_pos: int, max_pos: int,
                        speed: int = 50) -> bool:
        """Test min/max boundaries for a single servo."""
        if not self.connected:
            self.error_occurred.emit("Not connected to servo bus")
            return False

        try:
            # Move to minimum position
            self.servo_bus.MoveTo(servo_id, min_pos, speed=speed, acc=30, wait=True)

            # Move to maximum position
            self.servo_bus.MoveTo(servo_id, max_pos, speed=speed, acc=30, wait=True)

            # Move back to center
            center = (min_pos + max_pos) // 2
            self.servo_bus.MoveTo(servo_id, center, speed=speed, acc=30, wait=False)

            return True
        except Exception as e:
            self.error_occurred.emit(f"Boundary test failed: {e}")
            return False

    def set_limits_on_servo(self, servo_id: int, min_pos: int,
                            max_pos: int) -> bool:
        """Write min/max limits to servo EEPROM."""
        if not self.connected:
            self.error_occurred.emit("Not connected to servo bus")
            return False

        try:
            servo = self.servo_bus.wrap_servo(servo_id)
            servo.eeprom.write_min_angle_limit(min_pos)
            servo.eeprom.write_max_angle_limit(max_pos)
            return True
        except Exception as e:
            self.error_occurred.emit(f"Set limits failed: {e}")
            return False


class CommandBlockWidget(QFrame):
    """Visual representation of a command block with edit capability."""

    delete_requested = pyqtSignal()
    move_up = pyqtSignal()
    move_down = pyqtSignal()
    edit_requested = pyqtSignal()

    # Block type colors
    TYPE_COLORS = {
        'move': ("#4a9eff", "#1a3a5c"),
        'move_all': ("#4aff4a", "#1a5c2a"),
        'wait': ("#ff4aff", "#5c1a5c"),
        'set_speed': ("#ffff4a", "#5c5c1a"),
        'test_boundaries': ("#ffaa4a", "#5c3a1a"),
    }

    def __init__(self, block: BlockCommand, index: int, parent=None):
        super().__init__(parent)
        self.block = block
        self.index = index
        self.setup_ui()

    def setup_ui(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        color, dark_color = self.TYPE_COLORS.get(self.block.block_type, ("#4a9eff", "#1a3a5c"))
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {dark_color};
                border-radius: 8px;
                border: 2px solid {color};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Header with connector line
        header = QHBoxLayout()

        # Connection indicator (visual connector to next block)
        connector = QLabel("●")
        connector.setStyleSheet("color: #666; font-size: 16px;")
        connector.setFixedWidth(15)
        header.addWidget(connector)

        # Block number badge
        badge = QLabel(f"{self.index + 1}")
        badge.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                color: #000;
                font-weight: bold;
                font-size: 12px;
                border-radius: 10px;
                padding: 2px 8px;
            }}
        """)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(24, 20)
        header.addWidget(badge)

        # Block type label
        block_type_label = QLabel(self.get_block_type_name())
        block_type_label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 13px;")
        header.addWidget(block_type_label)

        header.addStretch()

        # Edit button
        edit_btn = QPushButton("✎")
        edit_btn.setFixedSize(28, 28)
        edit_btn.setToolTip("Edit block parameters")
        edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a9eff;
                color: white;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5aafff;
            }
        """)
        edit_btn.clicked.connect(self.edit_requested.emit)
        header.addWidget(edit_btn)

        # Move up button
        up_btn = QPushButton("▲")
        up_btn.setFixedSize(28, 28)
        up_btn.setToolTip("Move up")
        up_btn.setStyleSheet("""
            QPushButton {
                background-color: #666;
                color: white;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #777;
            }
        """)
        up_btn.clicked.connect(self.move_up.emit)
        header.addWidget(up_btn)

        # Move down button
        down_btn = QPushButton("▼")
        down_btn.setFixedSize(28, 28)
        down_btn.setToolTip("Move down")
        down_btn.setStyleSheet("""
            QPushButton {
                background-color: #666;
                color: white;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #777;
            }
        """)
        down_btn.clicked.connect(self.move_down.emit)
        header.addWidget(down_btn)

        # Delete button
        del_btn = QPushButton("🗑")
        del_btn.setFixedSize(28, 28)
        del_btn.setToolTip("Delete block")
        del_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff4444;
                color: white;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #ff6666;
            }
        """)
        del_btn.clicked.connect(self.delete_requested.emit)
        header.addWidget(del_btn)

        layout.addLayout(header)

        # Separator line
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"background-color: {color};")
        line.setFixedHeight(1)
        layout.addWidget(line)

        # Parameters section
        params_widget = QWidget()
        params_layout = QGridLayout(params_widget)
        params_layout.setContentsMargins(5, 5, 5, 5)
        params_layout.setHorizontalSpacing(15)
        params_layout.setVerticalSpacing(5)

        self._setup_params_layout(params_layout)

        layout.addWidget(params_widget)

    def _setup_params_layout(self, layout: QGridLayout):
        """Setup parameters display based on block type."""
        if self.block.block_type == 'move':
            self._add_param_row(layout, "Axis:", str(self.block.axis + 1), "#888")
            self._add_param_row(layout, "Position:", str(self.block.position), "#4aff4a")
            self._add_param_row(layout, "Speed:", f"{self.block.speed}%", "#ffff4a")
            self._add_param_row(layout, "Accel:", f"{self.block.acceleration}", "#ffaa4a")

        elif self.block.block_type == 'move_all':
            positions = self.block.parameters.get('positions', {})
            pos_str = ", ".join(f"A{i+1}:{v}" for i, v in sorted(positions.items(), key=lambda x: int(x[0])) if v)
            if not pos_str:
                pos_str = "(no positions set)"
            self._add_param_row(layout, "Axes:", "All (1-6)", "#888")
            self._add_param_row(layout, "Positions:", pos_str, "#4aff4a")

        elif self.block.block_type == 'wait':
            self._add_param_row(layout, "Wait Time:", f"{self.block.wait_time:.1f} sec", "#ff4aff")

        elif self.block.block_type == 'set_speed':
            axis_str = str(self.block.axis + 1) if self.block.axis >= 0 else "All Axes"
            self._add_param_row(layout, "Axis:", axis_str, "#888")
            self._add_param_row(layout, "Speed:", f"{self.block.speed}%", "#ffff4a")

        elif self.block.block_type == 'test_boundaries':
            config_min = self.block.parameters.get('min_pos', 0)
            config_max = self.block.parameters.get('max_pos', 4095)
            self._add_param_row(layout, "Axis:", str(self.block.axis + 1), "#ffaa4a")
            self._add_param_row(layout, "Range:", f"{config_min} - {config_max}", "#4aff4a")

    def _add_param_row(self, layout: QGridLayout, label: str, value: str, color: str):
        """Add a parameter row to the layout."""
        label_widget = QLabel(label)
        label_widget.setStyleSheet("color: #aaa; font-size: 11px;")
        value_widget = QLabel(value)
        value_widget.setStyleSheet(f"color: {color}; font-weight: bold; font-family: monospace; font-size: 12px;")

        row = layout.rowCount()
        layout.addWidget(label_widget, row, 0)
        layout.addWidget(value_widget, row, 1)

    def get_block_type_name(self) -> str:
        names = {
            'move': "Move Axis",
            'move_all': "Move All",
            'wait': "Wait",
            'set_speed': "Set Speed",
            'set_limits': "Set Limits",
            'test_boundaries': "Test Boundaries",
        }
        return names.get(self.block.block_type, self.block.block_type)

    def update_block(self, block: BlockCommand):
        """Update the block and refresh display."""
        self.block = block
        # Refresh the UI
        while self.layout().count() > 0:
            item = self.layout().takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.setup_ui()


class BlockProgrammingWidget(QWidget):
    """Enhanced block programming interface with categorized toolbar."""

    program_changed = pyqtSignal()

    def __init__(self, servo_configs: dict[int, ServoConfig], parent=None):
        super().__init__(parent)
        self.servo_configs = servo_configs
        self.blocks: list[BlockCommand] = []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Title
        title = QLabel("Block Programming Interface")
        title.setStyleSheet("color: #4a9eff; font-weight: bold; font-size: 16px; padding: 5px;")
        layout.addWidget(title)

        # Toolbar with categories
        toolbar = QVBoxLayout()

        # Category: Movement
        move_group = self._create_button_group("Movement Commands", [
            ("📍 Move", 'move', "Move single axis to position"),
            ("📍 Move All", 'move_all', "Move all axes simultaneously"),
        ])
        toolbar.addLayout(move_group)

        # Category: Control
        control_group = self._create_button_group("Control Commands", [
            ("⏱️ Wait", 'wait', "Wait for specified time"),
            ("⚡ Set Speed", 'set_speed', "Set movement speed"),
        ])
        toolbar.addLayout(control_group)

        # Category: Testing
        test_group = self._create_button_group("Testing Commands", [
            ("🧪 Test Boundaries", 'test_boundaries', "Test min/max boundaries"),
        ])
        toolbar.addLayout(test_group)

        # Action buttons row
        action_row = QHBoxLayout()

        self.clear_btn = QPushButton("🗑 Clear All")
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #666;
                color: white;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #777;
            }
        """)
        self.clear_btn.clicked.connect(self.clear_blocks)
        action_row.addWidget(self.clear_btn)

        action_row.addStretch()

        self.run_btn = QPushButton("▶️ Run Program")
        self.run_btn.setStyleSheet("""
            QPushButton {
                background-color: #4aff4a;
                color: black;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #44dd44;
            }
            QPushButton:pressed {
                background-color: #33cc33;
            }
        """)
        action_row.addWidget(self.run_btn)

        toolbar.addLayout(action_row)

        # Toolbar frame
        toolbar_frame = QFrame()
        toolbar_frame.setStyleSheet("""
            QFrame {
                background-color: #2a2a2a;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        toolbar_frame.setLayout(toolbar)
        layout.addWidget(toolbar_frame)

        # Blocks counter
        self.counter_label = QLabel("0 blocks")
        self.counter_label.setStyleSheet("color: #666; font-size: 11px; padding: 2px;")
        layout.addWidget(self.counter_label)

        # Blocks area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: #1a1a1a;
                border-radius: 4px;
                border: 1px solid #333;
            }
        """)

        self.blocks_container = QWidget()
        self.blocks_layout = QVBoxLayout(self.blocks_container)
        self.blocks_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.blocks_layout.setSpacing(5)

        scroll.setWidget(self.blocks_container)
        layout.addWidget(scroll, 1)

        # Empty state
        self.empty_label = QLabel(
            "📋 No blocks added\n\nClick the buttons above to add commands.\n"
            "Double-click a block to edit its parameters."
        )
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: #555; padding: 40px; font-size: 13px;")
        self.blocks_layout.addWidget(self.empty_label)

    def _create_button_group(self, title: str, buttons: list[tuple]) -> QHBoxLayout:
        """Create a row of buttons with a title."""
        group = QHBoxLayout()

        label = QLabel(f"{title}:")
        label.setStyleSheet("color: #888; font-size: 11px; padding-right: 5px;")
        group.addWidget(label)

        for icon, block_type, tooltip in buttons:
            btn = QPushButton(icon)
            btn.setToolTip(tooltip)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3a3a3a;
                    color: white;
                    padding: 5px 10px;
                    border-radius: 4px;
                    border: 1px solid #444;
                }
                QPushButton:hover {
                    background-color: #4a4a4a;
                    border-color: #4a9eff;
                }
            """)
            btn.clicked.connect(lambda checked, t=block_type: self.add_block(t))
            group.addWidget(btn)

        group.addStretch()
        return group

    def add_block(self, block_type: str):
        """Add a new command block."""
        block = BlockCommand(block_type=block_type)

        # Set defaults based on type
        if block_type == 'move':
            block.axis = 0
            block.position = 2048
            block.speed = 50
            block.acceleration = 50
        elif block_type == 'move_all':
            block.parameters = {'positions': {str(i): 2048 for i in range(6)}}
            block.speed = 50
        elif block_type == 'wait':
            block.wait_time = 1.0
        elif block_type == 'set_speed':
            block.axis = -1  # All axes
            block.speed = 50
        elif block_type == 'test_boundaries':
            block.axis = 0
            config = self.servo_configs.get(0, ServoConfig())
            block.parameters = {
                'min_pos': config.limits.min_position,
                'max_pos': config.limits.max_position,
                'speed': 50
            }

        self.blocks.append(block)
        self.refresh_blocks()
        self.program_changed.emit()

    def remove_block(self, index: int):
        """Remove a block at index."""
        if 0 <= index < len(self.blocks):
            self.blocks.pop(index)
            self.refresh_blocks()
            self.program_changed.emit()

    def move_block(self, index: int, direction: int):
        """Move block up or down."""
        new_index = index + direction
        if 0 <= index < len(self.blocks) and 0 <= new_index < len(self.blocks):
            self.blocks[index], self.blocks[new_index] = \
                self.blocks[new_index], self.blocks[index]
            self.refresh_blocks()
            self.program_changed.emit()

    def edit_block(self, index: int):
        """Open edit dialog for a block."""
        if 0 <= index < len(self.blocks):
            block = self.blocks[index]
            dialog = BlockEditDialog(block, self.servo_configs, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.blocks[index] = dialog.get_updated_block()
                self.refresh_blocks()
                self.program_changed.emit()

    def refresh_blocks(self):
        """Refresh the block display."""
        # Clear existing widgets
        while self.blocks_layout.count() > 0:
            item = self.blocks_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Update counter
        self.counter_label.setText(f"{len(self.blocks)} block(s)")

        if not self.blocks:
            self.blocks_layout.addWidget(self.empty_label)
            return

        for i, block in enumerate(self.blocks):
            widget = CommandBlockWidget(block, i)
            widget.delete_requested.connect(lambda idx=i: self.remove_block(idx))
            widget.move_up.connect(lambda idx=i: self.move_block(idx, -1))
            widget.move_down.connect(lambda idx=i: self.move_block(idx, 1))
            widget.edit_requested.connect(lambda idx=i: self.edit_block(idx))
            self.blocks_layout.addWidget(widget)

    def get_blocks(self) -> list[BlockCommand]:
        return self.blocks.copy()

    def clear_blocks(self):
        """Clear all blocks."""
        if self.blocks:
            reply = QMessageBox.question(
                self, "Clear All",
                "Are you sure you want to clear all blocks?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
        self.blocks.clear()
        self.refresh_blocks()
        self.program_changed.emit()

    def load_blocks(self, blocks: list[BlockCommand]):
        self.blocks = blocks
        self.refresh_blocks()
        self.program_changed.emit()


class ServoSliderWidget(QWidget):
    """Slider control for a single servo with limits visualization."""

    value_changed = pyqtSignal(int)

    def __init__(self, config: ServoConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Name and ID
        name_layout = QHBoxLayout()
        self.name_label = QLabel(self.config.name)
        self.name_label.setStyleSheet("color: white; font-weight: bold;")
        name_layout.addWidget(self.name_label)

        self.id_label = QLabel(f"ID: {self.config.servo_id}")
        self.id_label.setStyleSheet("color: #888;")
        name_layout.addWidget(self.id_label)

        name_layout.addStretch()

        self.pos_label = QLabel(f"{self.config.current_position}")
        self.pos_label.setStyleSheet("color: #4aff4a; font-family: monospace;")
        name_layout.addWidget(self.pos_label)

        layout.addLayout(name_layout)

        # Slider with limits visualization
        slider_layout = QHBoxLayout()

        # Min label
        self.min_label = QLabel(str(self.config.limits.min_position))
        self.min_label.setStyleSheet("color: #ff4444; font-size: 10px;")
        slider_layout.addWidget(self.min_label)

        # Slider
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 4095)
        self.slider.setValue(self.config.current_position)
        self.slider.valueChanged.connect(self.on_slider_changed)
        slider_layout.addWidget(self.slider)

        # Max label
        self.max_label = QLabel(str(self.config.limits.max_position))
        self.max_label.setStyleSheet("color: #ff4444; font-size: 10px;")
        slider_layout.addWidget(self.max_label)

        layout.addLayout(slider_layout)

        # Spinbox for precise control
        spin_layout = QHBoxLayout()
        spin_layout.addWidget(QLabel("Target:"))
        self.target_spin = QSpinBox()
        self.target_spin.setRange(0, 4095)
        self.target_spin.setValue(self.config.target_position)
        self.target_spin.valueChanged.connect(self.on_target_changed)
        spin_layout.addWidget(self.target_spin)

        layout.addLayout(spin_layout)

        self.update_limits_display()

    def on_slider_changed(self, value: int):
        self.config.target_position = value
        self.pos_label.setText(str(value))
        self.value_changed.emit(value)

    def on_target_changed(self, value: int):
        self.config.target_position = value
        self.slider.setValue(value)
        self.value_changed.emit(value)

    def update_limits_display(self):
        self.min_label.setText(str(self.config.limits.min_position))
        self.max_label.setText(str(self.config.limits.max_position))

        # Update slider style to show limits
        if self.config.limits.enabled:
            self.slider.setStyleSheet("""
                QSlider::groove:horizontal {
                    height: 8px;
                    background: #333;
                    border-radius: 4px;
                }
                QSlider::handle:horizontal {
                    background: #4a9eff;
                    width: 20px;
                    margin: -6px 0;
                    border-radius: 10px;
                }
                QSlider::sub-page:horizontal {
                    background: #4a9eff;
                    border-radius: 4px;
                }
            """)
        else:
            self.slider.setStyleSheet("""
                QSlider::groove:horizontal {
                    height: 8px;
                    background: #333;
                    border-radius: 4px;
                }
                QSlider::handle:horizontal {
                    background: #4a9eff;
                    width: 20px;
                    margin: -6px 0;
                    border-radius: 10px;
                }
            """)

    def update_position(self, position: int):
        self.config.current_position = position
        self.pos_label.setText(str(position))


class ServoLimitsDialog(QDialog):
    """Dialog for configuring servo limits."""

    def __init__(self, configs: dict[int, ServoConfig], parent=None):
        super().__init__(parent)
        self.configs = configs
        self.setWindowTitle("Servo Limits Configuration")
        self.setMinimumSize(600, 500)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Info label
        info = QLabel("Configure min/max position limits for each axis.\n"
                     "Values are in servo steps (0-4095).")
        info.setStyleSheet("color: #aaa; padding: 10px;")
        layout.addWidget(info)

        # Limits form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        form_widget = QWidget()
        self.form_layout = QGridLayout(form_widget)

        headers = ["Axis", "Servo ID", "Min Position", "Max Position", "Enabled"]
        for col, header in enumerate(headers):
            label = QLabel(header)
            label.setStyleSheet("color: white; font-weight: bold; padding: 5px;")
            self.form_layout.addWidget(label, 0, col)

        row = 1
        self.min_spins: dict[int, QSpinBox] = {}
        self.max_spins: dict[int, QSpinBox] = {}
        self.enabled_checks: dict[int, QCheckBox] = {}

        for i in range(6):
            config = self.configs.get(i, ServoConfig(servo_id=i+1, name=f"Axis {i+1}"))

            # Axis name
            self.form_layout.addWidget(QLabel(config.name), row, 0)

            # Servo ID
            id_label = QLabel(str(config.servo_id))
            id_label.setStyleSheet("color: #888;")
            self.form_layout.addWidget(id_label, row, 1)

            # Min position
            min_spin = QSpinBox()
            min_spin.setRange(0, 4095)
            min_spin.setValue(config.limits.min_position)
            self.min_spins[i] = min_spin
            self.form_layout.addWidget(min_spin, row, 2)

            # Max position
            max_spin = QSpinBox()
            max_spin.setRange(0, 4095)
            max_spin.setValue(config.limits.max_position)
            self.max_spins[i] = max_spin
            self.form_layout.addWidget(max_spin, row, 3)

            # Enabled checkbox
            enabled_check = QCheckBox()
            enabled_check.setChecked(config.limits.enabled)
            self.enabled_checks[i] = enabled_check
            self.form_layout.addWidget(enabled_check, row, 4)

            row += 1

        scroll.setWidget(form_widget)
        layout.addWidget(scroll)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_updated_configs(self) -> dict[int, ServoConfig]:
        for i in range(6):
            config = self.configs.get(i, ServoConfig(servo_id=i+1))
            config.limits.min_position = self.min_spins[i].value()
            config.limits.max_position = self.max_spins[i].value()
            config.limits.enabled = self.enabled_checks[i].isChecked()
            self.configs[i] = config
        return self.configs


class BlockEditDialog(QDialog):
    """Dialog for editing block parameters."""

    def __init__(self, block: BlockCommand, configs: dict[int, ServoConfig], parent=None):
        super().__init__(parent)
        self.block = block
        self.configs = configs
        self.setWindowTitle(f"Edit {block.block_type.replace('_', ' ').title()} Block")
        self.setMinimumWidth(400)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        if self.block.block_type == 'move':
            self._setup_move_layout(layout)
        elif self.block.block_type == 'move_all':
            self._setup_move_all_layout(layout)
        elif self.block.block_type == 'wait':
            self._setup_wait_layout(layout)
        elif self.block.block_type == 'set_speed':
            self._setup_speed_layout(layout)
        elif self.block.block_type == 'test_boundaries':
            self._setup_test_layout(layout)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _setup_move_layout(self, layout: QVBoxLayout):
        form = QFormLayout()

        # Axis selector
        self.axis_combo = QComboBox()
        for i in range(6):
            name = self.configs.get(i, ServoConfig(servo_id=i+1)).name
            self.axis_combo.addItem(f"{name} (ID: {self.configs.get(i, ServoConfig(servo_id=i+1)).servo_id})", i)
            if i == self.block.axis:
                self.axis_combo.setCurrentIndex(i)
        form.addRow("Axis:", self.axis_combo)

        # Position
        self.position_spin = QSpinBox()
        self.position_spin.setRange(0, 4095)
        self.position_spin.setValue(self.block.position)
        self.position_spin.setStyleSheet("color: #4aff4a; font-family: monospace; font-size: 14px;")
        form.addRow("Position:", self.position_spin)

        # Speed
        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(1, 100)
        self.speed_spin.setValue(self.block.speed)
        form.addRow("Speed (%):", self.speed_spin)

        # Acceleration
        self.accel_spin = QSpinBox()
        self.accel_spin.setRange(1, 100)
        self.accel_spin.setValue(self.block.acceleration)
        form.addRow("Acceleration:", self.accel_spin)

        layout.addLayout(form)

    def _setup_move_all_layout(self, layout: QVBoxLayout):
        layout.addWidget(QLabel("Set positions for all axes:"))

        self.position_spins = {}
        grid = QGridLayout()
        grid.addWidget(QLabel("Axis"), 0, 0)
        grid.addWidget(QLabel("Position"), 0, 1)

        for i in range(6):
            config = self.configs.get(i, ServoConfig(servo_id=i+1))
            label = QLabel(f"{config.name}")
            label.setStyleSheet("color: white;")
            grid.addWidget(label, i + 1, 0)

            spin = QSpinBox()
            spin.setRange(0, 4095)
            positions = self.block.parameters.get('positions', {})
            spin.setValue(positions.get(str(i), 2048))
            self.position_spins[i] = spin
            grid.addWidget(spin, i + 1, 1)

        layout.addLayout(grid)

        # Speed
        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(1, 100)
        self.speed_spin.setValue(self.block.speed)
        layout.addWidget(QLabel("Speed (%):"))
        layout.addWidget(self.speed_spin)

    def _setup_wait_layout(self, layout: QVBoxLayout):
        form = QFormLayout()

        self.time_spin = QDoubleSpinBox()
        self.time_spin.setRange(0.1, 60.0)
        self.time_spin.setValue(self.block.wait_time)
        self.time_spin.setSuffix(" s")
        self.time_spin.setStyleSheet("color: #ff4aff; font-family: monospace; font-size: 14px;")
        form.addRow("Wait Time:", self.time_spin)

        layout.addLayout(form)

    def _setup_speed_layout(self, layout: QVBoxLayout):
        form = QFormLayout()

        # Axis selector
        self.axis_combo = QComboBox()
        self.axis_combo.addItem("All Axes", -1)
        for i in range(6):
            name = self.configs.get(i, ServoConfig(servo_id=i+1)).name
            self.axis_combo.addItem(f"{name}", i)
            if i == self.block.axis:
                self.axis_combo.setCurrentIndex(i + 1)  # +1 because "All Axes" is first
        form.addRow("Axis:", self.axis_combo)

        # Speed
        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(1, 100)
        self.speed_spin.setValue(self.block.speed)
        self.speed_spin.setStyleSheet("color: #ffff4a; font-family: monospace; font-size: 14px;")
        form.addRow("Speed (%):", self.speed_spin)

        layout.addLayout(form)

    def _setup_test_layout(self, layout: QVBoxLayout):
        form = QFormLayout()

        # Axis selector
        self.axis_combo = QComboBox()
        for i in range(6):
            name = self.configs.get(i, ServoConfig(servo_id=i+1)).name
            self.axis_combo.addItem(f"{name} (ID: {self.configs.get(i, ServoConfig(servo_id=i+1)).servo_id})", i)
            if i == self.block.axis:
                self.axis_combo.setCurrentIndex(i)
        form.addRow("Axis to Test:", self.axis_combo)

        # Min position
        config = self.configs.get(self.block.axis, ServoConfig())
        self.min_spin = QSpinBox()
        self.min_spin.setRange(0, 4095)
        self.min_spin.setValue(config.limits.min_position)
        form.addRow("Min Position:", self.min_spin)

        # Max position
        self.max_spin = QSpinBox()
        self.max_spin.setRange(0, 4095)
        self.max_spin.setValue(config.limits.max_position)
        form.addRow("Max Position:", self.max_spin)

        # Test speed
        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(10, 100)
        self.speed_spin.setValue(50)
        form.addRow("Test Speed:", self.speed_spin)

        layout.addLayout(form)

    def get_updated_block(self) -> BlockCommand:
        """Return the block with updated parameters."""
        if self.block.block_type == 'move':
            self.block.axis = self.axis_combo.currentData()
            self.block.position = self.position_spin.value()
            self.block.speed = self.speed_spin.value()
            self.block.acceleration = self.accel_spin.value()

        elif self.block.block_type == 'move_all':
            positions = {str(i): spin.value() for i, spin in self.position_spins.items()}
            self.block.parameters['positions'] = positions
            self.block.speed = getattr(self, 'speed_spin', None) and self.speed_spin.value() or 100

        elif self.block.block_type == 'wait':
            self.block.wait_time = self.time_spin.value()

        elif self.block.block_type == 'set_speed':
            self.block.axis = self.axis_combo.currentData()
            self.block.speed = self.speed_spin.value()

        elif self.block.block_type == 'test_boundaries':
            self.block.axis = self.axis_combo.currentData()
            self.block.parameters['min_pos'] = self.min_spin.value()
            self.block.parameters['max_pos'] = self.max_spin.value()
            self.block.parameters['speed'] = self.speed_spin.value()

        return self.block


class ST3215ControllerWindow(QMainWindow):
    """Main window for ST3215 servo controller."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ST3215 Servo Controller")
        self.setMinimumSize(1200, 800)

        self.backend = ServoControllerBackend()
        self.servo_configs: dict[int, ServoConfig] = {
            i: ServoConfig(servo_id=i+1, name=f"Axis {i+1}")
            for i in range(6)
        }

        # Update backend configs
        self.backend.servo_configs = self.servo_configs

        self.setup_ui()
        self.setup_menu()
        self.setup_statusbar()

        # Start polling timer
        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self.poll_servos)
        self.poll_timer.start(100)  # 10 Hz

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        # Left panel - Servo controls
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Connection group
        conn_group = QGroupBox("Connection")
        conn_layout = QHBoxLayout(conn_group)

        self.port_combo = QComboBox()
        self.port_combo.addItems(["COM1", "COM2", "COM3", "COM4",
                                  "/dev/ttyUSB0", "/dev/ttyUSB1",
                                  "/dev/ttyACM0", "/dev/ttyACM1"])
        self.port_combo.setEditable(True)
        self.port_combo.setCurrentText("COM3")
        conn_layout.addWidget(self.port_combo)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.toggle_connection)
        conn_layout.addWidget(self.connect_btn)

        self.status_indicator = QLabel("●")
        self.status_indicator.setStyleSheet("color: red; font-size: 20px;")
        conn_layout.addWidget(self.status_indicator)

        left_layout.addWidget(conn_group)

        # Servo control group
        servo_group = QGroupBox("Servo Controls (6 Axes)")
        servo_layout = QVBoxLayout(servo_group)

        self.slider_widgets: dict[int, ServoSliderWidget] = {}

        for i in range(6):
            config = self.servo_configs[i]
            slider_widget = ServoSliderWidget(config)
            slider_widget.value_changed.connect(
                lambda pos, idx=i: self.on_servo_move(idx, pos)
            )
            self.slider_widgets[i] = slider_widget
            servo_layout.addWidget(slider_widget)

        servo_layout.addStretch()

        # Control buttons
        btn_layout = QHBoxLayout()

        self.move_all_btn = QPushButton("Move All")
        self.move_all_btn.clicked.connect(self.move_all_servos)
        btn_layout.addWidget(self.move_all_btn)

        self.limits_btn = QPushButton("Configure Limits")
        self.limits_btn.clicked.connect(self.show_limits_dialog)
        btn_layout.addWidget(self.limits_btn)

        self.zero_btn = QPushButton("Zero All")
        self.zero_btn.clicked.connect(self.zero_all_servos)
        btn_layout.addWidget(self.zero_btn)

        servo_layout.addLayout(btn_layout)

        left_layout.addWidget(servo_group)
        left_layout.addStretch()

        layout.addWidget(left_panel, 1)

        # Right panel - Block programming
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.block_programmer = BlockProgrammingWidget()
        self.block_programmer.run_btn.clicked.connect(self.run_program)
        right_layout.addWidget(self.block_programmer)

        layout.addWidget(right_panel, 2)

        # Log panel at bottom
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #4aff4a;
                font-family: monospace;
            }
        """)
        log_layout.addWidget(self.log_text)

        layout.addWidget(log_group)

    def setup_menu(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        save_prog_action = QAction("Save Program", self)
        save_prog_action.triggered.connect(self.save_program)
        file_menu.addAction(save_prog_action)

        load_prog_action = QAction("Load Program", self)
        load_prog_action.triggered.connect(self.load_program)
        file_menu.addAction(load_prog_action)

        file_menu.addSeparator()

        save_config_action = QAction("Save Configuration", self)
        save_config_action.triggered.connect(self.save_configuration)
        file_menu.addAction(save_config_action)

        load_config_action = QAction("Load Configuration", self)
        load_config_action.triggered.connect(self.load_configuration)
        file_menu.addAction(load_config_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Tools menu
        tools_menu = menubar.addMenu("Tools")

        test_all_action = QAction("Test All Boundaries", self)
        test_all_action.triggered.connect(self.test_all_boundaries)
        tools_menu.addAction(test_all_action)

        write_limits_action = QAction("Write Limits to Servos", self)
        write_limits_action.triggered.connect(self.write_limits_to_servos)
        tools_menu.addAction(write_limits_action)

        # Help menu
        help_menu = menubar.addMenu("Help")

        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def setup_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Ready")

    def log(self, message: str):
        """Add message to log."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")

    def toggle_connection(self):
        """Connect or disconnect from servo bus."""
        if self.backend.connected:
            self.backend.disconnect()
            self.connect_btn.setText("Connect")
            self.status_indicator.setStyleSheet("color: red; font-size: 20px;")
            self.log("Disconnected")
            self.statusbar.showMessage("Disconnected")
        else:
            port = self.port_combo.currentText()
            if self.backend.connect(port):
                self.connect_btn.setText("Disconnect")
                self.status_indicator.setStyleSheet("color: #4aff4a; font-size: 20px;")
                self.log(f"Connected to {port}")
                self.statusbar.showMessage(f"Connected to {port}")
            else:
                self.log("Connection failed")

    def on_servo_move(self, axis: int, position: int):
        """Handle servo slider movement."""
        config = self.servo_configs[axis]
        self.backend.move_servo(config.servo_id, position)

    def move_all_servos(self):
        """Move all servos to their target positions."""
        positions = {
            self.servo_configs[i].servo_id: self.servo_configs[i].target_position
            for i in range(6)
        }
        self.backend.move_all_servos(positions)
        self.log(f"Moving all servos: {positions}")

    def zero_all_servos(self):
        """Move all servos to center position (2048)."""
        for i in range(6):
            self.slider_widgets[i].slider.setValue(2048)
        self.move_all_servos()
        self.log("Zeroed all servos to center position")

    def show_limits_dialog(self):
        """Show limits configuration dialog."""
        dialog = ServoLimitsDialog(self.servo_configs, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.servo_configs = dialog.get_updated_configs()
            self.backend.servo_configs = self.servo_configs

            # Update slider displays
            for i in range(6):
                self.slider_widgets[i].update_limits_display()

            self.log("Limits configuration updated")

    def poll_servos(self):
        """Poll servos for current position and temperature."""
        if not self.backend.connected:
            return

        for i in range(6):
            config = self.servo_configs[i]
            pos = self.backend.read_position(config.servo_id)
            if pos is not None:
                self.slider_widgets[i].update_position(pos)

    def run_program(self):
        """Execute the block program."""
        blocks = self.block_programmer.get_blocks()

        if not blocks:
            QMessageBox.information(self, "No Program",
                                   "Add blocks to the program first.")
            return

        if not self.backend.connected:
            QMessageBox.warning(self, "Not Connected",
                               "Please connect to servo bus first.")
            return

        self.log(f"Running program with {len(blocks)} blocks...")
        self.execute_blocks(blocks)

    def execute_blocks(self, blocks: list[BlockCommand]):
        """Execute blocks sequentially."""
        for block in blocks:
            try:
                if block.block_type == 'move':
                    servo_id = self.servo_configs[block.axis].servo_id
                    success = self.backend.move_servo(
                        servo_id, block.position, block.speed, block.acceleration
                    )
                    if success:
                        self.log(f"Moved axis {block.axis + 1} to {block.position}")

                elif block.block_type == 'move_all':
                    positions = block.parameters.get('positions', {})
                    self.backend.move_all_servos(positions)
                    self.log(f"Moved all servos: {positions}")

                elif block.block_type == 'wait':
                    self.log(f"Waiting {block.wait_time}s")

                elif block.block_type == 'set_speed':
                    # Speed is applied on next move
                    self.log(f"Set speed to {block.speed}")

                elif block.block_type == 'test_boundaries':
                    config = self.servo_configs[block.axis]
                    self.backend.test_boundaries(
                        config.servo_id,
                        config.limits.min_position,
                        config.limits.max_position
                    )
                    self.log(f"Testing boundaries for axis {block.axis + 1}")

            except Exception as e:
                self.log(f"Error executing block: {e}")
                break

    def test_all_boundaries(self):
        """Test boundaries for all servos sequentially."""
        if not self.backend.connected:
            QMessageBox.warning(self, "Not Connected",
                               "Please connect to servo bus first.")
            return

        for i in range(6):
            config = self.servo_configs[i]
            self.log(f"Testing axis {i + 1}...")
            self.backend.test_boundaries(
                config.servo_id,
                config.limits.min_position,
                config.limits.max_position
            )

    def write_limits_to_servos(self):
        """Write configured limits to servo EEPROM."""
        if not self.backend.connected:
            QMessageBox.warning(self, "Not Connected",
                               "Please connect to servo bus first.")
            return

        for i in range(6):
            config = self.servo_configs[i]
            if config.limits.enabled:
                self.backend.set_limits_on_servo(
                    config.servo_id,
                    config.limits.min_position,
                    config.limits.max_position
                )
                self.log(f"Wrote limits to servo {config.servo_id}: "
                        f"{config.limits.min_position}-{config.limits.max_position}")

    def save_program(self):
        """Save block program to file."""
        blocks = self.block_programmer.get_blocks()
        data = [asdict(b) for b in blocks]

        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Program", "", "JSON Files (*.json)"
        )
        if filename:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            self.log(f"Program saved to {filename}")

    def load_program(self):
        """Load block program from file."""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load Program", "", "JSON Files (*.json)"
        )
        if filename:
            with open(filename, 'r') as f:
                data = json.load(f)
            blocks = [BlockCommand(**d) for d in data]
            self.block_programmer.load_blocks(blocks)
            self.log(f"Program loaded from {filename}")

    def save_configuration(self):
        """Save servo configuration to file."""
        data = {str(k): asdict(v) for k, v in self.servo_configs.items()}

        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Configuration", "", "JSON Files (*.json)"
        )
        if filename:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            self.log(f"Configuration saved to {filename}")

    def load_configuration(self):
        """Load servo configuration from file."""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load Configuration", "", "JSON Files (*.json)"
        )
        if filename:
            with open(filename, 'r') as f:
                data = json.load(f)
            self.servo_configs = {
                int(k): ServoConfig(**v) for k, v in data.items()
            }
            self.backend.servo_configs = self.servo_configs

            # Refresh UI
            for i in range(6):
                self.slider_widgets[i].config = self.servo_configs[i]
                self.slider_widgets[i].update_limits_display()

            self.log(f"Configuration loaded from {filename}")

    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About ST3215 Controller",
            "ST3215 Servo Controller with Block Programming\n\n"
            "A PyQt6-based GUI for controlling up to 6 ST3215 servos\n"
            "with visual block programming interface.\n\n"
            "Features:\n"
            "- Individual servo control with sliders\n"
            "- Min/max position limits\n"
            "- Block-based programming\n"
            "- Boundary testing\n"
            "- Save/load programs and configurations"
        )

    def closeEvent(self, event):
        """Clean up on close."""
        self.poll_timer.stop()
        self.backend.disconnect()
        event.accept()


def main():
    app = QApplication(sys.argv)

    # Set dark theme
    app.setStyle("Fusion")

    # Dark palette
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    app.setPalette(palette)

    window = ST3215ControllerWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()