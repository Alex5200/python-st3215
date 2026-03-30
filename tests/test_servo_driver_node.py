"""
Test suite for ServoDriverNode - ROS2 servo driver node.
Follows TDD principles: tests first, then implementation.

Run with: pytest tests/test_servo_driver_node.py -v
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call


class TestServoDriverNodeInitialization(unittest.TestCase):
    """Tests for ServoDriverNode initialization."""

    @patch('src.python_st3215.ros2_node.ST3215')
    @patch('rclpy.create_node')
    @patch('rclpy.init')
    def test_node_creates_with_default_params(self, mock_init, mock_node, mock_st3215):
        """Node should initialize with default parameters."""
        mock_node_instance = Mock()
        mock_node.return_value = mock_node_instance

        # Mock parameter declarations
        mock_node_instance.get_parameter.side_effect = lambda name: {
            'port': Mock(get_parameter_value=lambda: Mock(string_value='COM3')),
            'servo_ids': Mock(get_parameter_value=lambda: Mock(integer_array_value=[1, 2, 3, 4, 5, 6])),
            'update_rate_hz': Mock(get_parameter_value=lambda: Mock(double_value=20.0)),
        }.get(name, Mock(get_parameter_value=lambda: Mock()))

        from src.python_st3215.ros2_node import ServoDriverNode
        node = ServoDriverNode()

        self.assertEqual(node.port, 'COM3')
        self.assertEqual(node.ids, [1, 2, 3, 4, 5, 6])
        self.assertEqual(node.rate, 20.0)

    @patch('src.python_st3215.ros2_node.ST3215')
    @patch('rclpy.create_node')
    @patch('rclpy.init')
    def test_node_initializes_servo_bus(self, mock_init, mock_node, mock_st3215):
        """Node should initialize ST3215 connection on startup."""
        mock_node_instance = Mock()
        mock_node.return_value = mock_node_instance
        mock_node_instance.get_parameter.side_effect = lambda name: {
            'port': Mock(get_parameter_value=lambda: Mock(string_value='COM3')),
            'servo_ids': Mock(get_parameter_value=lambda: Mock(integer_array_value=[1, 2, 3])),
            'update_rate_hz': Mock(get_parameter_value=lambda: Mock(double_value=20.0)),
        }.get(name, Mock(get_parameter_value=lambda: Mock()))

        mock_servo_bus = Mock()
        mock_st3215.return_value = mock_servo_bus

        from src.python_st3215.ros2_node import ServoDriverNode
        node = ServoDriverNode()

        mock_st3215.assert_called_once_with('COM3')
        self.assertEqual(node.servo_bus, mock_servo_bus)

    @patch('src.python_st3215.ros2_node.ST3215', side_effect=Exception('Connection failed'))
    @patch('rclpy.create_node')
    @patch('rclpy.init')
    def test_node_raises_on_connection_failure(self, mock_init, mock_node, mock_st3215):
        """Node should raise exception when servo connection fails."""
        from src.python_st3215.ros2_node import ServoDriverNode

        with self.assertRaises(Exception) as ctx:
            ServoDriverNode()

        self.assertEqual(str(ctx.exception), 'Connection failed')

    @patch('src.python_st3215.ros2_node.ST3215')
    @patch('rclpy.create_node')
    @patch('rclpy.init')
    def test_node_creates_publishers(self, mock_init, mock_node, mock_st3215):
        """Node should create required publishers on initialization."""
        mock_node_instance = Mock()
        mock_node.return_value = mock_node_instance
        mock_node_instance.create_publisher = Mock()

        mock_node_instance.get_parameter.side_effect = lambda name: {
            'port': Mock(get_parameter_value=lambda: Mock(string_value='COM3')),
            'servo_ids': Mock(get_parameter_value=lambda: Mock(integer_array_value=[1, 2, 3])),
            'update_rate_hz': Mock(get_parameter_value=lambda: Mock(double_value=20.0)),
        }.get(name, Mock(get_parameter_value=lambda: Mock()))

        from src.python_st3215.ros2_node import ServoDriverNode
        node = ServoDriverNode()

        # Verify publishers were created
        self.assertEqual(mock_node_instance.create_publisher.call_count, 3)
        calls = mock_node_instance.create_publisher.call_args_list

        # Check each publisher was created with correct topic
        publisher_topics = [c[0][1] for c in calls]
        self.assertIn('/servos/joint_states', publisher_topics)
        self.assertIn('/servos/temperatures', publisher_topics)
        self.assertIn('/servos/is_moving', publisher_topics)

    @patch('src.python_st3215.ros2_node.ST3215')
    @patch('rclpy.create_node')
    @patch('rclpy.init')
    def test_node_creates_subscriber(self, mock_init, mock_node, mock_st3215):
        """Node should create command subscriber on initialization."""
        mock_node_instance = Mock()
        mock_node.return_value = mock_node_instance
        mock_node_instance.create_subscription = Mock()

        mock_node_instance.get_parameter.side_effect = lambda name: {
            'port': Mock(get_parameter_value=lambda: Mock(string_value='COM3')),
            'servo_ids': Mock(get_parameter_value=lambda: Mock(integer_array_value=[1, 2, 3])),
            'update_rate_hz': Mock(get_parameter_value=lambda: Mock(double_value=20.0)),
        }.get(name, Mock(get_parameter_value=lambda: Mock()))

        from src.python_st3215.ros2_node import ServoDriverNode
        node = ServoDriverNode()

        mock_node_instance.create_subscription.assert_called()
        call_args = mock_node_instance.create_subscription.call_args
        self.assertEqual(call_args[0][1], '/servos/command')

    @patch('src.python_st3215.ros2_node.ST3215')
    @patch('rclpy.create_node')
    @patch('rclpy.init')
    def test_node_creates_timer(self, mock_init, mock_node, mock_st3215):
        """Node should create timer with correct frequency."""
        mock_node_instance = Mock()
        mock_node.return_value = mock_node_instance
        mock_node_instance.create_timer = Mock()

        mock_node_instance.get_parameter.side_effect = lambda name: {
            'port': Mock(get_parameter_value=lambda: Mock(string_value='COM3')),
            'servo_ids': Mock(get_parameter_value=lambda: Mock(integer_array_value=[1, 2, 3])),
            'update_rate_hz': Mock(get_parameter_value=lambda: Mock(double_value=20.0)),
        }.get(name, Mock(get_parameter_value=lambda: Mock()))

        from src.python_st3215.ros2_node import ServoDriverNode
        node = ServoDriverNode()

        mock_node_instance.create_timer.assert_called()
        call_args = mock_node_instance.create_timer.call_args
        # Timer period should be 1/rate = 1/20 = 0.05 seconds
        self.assertEqual(call_args[0][0], 0.05)


class TestCommandCallback(unittest.TestCase):
    """Tests for command_callback method."""

    def setUp(self):
        """Set up test fixtures."""
        self.rclpy_patcher = patch('rclpy.init')
        self.node_patcher = patch('rclpy.create_node')
        self.st3215_patcher = patch('src.python_st3215.ros2_node.ST3215')

        self.mock_rclpy = self.rclpy_patcher.start()
        self.mock_node = self.node_patcher.start()
        self.mock_st3215 = self.st3215_patcher.start()

        mock_node_instance = Mock()
        self.mock_node.return_value = mock_node_instance
        mock_node_instance.get_parameter.side_effect = lambda name: {
            'port': Mock(get_parameter_value=lambda: Mock(string_value='COM3')),
            'servo_ids': Mock(get_parameter_value=lambda: Mock(integer_array_value=[1, 2, 3])),
            'update_rate_hz': Mock(get_parameter_value=lambda: Mock(double_value=20.0)),
        }.get(name, Mock(get_parameter_value=lambda: Mock()))

    def tearDown(self):
        """Clean up patches."""
        self.rclpy_patcher.stop()
        self.node_patcher.stop()
        self.st3215_patcher.stop()

    def test_command_callback_validates_length(self):
        """Callback should reject commands with mismatched array length."""
        from src.python_st3215.ros2_node import ServoDriverNode
        node = ServoDriverNode()

        # Command with wrong length
        mock_msg = Mock()
        mock_msg.data = [100, 200]  # Only 2 values, expected 3

        node.command_callback(mock_msg)

        self.mock_node.return_value.get_logger().warn.assert_called()

    def test_command_callback_sends_positions(self):
        """Callback should send target positions to all servos."""
        from src.python_st3215.ros2_node import ServoDriverNode
        node = ServoDriverNode()

        mock_msg = Mock()
        mock_msg.data = [100, 200, 300]

        node.command_callback(mock_msg)

        # Verify MoveTo was called for each servo
        self.assertEqual(node.servo_bus.MoveTo.call_count, 3)
        node.servo_bus.MoveTo.assert_any_call(1, 100, speed=100, acc=50, wait=False)
        node.servo_bus.MoveTo.assert_any_call(2, 200, speed=100, acc=50, wait=False)
        node.servo_bus.MoveTo.assert_any_call(3, 300, speed=100, acc=50, wait=False)

    def test_command_callback_handles_errors_gracefully(self):
        """Callback should handle individual servo errors without crashing."""
        from src.python_st3215.ros2_node import ServoDriverNode
        node = ServoDriverNode()

        # Make second servo fail
        node.servo_bus.MoveTo.side_effect = [
            None,  # First succeeds
            Exception("Servo error"),  # Second fails
            None   # Third succeeds
        ]

        mock_msg = Mock()
        mock_msg.data = [100, 200, 300]

        # Should not raise
        node.command_callback(mock_msg)

        # Logger should report error
        self.mock_node.return_value.get_logger().error.assert_called()


class TestTimerCallback(unittest.TestCase):
    """Tests for timer_callback method."""

    def setUp(self):
        """Set up test fixtures."""
        self.rclpy_patcher = patch('rclpy.init')
        self.node_patcher = patch('rclpy.create_node')
        self.st3215_patcher = patch('src.python_st3215.ros2_node.ST3215')

        self.mock_rclpy = self.rclpy_patcher.start()
        self.mock_node = self.node_patcher.start()
        self.mock_st3215 = self.st3215_patcher.start()

        mock_node_instance = Mock()
        self.mock_node.return_value = mock_node_instance
        mock_node_instance.get_parameter.side_effect = lambda name: {
            'port': Mock(get_parameter_value=lambda: Mock(string_value='COM3')),
            'servo_ids': Mock(get_parameter_value=lambda: Mock(integer_array_value=[1, 2, 3])),
            'update_rate_hz': Mock(get_parameter_value=lambda: Mock(double_value=20.0)),
        }.get(name, Mock(get_parameter_value=lambda: Mock()))

    def tearDown(self):
        """Clean up patches."""
        self.rclpy_patcher.stop()
        self.node_patcher.stop()
        self.st3215_patcher.stop()

    def test_timer_callback_reads_all_servos(self):
        """Timer should read position, load, temperature from all servos."""
        from src.python_st3215.ros2_node import ServoDriverNode
        node = ServoDriverNode()

        # Mock servo responses
        node.servo_bus.ReadPosition.side_effect = [100, 200, 300]
        node.servo_bus.ReadLoad.side_effect = [10, 20, 30]
        node.servo_bus.ReadTemperature.side_effect = [35, 40, 45]
        node.servo_bus.IsMoving.side_effect = [False, False, False]

        node.timer_callback()

        # Verify all servos were read
        self.assertEqual(node.servo_bus.ReadPosition.call_count, 3)
        self.assertEqual(node.servo_bus.ReadLoad.call_count, 3)
        self.assertEqual(node.servo_bus.ReadTemperature.call_count, 3)
        self.assertEqual(node.servo_bus.IsMoving.call_count, 3)

    def test_timer_callback_publishes_joint_state(self):
        """Timer should publish JointState with correct data."""
        from src.python_st3215.ros2_node import ServoDriverNode
        node = ServoDriverNode()

        node.servo_bus.ReadPosition.side_effect = [100, 200, 300]
        node.servo_bus.ReadLoad.side_effect = [10, 20, 30]
        node.servo_bus.ReadTemperature.side_effect = [35, 40, 45]
        node.servo_bus.IsMoving.side_effect = [False, False, False]

        mock_publisher = Mock()
        self.mock_node.return_value.create_publisher.side_effect = [
            mock_publisher, Mock(), Mock()
        ]

        node.timer_callback()

        mock_publisher.publish.assert_called()
        published_msg = mock_publisher.publish.call_args[0][0]

        self.assertEqual(len(published_msg.position), 3)
        self.assertEqual(published_msg.position, [100.0, 200.0, 300.0])
        self.assertEqual(published_msg.effort, [10.0, 20.0, 30.0])

    def test_timer_callback_publishes_temperature(self):
        """Timer should publish temperature array."""
        from src.python_st3215.ros2_node import ServoDriverNode
        node = ServoDriverNode()

        node.servo_bus.ReadPosition.side_effect = [100, 200, 300]
        node.servo_bus.ReadLoad.side_effect = [10, 20, 30]
        node.servo_bus.ReadTemperature.side_effect = [35, 40, 45]
        node.servo_bus.IsMoving.side_effect = [False, False, False]

        temp_publisher = Mock()
        self.mock_node.return_value.create_publisher.side_effect = [
            Mock(), temp_publisher, Mock()
        ]

        node.timer_callback()

        temp_publisher.publish.assert_called()
        published_msg = temp_publisher.publish.call_args[0][0]
        self.assertEqual(published_msg.data, [35.0, 40.0, 45.0])

    def test_timer_callback_detects_moving_status(self):
        """Timer should detect if any servo is moving."""
        from src.python_st3215.ros2_node import ServoDriverNode
        node = ServoDriverNode()

        node.servo_bus.ReadPosition.side_effect = [100, 200, 300]
        node.servo_bus.ReadLoad.side_effect = [10, 20, 30]
        node.servo_bus.ReadTemperature.side_effect = [35, 40, 45]
        # Second servo is moving
        node.servo_bus.IsMoving.side_effect = [False, True, False]

        moving_publisher = Mock()
        self.mock_node.return_value.create_publisher.side_effect = [
            Mock(), Mock(), moving_publisher
        ]

        node.timer_callback()

        moving_publisher.publish.assert_called()
        published_msg = moving_publisher.publish.call_args[0][0]
        self.assertTrue(published_msg.data)

    def test_timer_callback_handles_read_errors(self):
        """Timer should handle read errors gracefully."""
        from src.python_st3215.ros2_node import ServoDriverNode
        node = ServoDriverNode()

        # First servo fails, others succeed
        node.servo_bus.ReadPosition.side_effect = [
            Exception("Read error"),
            200, 300
        ]
        node.servo_bus.ReadLoad.side_effect = [0, 20, 30]
        node.servo_bus.ReadTemperature.side_effect = [0, 40, 45]
        node.servo_bus.IsMoving.side_effect = [False, False, False]

        # Should not raise
        node.timer_callback()

        # Should log warning
        self.mock_node.return_value.get_logger().warn.assert_called()


class TestServoDriverNodeIntegration(unittest.TestCase):
    """Integration tests for the complete node lifecycle."""

    @patch('src.python_st3215.ros2_node.ST3215')
    @patch('rclpy.create_node')
    @patch('rclpy.init')
    def test_full_command_and_read_cycle(self, mock_init, mock_node, mock_st3215):
        """Test complete cycle: send command, then read back positions."""
        mock_node_instance = Mock()
        mock_node.return_value = mock_node_instance
        mock_node_instance.get_parameter.side_effect = lambda name: {
            'port': Mock(get_parameter_value=lambda: Mock(string_value='COM3')),
            'servo_ids': Mock(get_parameter_value=lambda: Mock(integer_array_value=[1, 2])),
            'update_rate_hz': Mock(get_parameter_value=lambda: Mock(double_value=20.0)),
        }.get(name, Mock(get_parameter_value=lambda: Mock()))

        mock_servo_bus = Mock()
        mock_st3215.return_value = mock_servo_bus

        from src.python_st3215.ros2_node import ServoDriverNode
        node = ServoDriverNode()

        # Send command
        mock_msg = Mock()
        mock_msg.data = [500, 600]
        node.command_callback(mock_msg)

        # Verify command sent
        self.assertEqual(mock_servo_bus.MoveTo.call_count, 2)

        # Simulate read back
        mock_servo_bus.ReadPosition.side_effect = [500, 600]
        mock_servo_bus.ReadLoad.side_effect = [15, 25]
        mock_servo_bus.ReadTemperature.side_effect = [40, 42]
        mock_servo_bus.IsMoving.side_effect = [True, True]

        node.timer_callback()

        # Verify reads happened
        self.assertEqual(mock_servo_bus.ReadPosition.call_count, 2)


class TestMainFunction(unittest.TestCase):
    """Tests for the main entry point."""

    @patch('src.python_st3215.ros2_node.ST3215')
    @patch('rclpy.create_node')
    @patch('rclpy.init')
    @patch('rclpy.spin')
    @patch('rclpy.shutdown')
    def test_main_runs_without_keyboard_interrupt(
        self, mock_shutdown, mock_spin, mock_init, mock_node, mock_st3215
    ):
        """Main should run rclpy.spin until shutdown."""
        mock_node_instance = Mock()
        mock_node.return_value = mock_node_instance
        mock_node_instance.get_parameter.side_effect = lambda name: {
            'port': Mock(get_parameter_value=lambda: Mock(string_value='COM3')),
            'servo_ids': Mock(get_parameter_value=lambda: Mock(integer_array_value=[1, 2, 3])),
            'update_rate_hz': Mock(get_parameter_value=lambda: Mock(double_value=20.0)),
        }.get(name, Mock(get_parameter_value=lambda: Mock()))

        from src.python_st3215.ros2_node import main
        main()

        mock_spin.assert_called()
        mock_shutdown.assert_called()

    @patch('src.python_st3215.ros2_node.ST3215')
    @patch('rclpy.create_node')
    @patch('rclpy.init')
    @patch('rclpy.spin', side_effect=KeyboardInterrupt())
    @patch('rclpy.shutdown')
    def test_main_handles_keyboard_interrupt(
        self, mock_shutdown, mock_spin, mock_init, mock_node, mock_st3215
    ):
        """Main should handle Ctrl+C gracefully."""
        mock_node_instance = Mock()
        mock_node.return_value = mock_node_instance
        mock_node_instance.get_parameter.side_effect = lambda name: {
            'port': Mock(get_parameter_value=lambda: Mock(string_value='COM3')),
            'servo_ids': Mock(get_parameter_value=lambda: Mock(integer_array_value=[1, 2, 3])),
            'update_rate_hz': Mock(get_parameter_value=lambda: Mock(double_value=20.0)),
        }.get(name, Mock(get_parameter_value=lambda: Mock()))

        from src.python_st3215.ros2_node import main

        # Should not raise
        main()

        mock_shutdown.assert_called()


if __name__ == '__main__':
    unittest.main()
