import socket
import ipaddress

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

def valid_ip_address(addr: str) -> int:
    res: int = socket.AF_INET
    try:
        if type(ipaddress.ip_address(addr)) is ipaddress.IPv6Address:
            res = socket.AF_INET6
    except ValueError:
        pass
    return res

def get_error(err: Exception) -> str:
    return redcat.style.bold(": ".join(str(arg) for arg in err.args))
