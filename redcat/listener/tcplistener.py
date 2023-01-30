import select
import socket
import typing

import redcat.style
import redcat.utils
import redcat.channel
import redcat.channel.factory
import redcat.listener

class TcpListener(redcat.listener.Listener):

    def __init__(self, host: str, port: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self.__host: str = host
        self.__port: int = port
        self._endpoints: typing.Tuple[typing.Tuple[typing.Any, ...], ...] = None
        self._families: int = 0
        self._socks: typing.List[socket.socket] = []
        

    @property
    def endpoint(self) -> str:
        res = ""
        if len(self._endpoints) == 1:
            res = f"{self._endpoints[0][0]}:{self._endpoints[0][1]}"
        else:
            res = f"{self.__host}:{self.__port}"
        return res

    @property
    def protocol(self) -> typing.Tuple[int, str]:
        return redcat.channel.ChannelProtocol.TCP, "tcp"

    def on_start(self) -> typing.Tuple[bool, str]:
        res = False
        error = "Failed to start the listener"
        try:
            self._families, self._endpoints = redcat.utils.get_remotes_and_families_from_hostname(self.__host, self.__port, socktype=socket.SOCK_STREAM)
            for family, endpoint in zip(self._families, self._endpoints):
                sock = socket.socket(family, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(endpoint)
                sock.listen(5)
                self._socks.append(sock)
            res = True
            error = ""
        except socket.error as err:
            res = False
            error = redcat.utils.get_error(err)
        return res, error

    def on_stop(self) -> None:
        if self._socks:
            for sock in self._socks:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                    sock.close()
                except:
                    pass
            self._socks = None

    def listen(self) -> redcat.channel.Channel:
        chan = None
        readables, _, _ = select.select(self._socks, [], [], 0.1)
        if readables:
            for readable in readables:
                try:
                    sock, remote = readable.accept()
                    chan = self.build_channel(protocol=redcat.channel.ChannelProtocol.TCP, remote=remote, sock=sock)
                except:
                    chan = None # TODO: Think about a way to report this error
        return chan
