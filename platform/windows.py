import tty
import termios
import sys

import channel
from platform import Platform, WINDOWS


class Windows(Platform):

    def __init__(self, chan: channel.Channel) -> None:
        super().__init__(chan, WINDOWS)

    def interactive(self, value: bool) -> bool:
        return value

    def whoami(self) -> typing.Tuple[bool, str, str]:
        self.channel.purge()
        res, data = transaction.Transaction(f"whoami".encode(), self.channel, self, True).execute()
        return res, "", data.decode("utf-8").replace("\r", "").replace("\n", "")

