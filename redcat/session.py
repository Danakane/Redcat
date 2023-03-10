import sys
import threading
import time
import typing

import redcat.channel, redcat.channel.factory
import redcat.platform, redcat.platform.factory
import redcat.transaction


class Session: 

    def __init__(self, id: str, error_callback: typing.Callable, logger_callback: typing.Callable, 
                    platform_name: str, chan: redcat.channel.Channel=None, **kwargs) -> None:
        self.__id: str = id
        self.__error_callback: typing.Callable = error_callback
        self.__logger_callback: typing.Callable = logger_callback
        self.__chan: redcat.channel.Channel = None
        self.__platform: redcat.platform.Platform = None
        if chan:
            self.__chan = chan
        else:
            self.__chan = redcat.channel.factory.get_channel(logger_callback=self.__logger_callback, **kwargs)
        if self.__chan:
            self.__chan.error_callback = self.on_error
            self.__platform = redcat.platform.factory.get_platform(self.__chan, platform_name)
        self.__hostname: str = ""
        self.__user: str = ""
        self.__interactive: bool = False
        self.__thread_reader: threading.Thread = None
        self.__thread_writer: threading.Thread = None
        self.__stop_evt: threading.Event = threading.Event()
        self.__running: bool = False

    @property
    def id(self) -> str:
        return self.__id 

    @property
    def hostname(self) -> str:
        if self.__chan.is_open:
            if not self.__hostname:
                self.__hostname = self.platform.hostname()[2]
        return self.__hostname

    @property
    def user(self) -> str:
        if self.__chan.is_open:
            if not self.__user:
                self.__user = self.platform.whoami()[2]
        return self.__user            

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
    def platform(self) -> redcat.platform.Platform:
        return self.__platform

    @property
    def protocol(self) -> typing.Tuple[int, str]:
        return self.__chan.protocol

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
        self.__interactive = self.__platform.interactive(False)
        self.stop()
        self.__chan.close()
        print(end="") # to avoid bad file descriptor error message

    def interactive(self, value: bool, raw: bool=True) -> bool:
        res = False
        if (self.__interactive != value) and self.__platform and self.is_open:
            if not value:
                self.__user = ""
            res = self.__platform.interactive(value, self.__id, raw)
            self.__interactive = self.__platform.is_interactive
        return res

    def start(self) -> None:
        if self.__chan.is_open:
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
            self.__thread_reader = None
        if self.__thread_writer:
            self.__thread_writer.join()
            self.__thread_writer = None
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
            time.sleep(0.001)

    def __run_writer(self) -> None:
        self.__running = True
        res = False
        error = ""
        data = b""
        while not self.__stop_evt.is_set():
            res = False
            byte = sys.stdin.buffer.read(1)
            if (not byte) or (byte == b"\x04"):
                self.__stop_evt.set()
                res = True
            else:
                data += byte
                if data == b"\x1b" or data == b"\x1b[": # 0x1b is the escape sequence we hold it for the next character
                    res = True
                else:
                    res, error = self.send(data)
                    data = b""
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

