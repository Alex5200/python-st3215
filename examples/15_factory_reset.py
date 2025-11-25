"""
Example script to reset an ST3215 servo to factory settings.
"""

import os
import time
from python_st3215 import ST3215

controller = ST3215(os.environ.get("ST3215_PORT", "/dev/ttyUSB0"))

try:
    servo = controller.wrap_servo(1)
    servo.sram.torque_enable()

    print("Resetting servo to factory settings...")
    servo.reset()
    print("Servo has been reset to factory settings.")

    print("Waiting for servo to come back online...")
    timeout = 5
    start = time.time()
    while time.time() - start < timeout:
        try:
            if servo.ping():
                print("Servo is back!")
                break
        except Exception:
            pass
        time.sleep(0.2)
    else:
        print("Timeout: Servo did not come back online within 5 seconds.")
finally:
    controller.close()
