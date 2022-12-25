import enum
import queue
import sys
import threading
import typing
import abc
from abc import abstractmethod

class ChannelState(enum.Enum):
    ERROR = -1
    CLOSED = 0
    OPEN = 1
    OPENNING = 2
    CLOSING = 3



class Channel(abc.ABC):

    TCP: int = 0

    BIND: int = 0
    CONNECT: int = 1
    def __init__(self, stop_evt: threading.Event) -> None:
        self.__thread: threading.Thread = None
        self.__state: int = ChannelState.CLOSED
        self.__stop_evt: threading.Event = stop_evt
        self.__ready_evt: threading.Event = threading.Event()
        self.__has_data_evt: threading.Event() = threading.Event()
        self.__dataqueue: typing.Queue = queue.Queue()
        self.__queue_lock: threading.Lock = threading.Lock()


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
    @abstractmethod
    def remote(self) -> str:
        pass

    @property
    @abstractmethod
    def local(self) -> str:
        pass
    
    @abstractmethod
    def send(self, data: bytes) -> None:
        pass

    @abstractmethod
    def recv(self) -> typing.Tuple[bool, bytes]:
        pass

    @abstractmethod
    def on_error(self) -> None:
        pass

    @abstractmethod
    def listen_or_connect(self) -> bool:
        pass

    @abstractmethod
    def on_connection_established(self) -> None:
        pass

    @abstractmethod
    def on_close(self) -> None:
        pass

    def open(self) -> None:
        self.__state = ChannelState.OPENNING
        self.__thread = threading.Thread(target=self.__run)
        self.__thread.start()

    def close(self) -> None:
        self.__state = ChannelState.CLOSING
        self.__stop_evt.set()
        self.on_close()
        self.__thread.join()
        self.__state = ChannelState.CLOSED

    def error(self) -> None:
        self.__state = ChannelState.ERROR
        self.on_error()

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

    def wait_open(self, timeout=None) -> bool:
        return self.__ready_evt.wait(timeout)

    def wait_data(self, timeout=None) -> None:
       return self.__has_data_evt.wait(timeout)

    def __run(self) -> None:
        if self.listen_or_connect():
            if self.__state == ChannelState.OPENNING:
                self.__state = ChannelState.OPEN
                self.__ready_evt.set()
                self.on_connection_established()
                while not self.__stop_evt.is_set():
                    error, data = self.recv()
                    if error:
                        self.error()
                        self.__stop_evt.set()
                    else:
                        if data:
                            self.collect(data)
            else:
                self.__stop_evt.set()
        else:
            self.error()
            self.__stop_evt.set()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, type, value, traceback) -> None:
        self.close()

