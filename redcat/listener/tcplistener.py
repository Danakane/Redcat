import select
import socket
import typing

import redcat.style
import redcat.utils
import redcat.channel
import redcat.channel.factory
import redcat.listener

class TcpListener(redcat.listener.Listener):

    def __init__(self, addr: str, port: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self.__addr: str = addr
        self.__port: int = port
        self._endpoint: typing.Tuple[typing.Any] = None
        self._protocol: int = 0
        self._sock = None
        

    @property
    def endpoint(self) -> str:
         return f"{self._endpoint[0]}:{self._endpoint[1]}"

    @property
    def protocol(self) -> typing.Tuple[int, str]:
        return redcat.channel.ChannelProtocol.TCP, "tcp"

    def on_start(self) -> typing.Tuple[bool, str]:
        res = False
        error = "Failed to start the listener"
        try:
            self._protocol, self._endpoint = redcat.utils.get_remote_and_family_from_addr(self.__addr, self.__port, socktype=socket.SOCK_STREAM)
            self._sock = socket.socket(self._protocol, socket.SOCK_STREAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind(self._endpoint)
            self._sock.listen(5)
            res = True
            error = ""
        except socket.error as err:
            res = False
            error = redcat.utils.get_error(err)
        return res, error

    def on_stop(self) -> None:
        if self._sock:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
                self._sock.close()
            except:
                pass
            finally:
                self._sock = None

    def listen(self) -> redcat.channel.Channel:
        chan = None
        readables, _, _ = select.select([self._sock], [], [], 0.1)
        if readables:
            try:
                sock, remote = self._sock.accept()
                chan = self.build_channel(protocol=redcat.channel.ChannelProtocol.TCP, remote=remote, sock=sock)
            except:
                chan = None # TODO: Think about a way to report this error
        return chan
