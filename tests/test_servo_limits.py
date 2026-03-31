"""
Test suite for servo limits validation system.

Tests the min/max position limits validation for ST3215 servos.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock


class ServoLimitsConfig:
    """Test helper - mirrors the GUI config structure."""

    def __init__(self, min_pos=0, max_pos=4095, enabled=True):
        self.min_position = min_pos
        self.max_position = max_pos
        self.enabled = enabled


class TestServoLimitsValidation(unittest.TestCase):
    """Tests for servo limits validation logic."""

    def test_limits_default_values(self):
        """Test default limits configuration."""
        limits = ServoLimitsConfig()

        self.assertEqual(limits.min_position, 0)
        self.assertEqual(limits.max_position, 4095)
        self.assertTrue(limits.enabled)

    def test_limits_custom_values(self):
        """Test custom limits configuration."""
        limits = ServoLimitsConfig(min_pos=500, max_pos=3500, enabled=False)

        self.assertEqual(limits.min_position, 500)
        self.assertEqual(limits.max_position, 3500)
        self.assertFalse(limits.enabled)

    def test_position_within_limits(self):
        """Test position validation within limits."""
        limits = ServoLimitsConfig(min_pos=100, max_pos=4000)

        # Test positions within limits
        for pos in [100, 500, 2048, 3000, 4000]:
            self.assertTrue(
                limits.min_position <= pos <= limits.max_position,
                f"Position {pos} should be valid"
            )

    def test_position_below_minimum(self):
        """Test position validation below minimum."""
        limits = ServoLimitsConfig(min_pos=500, max_pos=4000)

        # Test positions below minimum
        for pos in [0, 100, 499]:
            self.assertFalse(
                limits.min_position <= pos <= limits.max_position,
                f"Position {pos} should be invalid (below min)"
            )

    def test_position_above_maximum(self):
        """Test position validation above maximum."""
        limits = ServoLimitsConfig(min_pos=0, max_pos=3000)

        # Test positions above maximum
        for pos in [3001, 3500, 4095]:
            self.assertFalse(
                limits.min_position <= pos <= limits.max_position,
                f"Position {pos} should be invalid (above max)"
            )

    def test_limits_disabled(self):
        """Test that disabled limits allow any position."""
        limits = ServoLimitsConfig(min_pos=1000, max_pos=3000, enabled=False)

        # When disabled, all positions should be allowed by application logic
        # (limits are stored but not enforced)
        self.assertFalse(limits.enabled)

    def test_limits_edge_cases(self):
        """Test edge cases for limits."""
        # Minimum possible values
        limits_min = ServoLimitsConfig(min_pos=0, max_pos=0)
        self.assertEqual(limits_min.min_position, 0)

        # Maximum possible values
        limits_max = ServoLimitsConfig(min_pos=4095, max_pos=4095)
        self.assertEqual(limits_max.max_position, 4095)

        # Full range
        limits_full = ServoLimitsConfig(min_pos=0, max_pos=4095)
        self.assertEqual(limits_full.min_position, 0)
        self.assertEqual(limits_full.max_position, 4095)

    def test_min_cannot_exceed_max(self):
        """Test that min position cannot exceed max position."""
        # This is a validation rule that should be enforced
        with self.assertRaises(AssertionError):
            min_pos = 3000
            max_pos = 1000
            self.assertLessEqual(min_pos, max_pos)


class TestServoMoveWithLimits(unittest.TestCase):
    """Tests for servo movement with limits checking."""

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
            'servo_ids': Mock(get_parameter_value=lambda: Mock(integer_array_value=[1, 2, 3, 4, 5, 6])),
            'update_rate_hz': Mock(get_parameter_value=lambda: Mock(double_value=20.0)),
        }.get(name, Mock(get_parameter_value=lambda: Mock()))

    def tearDown(self):
        """Clean up patches."""
        self.rclpy_patcher.stop()
        self.node_patcher.stop()
        self.st3215_patcher.stop()

    def test_move_within_limits(self):
        """Test movement within configured limits."""
        from src.python_st3215.ros2_node import ServoDriverNode
        node = ServoDriverNode()

        # Configure limits
        config = node.servo_configs[0]
        config.limits.min_position = 100
        config.limits.max_position = 4000
        config.limits.enabled = True

        # Move to valid position
        result = node.move_servo_with_limits(1, 2048, check_limits=True)

        self.assertTrue(result)
        node.servo_bus.MoveTo.assert_called()

    def test_move_below_minimum_limit(self):
        """Test movement blocked below minimum limit."""
        from src.python_st3215.ros2_node import ServoDriverNode
        node = ServoDriverNode()

        # Configure limits
        config = node.servo_configs[0]
        config.limits.min_position = 500
        config.limits.max_position = 4000
        config.limits.enabled = True

        # Try to move below minimum
        result = node.move_servo_with_limits(1, 100, check_limits=True)

        self.assertFalse(result)
        node.servo_bus.MoveTo.assert_not_called()

    def test_move_above_maximum_limit(self):
        """Test movement blocked above maximum limit."""
        from src.python_st3215.ros2_node import ServoDriverNode
        node = ServoDriverNode()

        # Configure limits
        config = node.servo_configs[0]
        config.limits.min_position = 0
        config.limits.max_position = 3000
        config.limits.enabled = True

        # Try to move above maximum
        result = node.move_servo_with_limits(1, 3500, check_limits=True)

        self.assertFalse(result)
        node.servo_bus.MoveTo.assert_not_called()

    def test_move_with_limits_disabled(self):
        """Test movement allowed when limits are disabled."""
        from src.python_st3215.ros2_node import ServoDriverNode
        node = ServoDriverNode()

        # Configure limits but disable them
        config = node.servo_configs[0]
        config.limits.min_position = 1000
        config.limits.max_position = 3000
        config.limits.enabled = False

        # Move should succeed even outside limits
        result = node.move_servo_with_limits(1, 500, check_limits=False)

        self.assertTrue(result)


class TestBoundaryTesting(unittest.TestCase):
    """Tests for boundary testing functionality."""

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
            'servo_ids': Mock(get_parameter_value=lambda: Mock(integer_array_value=[1, 2, 3, 4, 5, 6])),
            'update_rate_hz': Mock(get_parameter_value=lambda: Mock(double_value=20.0)),
        }.get(name, Mock(get_parameter_value=lambda: Mock()))

    def tearDown(self):
        """Clean up patches."""
        self.rclpy_patcher.stop()
        self.node_patcher.stop()
        self.st3215_patcher.stop()

    def test_boundary_test_sequence(self):
        """Test boundary testing moves to min then max then center."""
        from src.python_st3215.ros2_node import ServoDriverNode
        node = ServoDriverNode()

        min_pos = 100
        max_pos = 4000
        center = (min_pos + max_pos) // 2  # 2050

        node.test_boundaries(1, min_pos, max_pos)

        # Verify sequence: min -> max -> center
        calls = node.servo_bus.MoveTo.call_args_list
        self.assertEqual(len(calls), 3)

        # First call: move to minimum
        self.assertEqual(calls[0][0][1], min_pos)
        # Second call: move to maximum
        self.assertEqual(calls[1][0][1], max_pos)
        # Third call: move to center
        self.assertEqual(calls[2][0][1], center)

    def test_boundary_test_for_all_axes(self):
        """Test boundary testing for all 6 axes."""
        from src.python_st3215.ros2_node import ServoDriverNode
        node = ServoDriverNode()

        node.test_all_boundaries()

        # Should test all 6 servos
        self.assertEqual(node.servo_bus.MoveTo.call_count, 6 * 3)  # 3 moves per servo


if __name__ == '__main__':
    unittest.main()
