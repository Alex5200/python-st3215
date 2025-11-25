"""
Read servo load to detect when it's being blocked or resisted.
"""

import os
import time
from python_st3215 import ST3215

controller = ST3215(os.environ.get("ST3215_PORT", "/dev/ttyUSB0"))

try:
    servo = controller.wrap_servo(1)
    servo.sram.torque_enable()
    servo.sram.write_acceleration(50)

    print("Moving servo.  Try to resist the movement to see load change.")
    print("Press Ctrl+C to exit.\n")

    positions = [1000, 3000]
    pos_index = 0

    while True:
        servo.sram.write_target_location(positions[pos_index])
        pos_index = (pos_index + 1) % 2

        for _ in range(15):
            load = servo.sram.read_current_load()
            load_percent = load / 10
            position = servo.sram.read_current_location()

            bar_length = int(load_percent / 2)
            bar = "█" * bar_length + "░" * (50 - bar_length)

            print(
                f"Pos: {position:4d} | Load: {load_percent:5.1f}% [{bar}]\033[K",
                end="\r",
            )
            time.sleep(0.1)

except KeyboardInterrupt:
    print("\nStopped.")
    servo.sram.torque_disable()
finally:
    controller.close()
