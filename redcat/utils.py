import typing
import socket
import signal
import threading
import os
import sys
import termios
import shutil
import sys

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


class MainThreadInterruptibleSection:
    """ 
    A Helper class to manage the main thread interruption system
    It takes a setter to flag attribute that indicate if the main thread can be interrupted
    and set the flag to True when entering and to False when exiting a with block
    """
    def __init__(self) -> None:
        self.__is_interruptible: bool = False
        self.__original_sigusr1_handler = signal.getsignal(signal.SIGUSR1)

    @property
    def is_interruptible(self) -> bool:
        return self.__is_interruptible

    def interrupter(self, func: typing.Callable) -> typing.Callable:
        def decorator(*args, **kwargs) -> None:
            res = func(*args, **kwargs)
            if self.__is_interruptible:
                os.kill(os.getpid(),signal.SIGUSR1)
                self.__is_interruptible = False
            return res
        return decorator

    def interruptible(self, func: typing.Callable) -> typing.Callable:
        def decorator(*args, **kwargs) -> typing.Any:
            with self:
                return func(*args, **kwargs)
        return decorator

    def __enter__(self):
        signal.signal(signal.SIGUSR1, MainThreadInterruptibleSection.on_signal)
        self.__is_interruptible = True
        return self

    def __exit__(self, type, value, traceback) -> None:
        self.__is_interruptible = False
        signal.signal(signal.SIGUSR1, self.__original_sigusr1_handler)

    def on_signal(signum, frame):
        raise MainThreadInterrupt()


class MainThreadInterrupt(Exception):
    """
    Exception class specifically designed to interrupt the main thread
    """
    def __init__(self) -> None:
        pass


class Singleton(type):
    """
    Singleton metaclass 
    """
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
