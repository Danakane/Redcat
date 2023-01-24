import select
import socket
import typing

import redcat.style
import redcat.utils
import redcat.channel
import redcat.channel.factory
import redcat.listener

class TcpListener(redcat.listener.Listener):

    def __init__(self, addr: str, port: int, platform_name: str, callback: typing.Callable = None) -> None:
        super().__init__(platform_name, callback)
        self._endpoint: typing.Tuple[typing.Any] = None
        self._protocol: int = socket.AF_INET
        if redcat.utils.valid_ip_address(addr) == socket.AF_INET:
            self._endpoint = (addr, port)
            self._protocol = socket.AF_INET
        else:
            self._endpoint = (addr, port, 0, 0)
            self._protocol = socket.AF_INET6
        self._sock = None

    @property
    def endpoint(self) -> str:
         return f"@{self._endpoint[0]}:{self._endpoint[1]}"

    def on_start(self) -> typing.Tuple[bool, str]:
        res = False
        error = "Failed to start the listener"
        try:
            self._sock = socket.socket(self._protocol, socket.SOCK_STREAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind(self._endpoint)
            self._sock.listen(5)
            res = True
            error = ""
        except socket.error as err:
            res = False
            error = redcat.style.bold(": ".join([str(arg) for arg in err.args]))
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
            sock, remote = self._sock.accept()
            chan = redcat.channel.factory.get_channel(remote=remote, sock=sock, protocol=redcat.channel.ChannelProtocol.TCP)
        return chan
