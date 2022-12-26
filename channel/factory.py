import threading

import channel, channel.tcpchannel


def get_channel(addr: str, port: int, mode: int, channel_protocol) -> channel.Channel:
    chan = None
    if channel_protocol == channel.TCP:
        chan = channel.tcpchannel.TcpChannel(addr, port, mode, threading.Event())
    return chan
