import threading
import typing
import abc
from abc import abstractmethod

class Channel(abc.ABC):

    def __init__(self, stopevent: threading.Event) -> None:
        self.__thread: threading.Thread = None
        self.__open: bool = False
        self.__stopevt: threading.Event = stopevent
        self.__readyevt: threading.Event = threading.Event()

    @property
    def IsOpen(self) -> bool:
        return self.__open
    
    @abstractmethod
    def Send(self, data: bytes) -> None:
        pass

    @abstractmethod
    def Recv(self) -> typing.Tuple[bool, bytes]:
        pass

    @abstractmethod
    def Collect(self, data) -> None:
        pass

    @abstractmethod
    def OnError(self) -> None:
        pass

    @abstractmethod
    def ListenOrConnect(self) -> bool:
        pass

    @abstractmethod
    def OnConnectionEstablished(self) -> None:
        pass

    @abstractmethod
    def OnClose(self) -> None:
        pass

    def Open(self) -> None:
        self.__thread = threading.Thread(target=self.__run)
        self.__thread.start()

    def Close(self) -> None:
        self.__stopevt.set()
        self.OnClose()
        self.__thread.join()
        self.__open = False

    def Error(self) -> None:
        self.__open = False
        self.OnError()

    def WaitOpen(self, timeout=None) -> bool:
        return self.__readyevt.wait(timeout)

    def __run(self) -> None:
        if self.ListenOrConnect():
            self.__open = True
            self.__readyevt.set()
            self.OnConnectionEstablished()
            while not self.__stopevt.is_set():
                error, data = self.Recv()
                if error:
                    self.Error()
                    self.__stopevt.set()
                else:
                    self.Collect(data)
        else:
            self.Error()
            self.__stopevt.set()

    def __enter__(self):
        self.Open()
        return self

    def __exit__(self, type, value, traceback) -> None:
        self.Close()

