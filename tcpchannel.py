import select
import socket
import queue
import threading
import typing

import channel


class TCPChannel(channel.Channel):

    def __init__(self, endpoint: tuple, protocol: int, connect: bool, stopevent: threading.Event) -> None:
        super().__init__(stopevent)
        self.__endpoint: typing.Tuple = endpoint
        self.__remote: typing.Tuple = ()
        self.__connect: bool = connect
        self.__protocol: int = protocol
        self.__serversock: socket.socket = None
        self.__sock: socket.socket = None
        self.__dataqueue: typing.Queue = []
 
    def ListenOrConnect(self) -> None:
        if self.__connect:
            self.__sock = socket.socket(self.__protocol, socket.SOCK_STREAM)
            self.__sock.connect(self.__endpoint)
            self.__remote = self.__endpoint
        else:
            self.__serversock = socket.socket(self.__protocol, socket.SOCK_STREAM)
            self.__serversock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.__serversock.bind(self.__endpoint)
            self.__serversock.listen(1)
            self.__sock, self.__remote = self.__serversock.accept()
        self.__sock.setblocking(False)

    def OnClose(self) -> None:
        self.__sock.shutodown()
        self.__sock.close()
        if(self.__serversock):
            self.__serversock.shutdown()
            self.__serversock.close()

    def Recv(self) -> bytes:
        return self.__sock.recv(4096)

    def Send(self, data: bytes) -> None:
        self.__sock.send(data)

    def Collect(self, data: bytes) -> None:
        print(data.decode("UTF-8"), end="")
        self.__dataqueue.put(data)

    def Retrieve(self) -> bytes:
        data: bytes = b""
        if not self.__dataqueue.empty():
            data = self.__dataqueue.get()
        return data

