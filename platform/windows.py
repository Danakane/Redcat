
import channel
from platform import Platform, WINDOWS


class Windows(Platform):

    def __init__(self, chan: channel.Channel) -> None:
        super().__init__(chan, WINDOWS)

    def interactive(self, value: bool) -> bool:
        return value


