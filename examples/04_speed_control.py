"""
Control servo movement speed using acceleration parameter.
"""

import os
import time
from python_st3215 import ST3215

controller = ST3215(os.environ.get("ST3215_PORT", "/dev/ttyUSB0"))

try:
    servo = controller.wrap_servo(1)
    servo.sram.torque_enable()

    print("Slow movement (acceleration = 10)...")
    servo.sram.write_acceleration(10)
    servo.sram.write_target_location(3000)
    time.sleep(2)

    print("Fast movement (acceleration = 100)...")
    servo.sram.write_acceleration(100)
    servo.sram.write_target_location(1000)
    time.sleep(2)

    print("Very fast movement (acceleration = 254)...")
    servo.sram.write_acceleration(254)
    servo.sram.write_target_location(2048)
    time.sleep(2)

    servo.sram.torque_disable()
finally:
    controller.close()
