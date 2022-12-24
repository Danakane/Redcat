import sys
import select
import socket
import select
import threading
import typing
import ipaddress

import channel


class TcpChannel(channel.Channel):

    def __init__(self, addr: str, port: int, mode: int, stopevent: threading.Event) -> None:
        super().__init__(stopevent)
        self.__endpoint: typing.Tuple[typing.Any] = None
        self.__protocol: int = socket.AF_INET
        if self.__valid_ip_address(addr) == socket.AF_INET:
            self.__endpoint = (addr, port)
            self.__protocol = socket.AF_INET
        else:
            self.__endpoint = (addr, port, 0, 0)
            self.__protocol = socket.AF_INET6
        self.__remote: typing.Tuple = ()
        self.__mode: int = mode
        self.__listenning: bool = False
        self.__error: str = ""
        self.__serversock: socket.socket = None
        self.__sock: socket.socket = None
         
    def listen_or_connect(self) -> bool:
        res: bool = True
        try:
            if self.__mode == channel.Channel.CONNECT:
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
        except OSError:
            res = False
        except Exception as err:
            res = False
            self.__error = err.args[1]
        finally:
            self.__listenning = False
        return res

    def on_close(self) -> None:
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

    def on_connection_established(self) -> None:
        if self.is_open:
            print(f"Connected to remote {self.__remote[0]}:{self.__remote[1]}") 

    def recv(self) -> typing.Tuple[bool, bytes]:
        error = False
        data = b""
        try:
            readables, _, _= select.select([self.__sock], [], [], 0.05)
            if readables and readables[0] == self.__sock:
                try:
                    data = self.__sock.recv(4096)
                except IOError:
                    pass # to avoid bad descriptor error
                except Exception as err:
                    self.__error = err.args[1]
                    error = True
        except select.error as err:
            error = True
            self.__error = err.args[1]
        return error, data

    def send(self, data: bytes) -> None:
        self.__sock.send(data)

    def on_error(self) -> None:
        if self.__error:
            print(self.__error)

    def __valid_ip_address(self, addr: str) -> int:
        res: int = socket.AF_INET
        try:
            if type(ipaddress.ip_address(addr)) is ipaddress.IPv6Address:
                res = socket.AF_INET6
        except ValueError:
            pass
        return res

    
