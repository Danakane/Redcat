import enum
import queue
import select
import sys
import threading
import time
import typing
import abc
from abc import abstractmethod

import redcat.utils


class ChannelProtocol(enum.Enum):
    TCP: int = 0
    SSL: int = 1


class ChannelState(enum.Enum):
    ERROR: int = -1
    CLOSED: int = 0
    OPEN: int = 1
    OPENNING: int = 2
    CLOSING: int = 3


class Channel(abc.ABC):

    def __init__(self, error_callback: typing.Callable = None, logger_callback: typing.Callable = None) -> None:
        self.__state: int = ChannelState.CLOSED
        self.__ready_evt: threading.Event = threading.Event()
        self.__has_data_evt: threading.Event() = threading.Event()
        self.__dataqueue: typing.Queue = queue.Queue()
        self.__queue_lock: threading.Lock = threading.Lock()
        self.__transaction_lock: threading.RLock = threading.RLock()
        self.__error_callback: typing.Callable = error_callback
        self.__logger_callback: typing.Callable = logger_callback
        self.__register: GlobalChannelRegister = GlobalChannelRegister()

    @property
    def is_open(self) -> bool:
        return self.__state == ChannelState.OPEN

    @property
    def is_openning(self) -> bool:
        return self.__state == ChannelState.OPENNING

    @property
    def is_closed(self) -> bool:
        return self.__state == ChannelState.CLOSED

    @property
    def is_closing(self) -> bool:
        return self.__state == ChannelState.CLOSING

    @property
    def state(self) -> int:
        return self.__state

    @property
    def transaction_lock(self) -> threading.RLock:
        return self.__transaction_lock

    @property
    def error_callback(self) -> typing.Callable:
        return self.__error_callback

    @error_callback.setter
    def error_callback(self, callback: typing.Callable) -> None:
        self.__error_callback = callback

    @property
    def is_ready(self) -> bool:
        return self.__ready_evt.is_set()

    @is_ready.setter
    def is_ready(self, value: bool) -> None:
        self.__ready_evt.set() if value else self.__ready_evt.clear()

    @property
    def logger_callback(self) -> typing.Callable:
        return self.__logger_callback

    @property
    @abstractmethod
    def remote(self) -> str:
        pass

    @property
    @abstractmethod
    def protocol(self) -> typing.Tuple[int, str]:
        pass

    @abstractmethod
    def fileno(self) -> int:
        pass

    @abstractmethod
    def send(self, data: bytes) -> typing.Tuple[bool, str]:
        pass

    @abstractmethod
    def recv(self) -> typing.Tuple[bool, str, bytes]:
        pass

    def on_error(self, error: str) -> None:
        pass

    @abstractmethod
    def on_open(self) -> typing.Tuple[bool, str]:
        pass

    def on_connection_established(self) -> None:
        if self.__logger_callback:
            self.__logger_callback("Connection established")

    @abstractmethod
    def on_close(self) -> None:
        pass

    def open(self) -> typing.Tuple[bool, str]:
        self.__state = ChannelState.OPENNING
        res, error = self.on_open()
        if res:
            self.__register.register(self) # must be called after on_open
            self.__state = ChannelState.OPEN
            self.on_connection_established()
            self.is_ready = True
        return res, error

    def close(self) -> None:
        self.__state = ChannelState.CLOSING
        self.is_ready = False
        self.__register.remove(self) # must be called before on_close
        self.on_close()
        self.__state = ChannelState.CLOSED

    def error(self, err: str) -> None:
        if self.__state != ChannelState.ERROR:
            self.__state = ChannelState.ERROR
            self.on_error(err)
            self.__error_callback(self, err)

    def collect(self) -> None:
        with self.__transaction_lock: 
            res, error, data = self.recv()
            if not res:
                self.error(error)
                self.__register.remove(self)
            else:
                with self.__queue_lock:
                    self.__dataqueue.put(data)
                    self.__has_data_evt.set()

    def retrieve(self, n: int=0) -> bytes:
        data: typing.List[bytes] = []
        with self.__queue_lock:
            if n == 0:
                while not self.__dataqueue.empty():
                    data.append(self.__dataqueue.get())
            else:
                for i in range(n):
                    if self.__dataqueue.empty():
                        break
                    data.append(self.__dataqueue.get())
            if self.__dataqueue.empty():
                self.__has_data_evt.clear()
        return b"".join(data)

    def purge(self) -> None:
        with self.__queue_lock:
            while not self.__dataqueue.empty():
                self.__dataqueue.queue.clear()

    def exec_transaction(self, data: bytes, start: bytes, end: bytes, handle_echo: bool, timeout: int) -> typing.Tuple[bool, bytes]:
        res = False
        rdata = b""
        start_time = 0
        end_time = 0
        timed_out = False
        if self.is_open:
            with self.__transaction_lock:
                res, error = self.send(data)
                rdata = b""
                resp = b""
                start_received = False
                end_received = False
                if handle_echo:
                    # purge the command echo
                    start_time = time.time()
                    while res and (end not in rdata) and (not timed_out):
                        res, error, resp = self.recv()
                        rdata += resp
                        end_time = time.time()
                        if end_time - start_time > timeout:
                            timed_out = True
                    resp = b""
                    rdata = redcat.utils.extract_data(rdata, end)
                start_time = time.time()
                while res and (not start_received) and (not timed_out):
                    res, error, resp = self.recv()
                    rdata += resp
                    end_time = time.time()
                    if start in rdata:
                        start_received = True
                    elif end_time - start_time > timeout:
                        timed_out = True
                if end in rdata:
                    end_received = True
                while res and (not end_received) and (not timed_out):
                    res, error, resp = self.recv()
                    rdata += resp
                    end_time = time.time()
                    if end in rdata:
                        end_received = True
                    elif end_time - start_time > timeout:
                        timed_out = True
                if not timed_out:
                    resp = b"placeholder"
                    while res and (len(resp) > 0): # clear remaining data in the channel
                        res, error, resp = self.recv()
        if not res:
            rdata = b""
        elif timed_out:
            self.error(redcat.style.bold("channel's transaction timeout"))
        else:
            rdata = redcat.utils.extract_data(rdata, start, end)
        return (res and not timed_out), rdata

    def wait_open(self, timeout=None) -> bool:
        return self.__ready_evt.wait(timeout)

    def wait_data(self, timeout=None) -> None:
       return self.__has_data_evt.wait(timeout)

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, type, value, traceback) -> None:
        self.close()


class GlobalChannelRegister(metaclass=redcat.utils.Singleton):

    def __init__(self) -> None:
        self.__channels: typing.List[Channel] = []
        self.__lock: threading.RLock = threading.RLock()
        self.__thread: threading.Thread = None

    def register(self, channel: Channel) -> None:
        with self.__lock:
            self.__channels.append(channel)
            if not self.__thread:
                self.__thread: threading.Thread = threading.Thread(target=self.__run)
                self.__thread.start()
    
    def remove(self, channel: Channel) -> None:
        with self.__lock:
            if channel in self.__channels:
                self.__channels.remove(channel)

    def __run(self) -> None:
        while self.__channels:
            with self.__lock:
                readables, _, _ = select.select(self.__channels, [], [], 0.01)
            if readables:
                for channel in readables:
                    channel.collect()
            time.sleep(0.01)
        with self.__lock:
            self.__thread = None
                    
        