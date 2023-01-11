import base64
import os
import typing

import platform

class Transaction:

    def __init__(self, payload: bytes, pltf: platform.Platform, handle_echo: bool = False) -> None:
        self.__payload: bytes = payload
        self.__platform: platform.Platform = pltf
        self.__handle_echo: bool = handle_echo
        self.__start: bytes = base64.b64encode(os.urandom(16))
        self.__end: bytes = base64.b64encode(os.urandom(16))
        self.__buffer: bytes = self.__platform.build_transaction(self.__payload, self.__start, self.__end)

    def execute(self) -> typing.Tuple[bool, bytes]:
        res, data = self.__platform.exec_transaction(self.__buffer, self.__start, self.__end, self.__handle_echo)
        return res, data

