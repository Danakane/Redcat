import typing

import redcat.channel
import redcat.listener, redcat.listener.tcplistener

def get_listener(**kwargs: typing.Dict[str, typing.Any]) -> redcat.listener.Listener:
    new_listener = None
    protocol = kwargs["protocol"]
    del kwargs["protocol"]
    if protocol == redcat.channel.ChannelProtocol.TCP:
        # addr: str, port: int, platform_name: str, callback: callable
        new_listener = redcat.listener.tcplistener.TcpListener(**kwargs)
    elif protocol == redcat.channel.ChannelProtocol.SSL:
        # addr: str, port: int, platform_name: str, cert: str, key: str, password: str, ca_cert: str, callback: callable
        new_listener = redcat.listener.ssllistener.SslListener(**kwargs)
    return new_listener
