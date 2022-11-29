import threading
import typing
import abc
from abc import abstractmethod

class Channel(abc.ABC):

    def __init__(self, stopevent: threading.Event) -> None:
        self.__thread: threading.Thread = None
        self.__open: bool = False
        self.__stopevt: threading.Thread = stopevent

    @abstractmethod
    def Send(self, data: bytes) -> None:
        pass

    @abstractmethod
    def Recv(self) -> bytes:
        pass

    @abstractmethod
    def Collect(self, data) -> None:
        pass

    @abstractmethod
    def ListenOrConnect(self) -> None:
        pass

    @abstractmethod
    def OnClose(self) -> None:
        pass

    def Open(self) -> None:
        self.__thread = threading.Thread(target=self.__run)
        self.__thread.start()

    def Close(self) -> None:
        self.__stopevt.set()
        self.__thread.join()
        self.__open = False

    def __run(self) -> None:
        self.__open = True
        self.ListenOrConnect()
        while not self.__stopevt.is_set():
            try:
                self.Collect(self.Recv())
            except Exception as e:
                pass

