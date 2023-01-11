import typing
import tty
import termios
import sys

import channel
import transaction
from platform import Platform, WINDOWS


class Windows(Platform):

    def __init__(self, chan: channel.Channel) -> None:
        super().__init__(chan, WINDOWS)

    def interactive(self, value: bool) -> bool:
        return value

    def build_transaction(self, payload: bytes, start: bytes, end: bytes) -> bytes:
        return b"echo " + start + b" && " + payload + b" && " + b"echo " + end + b"\n"

    def whoami(self) -> typing.Tuple[bool, str, str]:
        self.channel.purge()
        res, data = transaction.Transaction(f"whoami".encode(), self, True).execute()
        return res, "", data.decode("utf-8").replace("\r", "").replace("\n", "").strip()

