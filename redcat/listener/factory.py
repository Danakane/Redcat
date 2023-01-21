import typing

import redcat.channel
import redcat.listener, redcat.listener.tcplistener

def get_listener(addr: str, port: int, platform_name: str, protocol: int = redcat.channel.TCP, callback: typing.Callable = None) -> redcat.listener.Listener:
    new_listener = None
    if protocol == redcat.channel.TCP:
        new_listener = redcat.listener.tcplistener.TcpListener(addr, port, platform_name, callback)
    return new_listener
