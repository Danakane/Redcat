import threading
import typing
import abc
from abc import abstractmethod

import channel

class Listener:

    def __init__(self, platform_name: str, callback: typing.Callable = None) -> None:
        self.__callback: typing.Callable = callback
        self.__platform_name: str = platform_name
        self.__thread: threading.Thread = None
        self.__stop_evt: threading.Event = threading.Event()

    @property
    @abstractmethod
    def endpoint(self) -> str:
        pass

    @abstractmethod
    def listen(self) -> channel.Channel:
        pass

    @abstractmethod
    def on_start(self) -> None:
        pass

    @abstractmethod
    def on_stop(self) -> None:
        pass

    @property
    def platform_name(self) -> str:
        return self.__platform_name

    @property
    def running(self) -> bool:
        return not self.__stop_evt.is_set()

    def start(self) -> typing.Tuple[bool, str]:
        self.__stop_evt.clear()
        res, error = self.on_start()
        if res:
            self.__thread = threading.Thread(target=self.__run)
            self.__thread.start()
        return res, error

    def stop(self) -> None:
        self.__stop_evt.set()
        if self.__thread:
            self.__thread.join()
        self.on_stop()

    def __run(self) -> None:
        while not self.__stop_evt.is_set():
            chan = self.listen()
            if chan and self.__callback:
                self.__callback(self, chan, self.__platform_name)

    def listen_once(self) -> typing.Tuple[bool, str, channel.Channel, str]:
        chan: channel.Channel = None
        res, error = self.on_start()
        while not chan:
            chan = self.listen()
        self.on_stop()
        return res, error, chan, self.__platform_name

