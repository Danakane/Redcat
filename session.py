import sys
import threading
import typing

import channel, channel.factory
import platform, platform.factory
import transaction


class Session: 

    def __init__(self, error_callback: typing.Callable, chan: channel.Channel = None, addr: str = None, port: int = None,
                 channel_protocol:int=channel.TCP, platform_name: str=platform.LINUX) -> None:
        self.__error_callback: typing.Callable = error_callback
        self.__chan: channel.Channel = None
        self.__platform: platform.Platform = None
        if chan:
            self.__chan = chan
        else:
            self.__chan: channel.Channel = channel.factory.get_channel(addr, port, channel_protocol)
        if self.__chan:
            self.__chan.error_callback = self.on_error
            self.__platform = platform.factory.get_platform(self.__chan, platform_name)
        self.__interactive: bool = False
        self.__thread_reader: threading.Thread = None
        self.__thread_writer: threading.Thread = None
        self.__stop_evt: threading.Event = threading.Event()
        self.__running: bool = False 

    @property
    def remote(self) -> str:
        return self.__chan.remote

    @property
    def local(self) -> str:
        return self.__chan.local

    @property
    def platform_name(self) -> str:
        return self.__platform.platform_name

    @property
    def platform(self) -> platform.Platform:
        return self.__platform

    @property
    def is_open(self) -> bool:
        return self.__chan.is_open

    @property
    def is_interactive(self) -> bool:
        return self.__interactive

    def on_error(self, sender, error) -> None:
        self.__error_callback(self, error)

    def open(self) -> typing.Tuple[bool, str]:
        return self.__chan.open()

    def close(self) -> None:
        self.__chan.close()
        print(end="") # to avoid bad file descriptor error message
        self.__interactive = self.__platform.interactive(False)
        if self.__thread_reader:
            self.__thread_reader.join()
        if self.__thread_writer:
            self.__thread_writer.join()

    def interactive(self, value: bool) -> bool:
        if (self.__interactive != value) and self.__platform:
            self.__platform.interactive(value)
            self.__interactive = self.__platform.is_interactive
        return self.__interactive

    def start(self) -> None:
        self.__stop_evt.clear()
        self.__thread_reader = threading.Thread(target=self.__run_reader)
        self.__thread_writer = threading.Thread(target=self.__run_writer)
        self.__thread_reader.start()
        self.__thread_writer.start()

    def stop(self) -> None:
        if not self.__stop_evt.is_set():
            self.__stop_evt.set()
        if self.__thread_reader:
            self.__thread_reader.join()
        if self.__thread_writer:
            self.__thread_writer.join()
        self.__running = False

    def send(self, data: bytes) -> typing.Tuple[bool, str]:
        return self.__chan.send(data)

    def wait_open(self, timeout: int=None) -> bool:
        return self.__chan.wait_open(timeout)

    def wait_stop(self, timeout: int=None) -> bool:
        res = self.__stop_evt.wait(timeout)
        if res :
            self.stop()
        return res

    def __run_reader(self)-> None:
        self.__running = True
        while not self.__stop_evt.is_set():
            data = self.__chan.retrieve()
            if data:
                try:
                    print(data.decode("UTF-8"), end="")
                except:
                    try:
                        print(data.decode("latin-1"), end="")
                    except:
                        pass
                data = b""
            sys.stdout.flush()

    def __run_writer(self) -> None:
        self.__running = True
        res = False
        error = ""
        while not self.__stop_evt.is_set():
            byte = sys.stdin.buffer.read(1)
            if (not byte) or (byte == b"\x04"):
                self.__stop_evt.set()
                res = True
            else:
                with self.__chan.transaction_lock:
                    res, error = self.send(byte)
                if not res:
                    self.__stop_evt.set()
        if (not res) and self.__chan.is_open:
            self.__chan.close()

    def download(self, rfile: str) -> typing.Tuple[bool, str, bytes]:
        return self.__platform.download(rfile)

    def upload(self, rfile: str, data: bytes) -> typing.Tuple[bool, str]:
        return self.__platform.upload(rfile, data)

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, type, value, traceback):
        if self.__running:
            self.stop()
        self.close()

