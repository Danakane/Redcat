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

def get_remote_and_family_from_addr(addr: str, port: int, socktype: int = 0) -> typing.Tuple[int, typing.Tuple]:
    if not addr:
        addr = "0.0.0.0" # "" -> "0.0.0.0" we default to IPv4
    addrinfo = socket.getaddrinfo(addr, port, 0, socktype)
    family = addrinfo[0][0]
    remote = addrinfo[0][4]
    return family, remote

def get_error(err: Exception) -> str:
    return redcat.style.bold(": ".join(str(arg) for arg in err.args))
