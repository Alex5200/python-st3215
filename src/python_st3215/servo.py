from __future__ import annotations
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from .st3215 import ST3215

from .instructions import Instruction
from .registers import _EEPROMRegisters, SRAMRegisters


class Servo:
    def __init__(self, controller: "ST3215", servo_id: int):
        self.controller = controller
        self.id = servo_id
        self.logger = controller.logger
        self.eeprom = _EEPROMRegisters(self)
        self.sram = SRAMRegisters(self)

    def send(
        self, instruction: int | Instruction, parameters: Sequence[int] | None = None
    ):
        self.logger.debug(
            f"Servo {self.id}: sending instruction {instruction} with parameters {parameters}"
        )
        packet = self.controller.send_instruction(self.id, instruction, parameters)
        response = self.controller.read_response(packet)
        if response:
            parsed = self.controller.parse_response(response)
            self.logger.debug(f"Servo {self.id}: received response {parsed}")
            return parsed
        self.logger.warning(
            f"Servo {self.id}: no response received for instruction {instruction}"
        )
        return None

    def ping(self):
        """Send PING command to the servo to check if it is responsive."""
        return self.controller.ping(self.id)

    def action(self):
        """Send ACTION command to the servo to execute all registered commands."""
        self.logger.debug(f"Sending ACTION command to servo {self.id}")
        return self.send(Instruction.ACTION)

    def reset(self):
        """Send RESET command to the servo to reset it to factory defaults."""
        self.logger.debug(f"Sending RESET command to servo {self.id}")
        return self.send(Instruction.RESET)

    def _read_memory(self, address: int, length: int = 1):
        self.logger.debug(
            f"Reading {length} bytes from address {address:#02x} on servo {self.id}"
        )
        response = self.send(Instruction.READ, [address, length])
        if response and response["parameters"]:
            data = response["parameters"]
            if length == 1:
                return data[0]
            value = 0
            for i, byte in enumerate(data):
                value |= byte << (8 * i)
            self.logger.debug(
                f"Read value {value} (0x{value:04X}) from servo {self.id}"
            )
            return value
        self.logger.warning(
            f"Failed to read memory from servo {self.id} at address {address:#02x}"
        )
        return None

    def _write_memory(self, address: int, values: Sequence[int]):
        if not isinstance(values, Sequence):
            values = [values]
        self.logger.debug(
            f"Writing values {values} to address {address:#02x} on servo {self.id}"
        )
        return self.send(Instruction.WRITE, [address, *values])

    def _reg_write_memory(self, address: int, values: Sequence[int]):
        if not isinstance(values, Sequence):
            values = [values]
        self.logger.debug(
            f"Reg Writing values {values} to address {address:#02x} on servo {self.id}"
        )
        return self.send(Instruction.REG_WRITE, [address, *values])

    def _sync_read(self, address: int, data_length: int, servo_ids: Sequence[int]):
        """
        Send SYNC READ command to query multiple servos at the same time.

        Args:
            address: The first address to read data from
            data_length: Length of data to read from each servo (must be same for all)
            servo_ids: List of servo IDs to query

        Returns:
            Dictionary mapping servo_id to response data
            e.g., {1: {'id': 1, 'status': 0, 'parameters': [...]},
                   2: {'id': 2, 'status': 0, 'parameters': [...]}}
        """
        # TODO: Make functions work with this method
        self.logger.debug(
            f"SYNC READ from address {address:#02x}, length {data_length} "
            f"for servos {servo_ids}"
        )

        parameters = [address, data_length, *servo_ids]
        packet = self.controller.send_instruction(
            0xFE, Instruction.SYNC_READ, parameters
        )

        responses = {}
        for servo_id in servo_ids:
            response = self.controller.read_response(packet)
            if response:
                parsed = self.controller.parse_response(response)
                self.logger.debug(
                    f"Servo {servo_id}: received SYNC READ response {parsed}"
                )
                responses[servo_id] = parsed
            else:
                self.logger.warning(
                    f"Servo {servo_id}: no response received for SYNC READ"
                )
                responses[servo_id] = None

        return responses

    def _sync_write(
        self, address: int, data_length: int, servo_data: dict[int, Sequence[int]]
    ):
        """
        Send SYNC WRITE command to control multiple servos at the same time.

        Args:
            address: The first address to write data to
            data_length: Length of data to write to each servo (must be same for all)
            servo_data: Dictionary mapping servo_id to list of data values
                       e.g., {1: [0x00, 0x08, 0x00, 0x00, 0xE8, 0x03],
                              2: [0x00, 0x08, 0x00, 0x00, 0xE8, 0x03]}

        Returns:
            None (broadcast ID is used, no response expected)
        """
        # TODO: Make functions work with this method
        self.logger.debug(
            f"SYNC WRITE to address {address:#02x} for {len(servo_data)} servos"
        )

        parameters = [address, data_length]

        for servo_id, data in servo_data.items():
            if len(data) != data_length:
                raise ValueError(
                    f"Servo {servo_id} data length {len(data)} does not match "
                    f"specified length {data_length}"
                )
            parameters.append(servo_id)
            parameters.extend(data)

        self.controller.send_instruction(0xFE, Instruction.SYNC_WRITE, parameters)
        self.logger.debug(f"SYNC WRITE command sent, no response expected")
        return None
