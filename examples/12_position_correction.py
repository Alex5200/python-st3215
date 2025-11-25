"""
Use position correction to offset the zero position.
"""

import os
import time
from python_st3215 import ST3215

controller = ST3215(os.environ.get("ST3215_PORT", "/dev/ttyUSB0"))

try:
    servo = controller.wrap_servo(1)

    original_correction = servo.eeprom.read_position_correction()
    print(f"Original position correction: {original_correction}")

    servo.sram.torque_enable()
    servo.sram.write_acceleration(50)

    print("\nMoving to 2048 with no correction...")
    servo.eeprom.write_position_correction(0)
    servo.sram.write_target_location(2048)
    time.sleep(1.5)
    print(f"Actual position: {servo.sram.read_current_location()}")

    print("\nApplying +500 correction...")
    servo.eeprom.write_position_correction(500)
    servo.sram.write_target_location(2048)
    time.sleep(1.5)
    print(f"Actual position: {servo.sram.read_current_location()}")

    print("\nApplying -500 correction...")
    servo.eeprom.write_position_correction(-500)
    servo.sram.write_target_location(2048)
    time.sleep(1.5)
    print(f"Actual position: {servo.sram.read_current_location()}")

    print("\nRestoring original correction...")
    servo.eeprom.write_position_correction(original_correction)

    servo.sram.torque_disable()
finally:
    controller.close()
