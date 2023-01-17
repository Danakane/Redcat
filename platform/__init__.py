import typing
import abc
from abc import abstractmethod

import style
import channel


LINUX="linux"
WINDOWS="windows"


class Platform(abc.ABC):

    def __init__(self, chan: channel.Channel, platform_name) -> None:
        self.__chan: channel.Channel = chan
        self.__platform_name: str = platform_name.lower()

    @property
    def platform_name(self) -> str:
        return self.__platform_name

    @property
    def channel(self) -> channel.Channel:
        return self.__chan

    @property
    @abstractmethod
    def is_interactive(self) -> bool:
        pass

    @abstractmethod
    def interactive(self, value: bool) -> bool:
        pass

    def download(self, rfile: str) -> typing.Tuple[bool, str, bytes]:
        return False, style.bold(f"not implemented for {self.__platform_name} platform"), b""

    def upload(self, rfile: str, data: bytes) -> typing.Tuple[bool, str]:
        return False, style.bold(f"not implemented for {self.__platform_name} platform")

    def whoami(self) -> typing.Tuple[bool, str, str]:
        return False, style.bold(f"not implemented for {self.__platform_name} platform"), ""

    def build_transaction(self, payload: bytes, start: bytes, end: bytes) -> bytes:
        return b"echo " + start + b";" + payload + b";" + b"echo " + end + b"\n"

    def exec_transaction(self, buffer: bytes, start: bytes, end: bytes, handle_echo: bool) -> typing.Tuple[bool, bytes]:
        return self.__chan.exec_transaction(buffer, start, end, handle_echo)
   

