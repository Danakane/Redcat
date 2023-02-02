import threading
import typing
import abc
from abc import abstractmethod

import redcat.channel


class Listener:

    def __init__(self, id: str, platform_name: str, callback: typing.Callable = None, 
            error_callback: typing.Callable = None, logger_callback: typing.Callable = None) -> None:
        self.__id: str = id
        self.__callback: typing.Callable = callback
        self.__error_callback: typing.Callable = error_callback
        self.__logger_callback: typing.Callable = logger_callback
        self.__platform_name: str = platform_name
        self.__thread: threading.Thread = None
        self.__stop_evt: threading.Event = threading.Event()

    @property
    def id(self) -> None:
        return self.__id

    @property
    @abstractmethod
    def endpoint(self) -> str:
        pass

    @property
    @abstractmethod
    def protocol(self) -> typing.Tuple[int, str]:
        pass

    @property
    def platform_name(self) -> str:
        return self.__platform_name

    @property
    def running(self) -> bool:
        return not self.__stop_evt.is_set()

    @abstractmethod
    def listen(self) -> redcat.channel.Channel:
        pass

    @abstractmethod
    def on_start(self) -> None:
        pass

    @abstractmethod
    def on_stop(self) -> None:
        pass

    def on_error(self, error: str) -> None:
        pass

    def build_channel(self, protocol: int, **kwargs) -> redcat.channel.Channel:
        return redcat.channel.factory.get_channel(protocol=protocol, error_callback=self.__error_callback, logger_callback=self.__logger_callback, **kwargs)

    def start(self) -> typing.Tuple[bool, str]:
        self.__stop_evt.clear()
        res, error = self.on_start()
        if res:
            self.__thread = threading.Thread(target=self.__run)
            self.__thread.start()
            self.__logger_callback(f"listener {redcat.style.blue(self.__id)} created and listening on {self.endpoint}")
        else:
            self.__error_callback(self, error)
        return res, error

    def stop(self) -> None:
        self.__stop_evt.set()
        if self.__thread:
            self.__thread.join()
        self.on_stop()

    def error(self, err: str) -> None:
        self.on_error(err)
        if self.__error_callback:
            self.__error_callback(self, err)

    def __run(self) -> None:
        while not self.__stop_evt.is_set():
            chan = self.listen()
            if chan and self.__callback:
                self.__callback(self, chan, self.__platform_name)

    def listen_once(self) -> typing.Tuple[bool, str, redcat.channel.Channel, str]:
        chan: redcat.channel.Channel = None
        res, error = self.on_start()
        if res:
            while not chan:
                chan = self.listen()
        self.on_stop()
        return res, error, chan, self.__platform_name

