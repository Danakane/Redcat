import base64
import os
import typing

import redcat.utils
import redcat.platform


class Transaction:

    def __init__(self, payload: bytes, pltf: redcat.platform.Platform, handle_echo: bool = False, timeout:int=30) -> None:
        self.__payload: bytes = payload
        self.__platform: redcat.platform.Platform = pltf
        self.__handle_echo: bool = handle_echo
        self.__timeout: int = timeout
        self.__start: bytes = base64.b64encode(os.urandom(8))
        self.__end: bytes = base64.b64encode(os.urandom(8))
        self.__control: bytes = base64.b64encode(os.urandom(8))
        self.__buffer: bytes = self.__platform.build_transaction(self.__payload, self.__start, self.__end, self.__control)

    def execute(self) -> typing.Tuple[bool, bool, bytes]:
        cmd_success = False
        res, data = self.__platform.exec_transaction(self.__buffer, self.__start, self.__end, self.__handle_echo, self.__timeout)
        if res and self.__control in data:
            cmd_success = True
            data = data.replace(self.__control, b"") # remove control code from the returned data
        if self.__platform.platform_name == redcat.platform.WINDOWS:
            # more cleaning for windows with pty...
            # This problem may be caused by how the implant works
            # Need to change the implant and test again
            if self.__platform.has_pty:
                # This fix is just too broken
                # Find a better solution later 
                escape_seq = b"\r\n\x1b[34;197H"
                idx = data.find(escape_seq)
                start_idx = data[:idx].rfind(b"\x07")
                data = data[start_idx:]
                data = redcat.utils.extract_data(data, b"\x07", b"\r\x1b]0;")
                filtered_data = bytearray()
                i = 0
                while i < len(data):
                    if data[i:i+len(escape_seq)] == escape_seq:
                        i += len(escape_seq) + 1
                    else:
                        filtered_data.append(data[i])
                        i += 1
                data = bytes(filtered_data)
        return res, cmd_success, data

