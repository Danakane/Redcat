import select
import socket
import typing

import utils
import channel.factory
import listener

class TcpListener(listener.Listener):

    def __init__(self, addr: str, port: int, platform_name: str, callback: typing.Callable = None) -> None:
        super().__init__(platform_name, callback)
        self.__endpoint: typing.Tuple[typing.Any] = None
        self.__protocol: int = socket.AF_INET
        if utils.valid_ip_address(addr) == socket.AF_INET:
            self.__endpoint = (addr, port)
            self.__protocol = socket.AF_INET
        else:
            self.__endpoint = (addr, port, 0, 0)
            self.__protocol = socket.AF_INET6
        self.__sock = None

    @property
    def endpoint(self) -> str:
         return f"@{self.__endpoint[0]}:{self.__endpoint[1]}"

    def on_start(self) -> typing.Tuple[bool, str]:
        res = False
        error = "Failed to start the listener"
        try:
            self.__sock = socket.socket(self.__protocol, socket.SOCK_STREAM)
            self.__sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.__sock.bind(self.__endpoint)
            self.__sock.listen(5)
            res = True
            error = ""
        except socket.error as err:
            res = False
            error = ": ".join([str(arg) for arg in err.args])
        return res, error

    def on_stop(self) -> None:
        if self.__sock:
            try:
                self.__sock.shutdown(socket.SHUT_RDWR)
                self.__sock.close()
            except:
                pass
            finally:
                self.__sock = None

    def listen(self) -> channel.Channel:
        chan = None
        readables, _, _ = select.select([self.__sock], [], [], 0.1)
        if readables:
            sock, remote = self.__sock.accept()
            chan = channel.factory.get_channel_from_remote(remote, sock, channel.TCP)
        return chan
