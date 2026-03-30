from .st3215 import ST3215
from .errors import ST3215Error, ServoNotRespondingError, InvalidInstructionError
from .servo import Servo

__version__ = "1.1.0"

__all__ = [
    "ST3215",
    "ST3215Error",
    "ServoNotRespondingError",
    "InvalidInstructionError",
    "Servo",
    "__version__",
]

# ROS2 integration (optional, requires rclpy)
try:
    from .ros2_node import ServoDriverNode, main
    __all__.extend(["ServoDriverNode", "main"])
except ImportError:
    pass
