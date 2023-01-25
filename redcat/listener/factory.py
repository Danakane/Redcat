import typing

import redcat.channel
import redcat.listener, redcat.listener.tcplistener, redcat.listener.ssllistener

def get_listener(protocol: int, **kwargs) -> redcat.listener.Listener:
    new_listener = None
    if protocol == redcat.channel.ChannelProtocol.TCP:
        # addr: str, port: int, platform_name: str, callback: callable
        new_listener = redcat.listener.tcplistener.TcpListener(**kwargs)
    elif protocol == redcat.channel.ChannelProtocol.SSL:
        # addr: str, port: int, platform_name: str, cert: str, key: str, password: str, ca_cert: str, callback: callable
        new_listener = redcat.listener.ssllistener.SslListener(**kwargs)
    return new_listener
