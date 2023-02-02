import typing
import socket

import redcat.style


def extract_data(raw: bytes, start: bytes, end: bytes=b"", reverse: bool=False) -> None:
    start_index = 0
    if reverse:
        start_index = raw.rfind(start)
    else:
        start_index = raw.find(start)
    extracted = b""
    if start_index != -1:
        if end:
            end_index = start_index + raw[start_index:].find(end)
            extracted = raw[start_index+len(start):end_index]
        else:
            extracted = raw[start_index+len(start):]
    return extracted

def get_remotes_and_families_from_hostname(hostname: str, port: int, socktype: int = 0) -> typing.Tuple[typing.Tuple[int], typing.Tuple[typing.Any, ...]]:
    addrinfo = None
    if not hostname:
        hostname = "::" # Use :: as default address. if /proc/sys/net/ipv6/bindv6only is set to 0 sockets will accept both IPv4 and IPv6 connections
    addrinfo = socket.getaddrinfo(hostname, port, 0, socktype)
    families = tuple([addrinfo[i][0] for i in range(len(addrinfo))])
    remotes = tuple([addrinfo[i][4] for i in range(len(addrinfo))])
    return families, remotes

def get_error(err: Exception) -> str:
    return redcat.style.bold(": ".join(str(arg) for arg in err.args))

 