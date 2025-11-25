class ST3215Error(Exception):
    pass


class ServoNotRespondingError(ST3215Error):
    pass


class InvalidInstructionError(ST3215Error):
    pass
