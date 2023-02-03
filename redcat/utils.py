import typing
import socket
import signal

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


class MainThreadInterruptionActivator:
    """ 
    A simple helper class to manage the main thread interruption system
    It takes a setter to flag attribute that indicate if the main thread can be interrupted
    and set the flag to True when entering and to False when exiting a with block
    """
    def __init__(self, switch: typing.Callable) -> None:
        self.__switch: typing.Callable = switch
        self.__original_sigusr1_handler = signal.getsignal(signal.SIGUSR1)

    def __enter__(self):
        signal.signal(signal.SIGUSR1, MainThreadInterruptionActivator.interrupt)
        self.__switch(True)
        return self

    def __exit__(self, type, value, traceback) -> None:
        self.__switch(False)
        signal.signal(signal.SIGUSR1, self.__original_sigusr1_handler)

    def interrupt(signum, frame):
        raise MainThreadInterrupt()


class MainThreadInterrupt(Exception):
    """
    Exception class specifically designed to interrupt the main thread
    """
    def __init__(self) -> None:
        pass


