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
    def __init__(self, sigwinch_handler: typing.Callable) -> None:
        self.__is_interruptible: bool = False
        self.__sigwinch_handler: typing.Callable = sigwinch_handler
        self.__original_sigusr1_handler = signal.getsignal(signal.SIGUSR1)
        self.__original_sigwinch_handle = signal.getsignal(signal.SIGWINCH)

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
        signal.signal(signal.SIGWINCH, self.__sigwinch_handler)
        signal.signal(signal.SIGUSR1, MainThreadInterruptibleSection.on_signal)
        self.__is_interruptible = True
        return self

    def __exit__(self, type, value, traceback) -> None:
        self.__is_interruptible = False
        signal.signal(signal.SIGUSR1, self.__original_sigusr1_handler)
        signal.signal(signal.SIGWINCH, self.__original_sigwinch_handle)

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


"""
# cursor navigation functions
"""

def get_cursor_current_position() -> tuple[int, int]:
    # Send the ANSI escape sequence to get the cursor position
    row = 0
    col = 0
    old = termios.tcgetattr(sys.stdin)
    _ = termios.tcgetattr(sys.stdin)
    _[3] = _[3] & ~(termios.ECHO | termios.ICANON)
    termios.tcsetattr(sys.stdin, termios.TCSAFLUSH, _)
    try:
        sys.stdout.write('\033[6n')
        sys.stdout.flush()
        # Read the response from the console
        response = ''
        while True:
            char = sys.stdin.read(1)
            if char == 'R':
                break
            response += char
        # Parse the response to get the cursor position
        parts = response.split(';')
        row = int(parts[0][2:]) - 1
        col = int(parts[1]) - 1
    except:
        pass
    termios.tcsetattr(sys.stdin, termios.TCSAFLUSH, old)
    return row, col

def get_console_bottom_row():
    _, rows = shutil.get_terminal_size()
    return rows - 1

def cursor_save_position():
    print("\001\u001B[s\002", end="", flush=True)     # Save current cursor position

def cursor_back_save_point():
    print("\u001B[u", end="", flush=True)     # Jump back to saved cursor position

def cursor_move_up(times: int = 1):
    for i in range(times):
        print("\001\u001B[A\002", end="", flush=True)     # Move cursor up one line

def cursor_move_down(times: int = 1):
    for i in range(times):
        print("\001\u001B[B\002", end="", flush=True)     # Move cursor down one line

def cursor_move_right(times: int = 1):
    for i in range(times):
        print("\001\u001B[C\002", end="", flush=True)     # Move cursor down one line

def cursor_move_to_bottom():
    _, rows = shutil.get_terminal_size()
    print(f"\001\033[{rows};0H\002", end="", flush=True)
    reset_line()

def cursor_move_to_top():
    rows, _ = shutil.get_terminal_size()
    print("\001\033[0;0H\002", end="", flush=True)

def cursor_move_to_line_start():
    print("\001\u001B[999D\001", end="", flush=True)  # Move cursor to beginning of line

def scroll_down():
    print("\001\u001B[S\002", end="", flush=True)     # Scroll up/pan window down 1 line

def insert_line():
    print("\001\u001B[L\002", end="", flush=True)     # Insert new line

def reset_line():
    print("\r\033[K", end="", flush=True)
