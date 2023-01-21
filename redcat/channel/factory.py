import threading
import typing

import redcat.channel, redcat.channel.tcpchannel


def get_channel(addr: str, port: int, channel_protocol: int) -> redcat.channel.Channel:
    chan = None
    if channel_protocol == redcat.channel.TCP:
        chan = redcat.channel.tcpchannel.TcpChannel(addr=addr, port=port)
    return chan

def get_channel_from_remote(host: typing.Tuple[typing.Any, ...], remote: typing.Any, channel_protocol: int) -> redcat.channel.Channel:
    chan = None
    if channel_protocol == redcat.channel.TCP:
        chan = redcat.channel.tcpchannel.TcpChannel(host, remote)
    return chan
