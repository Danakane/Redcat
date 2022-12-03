import os
import sys
import socket
import termios
import threading
import time
import tty

import channel
import tcpchannel
import platform


class Session: 

    def __init__(self, addr: str, port: int, channel_protocol:int=channel.Channel.TCP,
                 mode:int=channel.Channel.BIND, platform_name: str=platform.Platform.LINUX) -> None:
        self.__chan: channel.Channel = None
        self.__platform: platform.Platform = None
        if channel_protocol == channel.Channel.TCP:
            self.__chan = tcpchannel.TcpChannel(addr, port, mode, threading.Event())
        if self.__chan:
            self.__platform = platform.Platform(self.__chan, platform_name)
        self.__interactive: bool = False
        self.__thread: threading.Thread = None
        self.__stop_evt: threading.Event = threading.Event()
        self.__running: bool = False

    @property
    def is_open(self) -> bool:
        return self.__chan.is_open

    def open(self) -> None:
        self.__chan.open()

    def close(self) -> None:
        self.__chan.close()
        self.__interactive = self.__platform.interactive(False)

    def interactive(self, value: bool) -> bool:
        if (not self.__interactive) and self.__platform:
            self.__interactive = self.__platform.interactive(value)
        return self.__interactive

    def start(self) -> None:
        self.__stop_evt.clear()
        self.__thread = threading.Thread(target=self.__run)
        self.__thread.start()

    def stop(self) -> None:
        self.__stop_evt.set()
        self.__thread.join()
        self.__running = False

    def send(self, data: bytes) -> None:
        self.__chan.send(data)

    def wait_open(self) -> bool:
        return self.__chan.wait_open()

    def __run(self):
        self.__running = True
        self.__chan.wait_data()
        time.sleep(0.1)
        self.__chan.purge()
        self.__chan.send(b"\n")
        while not self.__stop_evt.is_set():
            data = self.__chan.retrieve()
            if data:
                print(data.decode("UTF-8"), end="")
                data = b""
            sys.stdout.flush()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, type, value, traceback):
        if self.__running:
            self.stop()
        self.close()
                


