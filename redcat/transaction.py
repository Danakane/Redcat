import base64
import os
import typing

import redcat.platform

class Transaction:

    def __init__(self, payload: bytes, pltf: redcat.platform.Platform, handle_echo: bool = False) -> None:
        self.__payload: bytes = payload
        self.__platform: redcat.platform.Platform = pltf
        self.__handle_echo: bool = handle_echo
        self.__start: bytes = base64.b64encode(os.urandom(16))
        self.__end: bytes = base64.b64encode(os.urandom(16))
        self.__control: bytes = base64.b64encode(os.urandom(16))
        self.__buffer: bytes = self.__platform.build_transaction(self.__payload, self.__start, self.__end, self.__control)

    def execute(self) -> typing.Tuple[bool, bool, bytes]:
        cmd_success = False
        res, data = self.__platform.exec_transaction(self.__buffer, self.__start, self.__end, self.__handle_echo)
        if res and self.__control in data:
            cmd_success = True
            data = data.replace(self.__control, b"") # remove control code from the returned data
        return res, cmd_success, data

