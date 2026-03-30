"""
ROS2 Node for ST3215 Servo Driver.

This module provides a ROS2 node that interfaces with ST3215 smart servos,
publishing joint states and accepting movement commands.

Design Principles:
- Testable: Dependencies injected where possible
- Single Responsibility: Node handles ROS2 integration only
- Error Handling: Graceful degradation on servo read/write failures
"""

import rclpy
from rclpy.node import Node
from rclpy.timer import Timer
from sensor_msgs.msg import JointState
from std_msgs.msg import Float32MultiArray, Bool

from .st3215 import ST3215


class ServoDriverNode(Node):
    """
    ROS2 node for ST3215 servo driver.

    Publishers:
        /servos/joint_states (JointState): Position, velocity, effort for all servos
        /servos/temperatures (Float32MultiArray): Temperature readings
        /servos/is_moving (Bool): Combined moving status (True if any servo moving)

    Subscribers:
        /servos/command (Float32MultiArray): Target positions for all servos

    Parameters:
        port (str): Serial port (default: 'COM3')
        servo_ids (integer_array): List of servo IDs (default: [1,2,3,4,5,6])
        update_rate_hz (double): Polling rate (default: 20.0)
    """

    def __init__(
        self,
        port: str = 'COM3',
        servo_ids: list[int] | None = None,
        update_rate_hz: float = 20.0,
        servo_bus: ST3215 | None = None,
    ) -> None:
        """
        Initialize the servo driver node.

        Args:
            port: Serial port for servo communication
            servo_ids: List of servo IDs to control
            update_rate_hz: Timer frequency for polling
            servo_bus: Optional ST3215 instance for dependency injection (testing)
        """
        super().__init__('servo_driver_node')

        # Configuration
        self.port = port
        self.ids = servo_ids if servo_ids is not None else [1, 2, 3, 4, 5, 6]
        self.rate = update_rate_hz

        # Servo bus initialization (supports dependency injection)
        if servo_bus is not None:
            self.servo_bus = servo_bus
        else:
            self.servo_bus = self._init_servo_bus(port)

        # Publishers
        self.pub_joint_state = self.create_publisher(
            JointState, '/servos/joint_states', 10
        )
        self.pub_temp = self.create_publisher(
            Float32MultiArray, '/servos/temperatures', 10
        )
        self.pub_moving = self.create_publisher(
            Bool, '/servos/is_moving', 10
        )

        # Subscriber
        self.sub_command = self.create_subscription(
            Float32MultiArray,
            '/servos/command',
            self.command_callback,
            10
        )

        # Timer
        self.timer = self.create_timer(
            1.0 / self.rate,
            self.timer_callback
        )

        self.get_logger().info(f"Servo Driver Node started for IDs: {self.ids}")

    def _init_servo_bus(self, port: str) -> ST3215:
        """Initialize ST3215 connection."""
        try:
            servo_bus = ST3215(port)
            self.get_logger().info(f"Connected to {port}")
            return servo_bus
        except Exception as e:
            self.get_logger().error(f"Failed to connect to {port}: {e}")
            raise

    def command_callback(self, msg: Float32MultiArray) -> None:
        """
        Handle incoming movement commands.

        Args:
            msg: Float32MultiArray with target positions for each servo
        """
        targets = msg.data

        if len(targets) != len(self.ids):
            self.get_logger().warning(
                f"Command length mismatch! Expected {len(self.ids)}, got {len(targets)}"
            )
            return

        self.get_logger().info("Received movement command")

        for i, servo_id in enumerate(self.ids):
            target_pos = int(targets[i])
            try:
                self.servo_bus.MoveTo(
                    servo_id, target_pos, speed=100, acc=50, wait=False
                )
            except Exception as e:
                self.get_logger().error(f"Failed to move servo {servo_id}: {e}")

    def timer_callback(self) -> None:
        """
        Periodic callback to read servo states and publish updates.

        Reads position, load (effort), temperature, and moving status from all servos.
        Publishes to joint_states, temperatures, and is_moving topics.
        """
        joint_msg = JointState()
        temp_data: list[float] = []
        any_moving = False

        joint_msg.header.stamp = self.get_clock().now().to_msg()
        joint_msg.name = [f"servo_{id}" for id in self.ids]

        for servo_id in self.ids:
            try:
                # Read position
                position = self.servo_bus.ReadPosition(servo_id)
                joint_msg.position.append(float(position))
                joint_msg.velocity.append(0.0)

                # Read load/effort
                try:
                    load = self.servo_bus.ReadLoad(servo_id)
                except AttributeError:
                    load = 0.0
                joint_msg.effort.append(float(load))

                # Read temperature
                try:
                    temp = self.servo_bus.ReadTemperature(servo_id)
                except AttributeError:
                    temp = 0.0
                temp_data.append(float(temp))

                # Check moving status
                is_moving = self.servo_bus.IsMoving(servo_id)
                if is_moving:
                    any_moving = True

            except Exception as e:
                self.get_logger().warning(f"Error reading servo {servo_id}: {e}")
                # Fill with zeros on error
                joint_msg.position.append(0.0)
                joint_msg.effort.append(0.0)
                temp_data.append(0.0)

        # Publish all messages
        temp_msg = Float32MultiArray(data=temp_data)
        moving_msg = Bool(data=any_moving)

        self.pub_joint_state.publish(joint_msg)
        self.pub_temp.publish(temp_msg)
        self.pub_moving.publish(moving_msg)


def main(args: list[str] | None = None) -> None:
    """
    Entry point for the servo driver node.

    Args:
        args: Command line arguments (passed to rclpy.init)
    """
    rclpy.init(args=args)

    node = ServoDriverNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
