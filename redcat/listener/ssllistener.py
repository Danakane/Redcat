import typing
import select
import ssl

import redcat.utils
import redcat.channel
import redcat.listener.tcplistener


class SslListener(redcat.listener.tcplistener.TcpListener):

    def __init__(self, cert: str, key: str, password: str = None, ca_cert: str = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.__ssl_context: ssl.SSLContext = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.__ssl_context.load_cert_chain(cert, key, password)
        self.__ssl_context.check_hostname = False
        if ca_cert:
            self.__ssl_context.load_verify_locations(ca_cert)
            self.__ssl_context.verify_mode = ssl.CERT_REQUIRED
        else:
            self.__ssl_context.verify_mode = ssl.CERT_NONE

    @property
    def protocol(self) -> typing.Tuple[int, str]:
        return redcat.channel.ChannelProtocol.SSL, "ssl"

    def on_start(self) -> typing.Tuple[bool, str]:
        res, error = super().on_start()
        if res:
            try:
                ssocks = []
                for sock in self._socks:
                    ssock = self.__ssl_context.wrap_socket(sock, server_side=True)
                    sock.close()
                    ssocks.append(ssock)
                self._socks = ssocks
            except Exception as err:
                res = False
                error = redcat.utils.get_error(err)
        return res, error

    def listen(self) -> redcat.channel.Channel:
        chan = None
        readables, _, _ = select.select(self._socks, [], [], 0.1)
        if readables:
            for readable in readables:
                try:
                    sock, remote = readable.accept()
                    chan = self.build_channel(remote=remote, sock=sock, protocol=redcat.channel.ChannelProtocol.SSL, ssl_context=self.__ssl_context)
                except Exception as err:
                    error = redcat.utils.get_error(err)
                    print(redcat.style.bold(redcat.style.red("[!] error: ")) + error)
                    chan = None # TODO: Think about a way to report this error
        return chan
