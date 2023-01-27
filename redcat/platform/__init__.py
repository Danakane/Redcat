import time
import threading
import typing
import abc
from abc import abstractmethod

import redcat.style
import redcat.channel


LINUX="linux"
WINDOWS="windows"


class Platform(abc.ABC):

    def __init__(self, chan: redcat.channel.Channel, platform_name) -> None:
        self.__chan: redcat.channel.Channel = chan
        self.__platform_name: str = platform_name.lower()
        self.__lock: threading.Lock = threading.Lock()

    @property
    def platform_name(self) -> str:
        return self.__platform_name

    @property
    def channel(self) -> redcat.channel.Channel:
        return self.__chan

    @property
    @abstractmethod
    def is_interactive(self) -> bool:
        pass

    @abstractmethod
    def interactive(self, value: bool, session_id: str = None) -> bool:
        pass

    def download(self, rfile: str) -> typing.Tuple[bool, str, bytes]:
        return False, redcat.style.bold(f"not implemented for {self.__platform_name} platform")

    def upload(self, rfile: str, data: bytes) -> typing.Tuple[bool, str]:
        return False, False, redcat.style.bold(f"not implemented for {self.__platform_name} platform")

    def whoami(self) -> typing.Tuple[bool, str, str]:
        return False, Dalse, redcat.style.bold(f"not implemented for {self.__platform_name} platform")

    def hostname(self) -> typing.Tuple[bool, str, str]:
        return False, False, redcat.style.bold(f"not implemented for {self.__platform_name} platform")

    def build_transaction(self, payload: bytes, start: bytes, end: bytes, control: bytes) -> bytes:
        return b"echo %b; %b && echo %b; echo %b\n" % (start, payload, control, end)

    def exec_transaction(self, buffer: bytes, start: bytes, end: bytes, handle_echo: bool, timeout: int) -> typing.Tuple[bool, bytes]:
        res = False
        data = b""
        if self.__chan.is_open:
            res, data = self.__chan.exec_transaction(buffer, start, end, handle_echo, timeout)
        return res, data

    def send_cmd(self, cmd: str, wait_for: int = 0.1) -> typing.Tuple[bool, str]:
        res, error = self.channel.send(f"{cmd}\n".encode())
        time.sleep(wait_for)
        return res, error

    def _with_lock(func: typing.Callable) -> typing.Callable:
        def decorator(self, *args, **kwargs) -> typing.Any:
            res = None
            with self.__lock:
                res = func(self, *args, **kwargs)
            return res
        return decorator