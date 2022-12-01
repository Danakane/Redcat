import select
import socket
import queue
import select
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
        self.__listenning: bool = False
        self.__error: str = ""
        self.__serversock: socket.socket = None
        self.__sock: socket.socket = None
        self.__dataqueue: typing.Queue = queue.Queue()
        self.__lock = threading.Lock()
 
    def ListenOrConnect(self) -> bool:
        noerror: bool = True
        try:
            if self.__connect:
                self.__sock = socket.socket(self.__protocol, socket.SOCK_STREAM)
                self.__sock.connect(self.__endpoint)
                self.__remote = self.__endpoint
            else:
                self.__listenning = True
                self.__serversock = socket.socket(self.__protocol, socket.SOCK_STREAM)
                self.__serversock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.__serversock.bind(self.__endpoint)
                self.__serversock.listen(1)
                self.__sock, self.__remote = self.__serversock.accept()
        except Exception as err:
            noerror = False
            self.__error = err.args[1]
            pass
        finally:
            self.__listenning = False
        return noerror

    def OnClose(self) -> None:
        if self.__sock:
            try:
                self.__sock.shutdown(socket.SHUT_RDWR)
                self.__sock.close()
                self.__sock = None
            except:
                pass
        if(self.__serversock):
            if self.__listenning:
                try:
                    sock = socket.socket(self.__protocol, socket.SOCK_STREAM)
                    sock.connect(self.__endpoint)
                    sock.shutdown(socket.SHUT_RDWR)
                    sock.close()
                except:
                    pass
            try:
                self.__serversock.shutdown(socket.SHUT_RDWR)
                self.__serversock.close()
                self.__serversock = None
            except:
                pass

    def OnConnectionEstablished(self) -> None:
        if self.IsOpen:
            print(f"Connected to remote {self.__remote[0]}:{self.__remote[1]}")

    def Recv(self) -> typing.Tuple[bool, bytes]:
        error = False
        data = b""
        try:
            readables, _, _= select.select([self.__sock], [], [], 0.2)
            if readables and readables[0] == self.__sock:
                try:
                    data = self.__sock.recv(4096)
                except Exception as err:
                    self.__error = err.args[1]
                    error = True
        except select.error as err:
            error = True
            self.__error = err.args[1]
        return error, data

    def Send(self, data: bytes) -> None:
        self.__sock.send(data)

    def Collect(self, data: bytes) -> None:
        print(data.decode("UTF-8"), end="")
        with self.__lock:
            self.__dataqueue.put(data)

    def OnError(self) -> None:
        if self.__error:
            print(self.__error)

    def Retrieve(self) -> bytes:
        data: bytes = b""
        with self.__lock:
            while not self.__dataqueue.empty():
                data = self.__dataqueue.get()
        return data

