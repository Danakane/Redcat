import sys
import select
import socket
import select
import threading
import typing

import utils
import channel


class TcpChannel(channel.Channel):

    def __init__(self, remote: typing.Tuple[typing.Any, ...] = None, sock: socket.socket = None, addr: str = None, port: int = None) -> None:
        super().__init__()
        self.__remote: typing.Tuple[typing.Any, ...] = None
        self.__sock: socket.socket = None
        self.__addr: str = None
        self.__port: int = None
        self.__error: str = ""
        if remote and sock:
            self.__remote = remote
            self.__sock = sock
        else:
            self.__addr = addr
            self.__port = port

    @property
    def remote(self) -> str:
        res = ""
        if self.__remote:
            res = f"@{self.__remote[0]}:{self.__remote[1]}"
        return res
         
    def connect(self) -> bool:
        res: bool = True
        if not self.__sock:
            try:
                protocol = socket.AF_INET
                endpoint = (self.__addr, self.__port)
                if utils.valid_ip_address(self.__addr) == socket.AF_INET6:
                    endpoint = (self.__addr, self.__port, 0, 0)
                    protocol = socket.AF_INET6
                self.__sock = socket.socket(protocol, socket.SOCK_STREAM)
                self.__sock.connect(endpoint)
                self.__remote = endpoint
            except OSError:
                res = False
            except Exception as err:
                res = False
                print(err.args)
                self.__error = err.args[0]
        return res

    def on_open(self) -> None:
        self.connect()

    def on_close(self) -> None:
        if self.__sock:
            try:
                self.__sock.shutdown(socket.SHUT_RDWR)
                self.__sock.close() 
            except:
                pass
            finally:
                self.__sock = None

    def on_connection_established(self) -> None:
        if self.is_open:
            print(f"Connected to remote {self.__remote[0]}:{self.__remote[1]}", end="")
            sys.stdout.flush()
            sys.stdin.flush()

    def on_error(self) -> None:
        if self.__error:
            print(self.__error)

    def recv(self) -> typing.Tuple[bool, bytes]:
        res = True
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
                    res = False
        except select.error as err:
            res = False
            self.__error = err.args[1]
        return res, data

    def send(self, data: bytes) -> None:
        self.__sock.send(data)

    

    
