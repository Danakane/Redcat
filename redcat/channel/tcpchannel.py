import sys
import select
import socket
import select
import threading
import typing

import redcat.style
import redcat.utils
import redcat.channel


class TcpChannel(redcat.channel.Channel):

    def __init__(self, remote: typing.Tuple[typing.Any, ...] = None, sock: socket.socket = None, host: str = None, port: int = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._remote: typing.Tuple[typing.Any, ...] = None
        self._sock: socket.socket = None
        self._host: str = None
        self._port: int = None
        if remote and sock:
            self._remote = remote
            self._sock = sock
        else:
            self._host = host
            self._port = port

    @property
    def remote(self) -> str:
        res = ""
        if self._remote:
            res = f"{self._remote[0]}:{self._remote[1]}"
        return res

    @property
    def protocol(self) -> typing.Tuple[int, str]:
        return redcat.channel.ChannelProtocol.TCP, "tcp"
         
    def connect(self) -> typing.Tuple[bool, str]:
        res = False
        error = "Failed to create session"
        if not self._sock:
            try:
                protocols, endpoints = redcat.utils.get_remotes_and_families_from_hostname(self._host, self._port, socket.SOCK_STREAM)
                for protocol, endpoint in zip(protocols, endpoints):
                    try:
                        self._sock = socket.socket(protocol, socket.SOCK_STREAM)
                        self._sock.connect(endpoint)
                        self._remote = endpoint
                        res = True
                        error = ""
                    except socket.error:
                        pass
            except Exception as err:
                error = redcat.utils.get_error(err)
        else:
            res = True
            error = ""
        return res, error

    def on_open(self) -> typing.Tuple[bool, str]:
        return self.connect()

    def on_close(self) -> None:
        if self._sock:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
                self._sock.close() 
            except:
                pass
            finally:
                self._sock = None

    def on_connection_established(self) -> None:
        if self.is_open:
            print(f"Connected to remote {self._remote[0]}:{self._remote[1]}", end="")
            sys.stdout.flush()

    def recv(self) -> typing.Tuple[bool, str, bytes]:
        res = False
        error = ""
        data = b""
        if self.is_open:
            try:
                res = True
                readables, _, _= select.select([self._sock], [], [], 0.05)
                if readables and readables[0] == self._sock:
                    try:
                        data = self._sock.recv(4096)
                        if len(data) == 0:
                            res = False
                            error = redcat.style.bold(f"Connection with remote {self._remote[0]}:{self._remote[1]} broken")
                    except IOError:
                        res = True # to avoid bad descriptor error
                    except Exception as err:
                        error = error = redcat.utils.get_error(err)
                        res = False
            except select.error as err:
                res = False
                error =  ": ".join(str(arg) for arg in err.args)
        return res, error, data

    def send(self, data: bytes) -> typing.Tuple[bool, str]:
        res = False
        error = ""
        try:
            self._sock.send(data)
            res = True
            error = ""
        except Exception as err:
            error = redcat.utils.get_error(err)
        return res, error


    

    
