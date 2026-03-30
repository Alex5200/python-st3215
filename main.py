"""
ROS2 Servo Driver Node - Entry Point.

This module provides the entry point for running the ST3215 servo driver node.
For the actual implementation, see src/python_st3215/ros2_node.py.

Usage:
    ros2 run python_st3215 servo_driver_node
    OR
    python main.py
"""

from src.python_st3215.ros2_node import ServoDriverNode, main

__all__ = ['ServoDriverNode', 'main']

if __name__ == '__main__':
    main()