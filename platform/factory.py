import channel
from platform import Platform, LINUX, WINDOWS
from platform.linux import Linux
from platform.windows import Windows


def get_platform(chan: channel.Channel, platform_name: str) -> Platform:
    platform = None
    if platform_name.lower() == LINUX:
        platform = Linux(chan)
    elif platform_name.lower() == WINDOWS:
        platform = Windows(chan)
    return platform

