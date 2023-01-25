import typing
import select
import ssl

import redcat.utils
import redcat.channel
import redcat.listener.tcplistener


class SslListener(redcat.listener.tcplistener.TcpListener):

    def __init__(self, addr: str, port: int, platform_name: str, 
        cert: str, key: str, password: str = None, ca_cert: str = None,
        callback: typing.Callable = None) -> None:
        super().__init__(addr, port, platform_name, callback)
        self.__ssl_context: ssl.SSLContext = ssl.SSLContext()
        self.__ssl_context.load_cert_chain(cert, key, password)
        self.__ssl_context.check_hostname = False
        if ca_cert:
            self.__ssl_context.load_verify_locations(ca_cert)
            self.__ssl_context.verify_mode

    @property
    def protocol(self) -> typing.Tuple[int, str]:
        return redcat.channel.ChannelProtocol.SSL, "ssl"

    def on_start(self) -> typing.Tuple[bool, str]:
        res, error = super().on_start()
        if res:
            ssock = self.__ssl_context.wrap_socket(self._sock, server_side=True)
            self._sock.close()
            self._sock = ssock
        return res, error

    def listen(self) -> redcat.channel.Channel:
        chan = None
        readables, _, _ = select.select([self._sock], [], [], 0.1)
        if readables:
            try:
                sock, remote = self._sock.accept()
                chan = redcat.channel.factory.get_channel(remote=remote, sock=sock, 
                    protocol=redcat.channel.ChannelProtocol.SSL, ssl_context=self.__ssl_context)
            except:
                chan = None # TODO: Think about a way to report this error
        return chan