import typing
import ssl

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

    def listen(self) -> redcat.channel.Channel:
        chan = None
        readables, _, _ = select.select([self._sock], [], [], 0.1)
        if readables:
            with context.wrap_socket(self._sock, server_side=True) as ssock: 
                sock, remote = ssock.accept()
                chan = redcat.channel.factory.get_channel(remote=remote, sock=sock, 
                    protocol=redcat.channel.ChannelProtocol.SSL, ssl_context=self.__ssl_context)
        return chan