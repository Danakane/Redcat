import enum
import queue
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

    def __init__(self, error_callback: typing.Callable = None) -> None:
        self.__thread: threading.Thread = None
        self.__state: int = ChannelState.CLOSED
        self.__stop_evt: threading.Event = threading.Event()
        self.__ready_evt: threading.Event = threading.Event()
        self.__has_data_evt: threading.Event() = threading.Event()
        self.__dataqueue: typing.Queue = queue.Queue()
        self.__queue_lock: threading.Lock = threading.Lock()
        self.__transaction_lock: threading.RLock = threading.RLock()
        self.__error_callback: typing.Callable = error_callback

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
    @abstractmethod
    def remote(self) -> str:
        pass

    @property
    @abstractmethod
    def protocol(self) -> typing.Tuple[int, str]:
        pass

    @abstractmethod
    def send(self, data: bytes) -> typing.Tuple[bool, str]:
        pass

    @abstractmethod
    def recv(self) -> typing.Tuple[bool, str, bytes]:
        pass

    def on_error(self) -> None:
        pass

    @abstractmethod
    def on_open(self) -> typing.Tuple[bool, str]:
        pass

    @abstractmethod
    def on_connection_established(self) -> None:
        pass

    @abstractmethod
    def on_close(self) -> None:
        pass

    def open(self) -> typing.Tuple[bool, str]:
        self.__state = ChannelState.OPENNING
        res, error = self.on_open()
        if res:
            self.__thread = threading.Thread(target=self.__run)
            self.__thread.start()
        return res, error

    def close(self) -> None:
        self.__state = ChannelState.CLOSING
        self.__stop_evt.set()
        self.on_close()
        self.__thread.join()
        self.__state = ChannelState.CLOSED

    def error(self, err: str) -> None:
        self.__state = ChannelState.ERROR
        self.on_error(err)
        self.__error_callback(self, err)

    def collect(self, data: bytes) -> None:
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

    def exec_transaction(self, data: bytes, start: bytes, end: bytes, handle_echo: bool) -> typing.Tuple[bool, bytes]:
        res = True
        rdata = b""
        with self.__transaction_lock:
            res, error = self.send(data)
            rdata = b""
            resp = b""
            start_received = False
            end_received = False
            if handle_echo:
                # purge the command echo
                while res and (end not in rdata):
                    res, error, resp = self.recv()
                    rdata += resp
                resp = b""
                rdata = redcat.utils.extract_data(rdata, end)
            while res and (not start_received):
                res, error, resp = self.recv()
                rdata += resp
                if start in rdata:
                    start_received = True
            if end in rdata:
                end_received = True
            while res and (not end_received):
                res, error, resp = self.recv()
                rdata += resp
                if end in rdata:
                    end_received = True
            resp = b"placeholder"
            while res and (len(resp) > 0): # clear remaining data in the channel
                res, error, resp = self.recv()
        if not res:
            rdata = b""
        else:
            rdata = redcat.utils.extract_data(rdata, start, end)
        return res, rdata

    def wait_open(self, timeout=None) -> bool:
        return self.__ready_evt.wait(timeout)

    def wait_data(self, timeout=None) -> None:
       return self.__has_data_evt.wait(timeout)

    def __run(self) -> None:
        self.__state = ChannelState.OPEN
        self.__ready_evt.set()
        self.on_connection_established()
        while not self.__stop_evt.is_set():
            with self.__transaction_lock:
                res, error, data = self.recv()
                if not res:
                    self.error(error)
                    self.__stop_evt.set()
                else:
                    if data:
                        self.collect(data)
            time.sleep(0.05) # small delay to prevent transaction starvation

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, type, value, traceback) -> None:
        self.close()

