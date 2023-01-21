import redcat.channel
import redcat.platform, redcat.platform.linux, redcat.platform.windows


def get_platform(chan: redcat.channel.Channel, platform_name: str) -> redcat.platform.Platform:
    platform = None
    if platform_name.lower() == redcat.platform.LINUX:
        platform = redcat.platform.linux.Linux(chan)
    elif platform_name.lower() == redcat.platform.WINDOWS:
        platform = redcat.platform.windows.Windows(chan)
    return platform

