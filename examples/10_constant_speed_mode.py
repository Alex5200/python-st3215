"""
Use constant speed mode to make servo rotate continuously.
"""

import os
import time
from python_st3215 import ST3215

controller = ST3215(os.environ.get("ST3215_PORT", "/dev/ttyUSB0"))

try:
    servo = controller.wrap_servo(1)

    print("Switching to constant speed mode (mode 1)...")
    servo.eeprom.write_operating_mode(1)
    servo.sram.torque_enable()

    print("Rotating clockwise at speed 500...")
    servo.sram.write_running_speed(500)
    time.sleep(3)

    print("Rotating counter-clockwise at speed -500...")
    servo.sram.write_running_speed(-500)
    time.sleep(3)

    print("Fast rotation at speed 1500...")
    servo.sram.write_running_speed(1500)
    time.sleep(2)

    print("Stopping...")
    servo.sram.write_running_speed(0)
    time.sleep(1)

    print("Switching back to position control mode (mode 0)...")
    servo.sram.torque_disable()
    servo.eeprom.write_operating_mode(0)
finally:
    controller.close()
