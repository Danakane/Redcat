import threading
import typing

import channel, channel.tcpchannel


def get_channel(addr: str, port: int, channel_protocol: int) -> channel.Channel:
    chan = None
    if channel_protocol == channel.TCP:
        chan = channel.tcpchannel.TcpChannel(addr=addr, port=port)
    return chan

def get_channel_from_remote(host: typing.Tuple[typing.Any, ...], remote: typing.Any, channel_protocol: int) -> channel.Channel:
    chan = None
    if channel_protocol == channel.TCP:
        chan = channel.tcpchannel.TcpChannel(host, remote)
    return chan
