import typing

import channel
import listener, listener.tcplistener

def get_listener(addr: str, port: int, platform_name: str, protocol: int = channel.TCP, callback: typing.Callable = None) -> listener.Listener:
    new_listener = None
    if protocol == channel.TCP:
        new_listener = listener.tcplistener.TcpListener(addr, port, platform_name, callback)
    return new_listener
