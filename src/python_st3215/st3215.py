import logging
import serial

from .servo import Servo
from .instructions import Instruction
from .errors import ST3215Error, ServoNotRespondingError, InvalidInstructionError

from typing import Optional, Sequence


class ST3215:
    logger = logging.getLogger("ST3215")
    logger.setLevel(logging.WARN)
    _console_handler = logging.StreamHandler()
    _console_handler.setFormatter(
        logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
    )
    logger.addHandler(_console_handler)

    @classmethod
    def set_log_level(cls, level: int):
        cls.logger.setLevel(level)

    @classmethod
    def disable_logging(cls):
        cls.logger.disabled = True

    @classmethod
    def enable_logging(cls):
        cls.logger.disabled = False

    def __init__(
        self,
        port: str,
        baudrate: int = 1000000,
        timeout: float = 0.002,
    ):
        self.logger.debug(
            f"Initializing ST3215 on port {port} with baudrate {baudrate}"
        )
        self.ser = serial.Serial(port, baudrate=baudrate, timeout=timeout)
        self.logger.debug(f"Serial port opened at {baudrate} baud.")

    def close(self):
        if self.ser.is_open:
            self.ser.close()
            self.logger.info("Serial port closed.")

    def build_packet(
        self, servo_id: int, instruction: int, parameters: Sequence[int] | None = None
    ) -> bytes:
        if not Instruction.has_value(instruction):
            raise InvalidInstructionError(f"Invalid instruction: {instruction:#04x}")
        params = tuple(parameters) if parameters else ()
        length = len(params) + 2
        checksum_base = servo_id + length + instruction + sum(params)
        checksum = (~checksum_base) & 0xFF
        packet = bytearray(
            [0xFF, 0xFF, servo_id & 0xFF, length & 0xFF, instruction & 0xFF]
        )
        packet.extend(p & 0xFF for p in params)
        packet.append(checksum)
        self.logger.debug(
            f"Built packet for servo {servo_id:#02x}: instruction={instruction:#02x}, params={params}, checksum={checksum:#02x}, bytes={list(packet)}"
        )
        return bytes(packet)

    def send_instruction(
        self,
        servo_id: int,
        instruction: int | Instruction,
        parameters: Sequence[int] | None = None,
    ) -> bytes:
        instruction_value = (
            instruction.value if isinstance(instruction, Instruction) else instruction
        )
        packet = self.build_packet(servo_id, instruction_value, parameters)
        self.logger.debug(f"Sending packet: {list(packet)}")
        self.ser.write(packet)
        self.ser.flush()
        return packet

    def read_response(self, sent_packet: bytes) -> Optional[bytes]:
        raw_data = self.ser.read(1024)
        self.logger.debug(f"Raw data read: {list(raw_data)}")
        if not raw_data:
            self.logger.warning("No response received.")
            return None
        if raw_data.startswith(sent_packet):
            self.logger.debug(
                "Response includes sent packet header, stripping sent packet."
            )
            return raw_data[len(sent_packet) :]
        return raw_data

    def parse_response(self, data: bytes):
        self.logger.debug(f"Parsing response data: {list(data)}")
        if len(data) < 6:
            self.logger.warning("Response too short to parse.")
            return None
        header = data[0:2]
        servo_id = data[2]
        length = data[3]
        error = data[4]
        parameters = data[5:-1] if length > 2 else b""
        received_checksum = data[-1]
        checksum_base = servo_id + length + error + sum(parameters)
        calculated_checksum = (~checksum_base) & 0xFF
        valid_checksum = calculated_checksum == received_checksum
        parsed = {
            "header": header,
            "id": servo_id,
            "length": length,
            "error": error,
            "parameters": parameters,
            "received_checksum": received_checksum,
            "calculated_checksum": calculated_checksum,
            "checksum_valid": valid_checksum,
        }
        self.logger.debug(f"Parsed response: {parsed}")
        return parsed

    def ping(self, servo_id: int):
        if servo_id == 254:
            raise ST3215Error("Cannot ping broadcast servo ID 254.")
        self.logger.debug(f"Pinging servo {servo_id}")
        packet = self.send_instruction(servo_id, Instruction.PING)
        response = self.read_response(packet)
        if response:
            parsed = self.parse_response(response)
            return parsed
        return None

    def wrap_servo(self, servo_id: int):
        if servo_id == 254:
            raise ST3215Error("Cannot wrap broadcast servo ID 254.")
        parsed = self.ping(servo_id)
        if not parsed or parsed.get("error") != 0:
            raise ServoNotRespondingError(
                f"Servo ID {servo_id} did not respond to ping."
            )
        return Servo(self, servo_id)

    def list_servos(self):
        found = []
        for servo_id in range(0, 254):
            try:
                self.wrap_servo(servo_id)
                found.append(servo_id)
            except ServoNotRespondingError:
                continue
        return found

    def broadcast_action(self):
        self.logger.debug(f"Broadcasting ACTION instruction to all servos")
        return self.send_instruction(254, Instruction.ACTION)
