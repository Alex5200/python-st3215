"""
Change a servo's ID.  USE WITH CAUTION - only one servo should be connected!
"""

import os
from python_st3215 import ST3215

OLD_ID = 1
NEW_ID = 5

controller = ST3215(os.environ.get("ST3215_PORT", "/dev/ttyUSB0"))

try:
    print("=" * 60)
    print("CHANGE SERVO ID")
    print("=" * 60)
    print("\nWARNING: Only connect ONE servo to avoid ID conflicts!")
    print(f"This will change servo ID from {OLD_ID} to {NEW_ID}")

    response = input("\nType 'yes' to continue: ")
    if response.lower() != "yes":
        print("Cancelled.")
    else:
        servo = controller.wrap_servo(OLD_ID)

        print(f"\nCurrent ID: {servo.eeprom.read_id()}")
        print(f"Changing to ID {NEW_ID}...")

        servo.eeprom.write_id(NEW_ID)

        print("\nVerifying change...")
        new_servo = controller.wrap_servo(NEW_ID)
        confirmed_id = new_servo.eeprom.read_id()

        if confirmed_id == NEW_ID:
            print(f"✓ Successfully changed to ID {NEW_ID}")
        else:
            print(f"✗ Failed to change ID (read: {confirmed_id})")
finally:
    controller.close()
