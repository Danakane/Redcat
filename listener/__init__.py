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

    def start(self) -> None:
        self.__stop_evt.clear()
        self.on_start()
        self.__thread = threading.Thread(target=self.__run)
        self.__thread.start()

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

    def listen_once(self) -> typing.Tuple[channel.Channel, str]:
        chan: channel.Channel = None
        self.on_start()
        try:
            while not chan:
                chan = self.listen()
        except KeyboardInterrupt:
            pass
        self.on_stop()
        return chan, self.__platform_name

