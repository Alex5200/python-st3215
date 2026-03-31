# ST3215 Servo Controller GUI

A PyQt6-based desktop application for controlling up to 6 ST3215 servos with visual block programming interface.

## Features

- **Individual Servo Control**: Slider-based control for each of 6 servo axes
- **Min/Max Position Limits**: Configurable limits for each servo with validation
- **Block Programming**: Visual drag-and-drop style programming interface
- **Boundary Testing**: Test min/max limits for each servo individually
- **Save/Load Programs**: Export and import block programs as JSON
- **Save/Load Configuration**: Persist servo configurations and limits

## Installation

```bash
# Install with GUI dependencies
pip install -e ".[gui]"

# Or install all dependencies (dev mode)
pip install -e ".[dev]"
```

## Running the Application

```bash
# Using the entry point
st3215-controller

# Or directly
python -m gui.st3215_controller
```

## Usage

### Connection

1. Select the serial port (e.g., `COM3` or `/dev/ttyUSB0`)
2. Click **Connect** to establish connection
3. Status indicator shows connection state (green = connected)

### Servo Control

Each axis has:
- **Slider**: Drag to set target position
- **Position Display**: Shows current servo position
- **Spinbox**: Precise position input
- **Limits Display**: Red labels show min/max limits

### Configuring Limits

1. Click **Configure Limits** button
2. Set min/max positions for each axis (0-4095)
3. Enable/disable limits enforcement
4. Click **Save** to apply

### Block Programming

Add command blocks to create automated sequences:

- **Move**: Move a single axis to a position
- **Move All**: Move all axes simultaneously
- **Wait**: Pause execution for specified time
- **Speed**: Set movement speed
- **Test**: Test boundary limits for an axis

Click **Run Program** to execute the sequence.

### Tools Menu

- **Test All Boundaries**: Sequentially test limits for all servos
- **Write Limits to Servos**: Save limits to servo EEPROM

## File Formats

### Program JSON

```json
[
  {
    "block_type": "move",
    "axis": 0,
    "position": 2048,
    "speed": 100,
    "acceleration": 50
  },
  {
    "block_type": "wait",
    "wait_time": 1.0
  }
]
```

### Configuration JSON

```json
{
  "0": {
    "servo_id": 1,
    "name": "Axis 1",
    "limits": {
      "min_position": 100,
      "max_position": 4000,
      "enabled": true
    }
  }
}
```

## Architecture

```
gui/
├── __init__.py              # Package exports
├── st3215_controller.py     # Main GUI application
└── README.md                # This file
```

### Components

- `ServoControllerBackend`: Hardware abstraction layer
- `ST3215ControllerWindow`: Main window
- `ServoSliderWidget`: Individual servo control
- `BlockProgrammingWidget`: Visual programming interface
- `CommandBlockWidget`: Single command block display
- `ServoLimitsDialog`: Limits configuration dialog

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+S | Save Program |
| Ctrl+O | Load Program |
| Ctrl+Shift+S | Save Configuration |
| Ctrl+Shift+O | Load Configuration |
| Esc | Stop Program |

## Troubleshooting

### "Not Connected" Error

Ensure the servo controller is properly connected to the selected COM port.

### Servo Not Responding

Check:
- Power supply is adequate
- Wiring is correct
- Servo ID matches configuration

### Limits Not Enforced

Verify limits are enabled in the configuration dialog. Limits can be bypassed by setting `check_limits=False`.

## Safety Warnings

1. **Always test limits slowly** before running at full speed
2. **Verify wiring** before applying power
3. **Monitor temperature** during extended operation
4. **Use emergency stop** if unexpected behavior occurs
