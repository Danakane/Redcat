import threading
import typing

import redcat.channel, redcat.channel.tcpchannel, redcat.channel.sslchannel


def get_channel(protocol: int, **kwargs) -> redcat.channel.Channel:
    chan = None
    if protocol == redcat.channel.ChannelProtocol.TCP:
        # addr: str, port: int
        # OR
        # remote: tuple, sock: socket
        chan = redcat.channel.tcpchannel.TcpChannel(**kwargs)
    elif protocol == redcat.channel.ChannelProtocol.SSL:
        # addr: str, port: int, ca_cert: str, cert: str, key: str, password: str
        # OR
        # remote: tuple, sock: SSLSocket, ssl_context: SSLContext
        chan = redcat.channel.sslchannel.SslChannel(**kwargs)
    return chan
