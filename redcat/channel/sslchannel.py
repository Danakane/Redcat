import typing
import socket
import ssl

import redcat.style
import redcat.channel.tcpchannel


class SslChannel(redcat.channel.tcpchannel.TcpChannel):

    def __init__(self, remote: typing.Tuple[typing.Any, ...] = None, sock: socket.socket = None, addr: str = None, port: int = None, 
        ssl_context: ssl.SSLContext=None, cert: str=None, key: str=None, password: str=None, ca_cert: str=None) -> None:
        super().__init__(remote, sock, addr, port)
        self.__cert: str = cert
        self.__key: str = key
        self.__password: str = password
        self.__ca_cert: str = ca_cert
        self.__ssl_context: ssl.SSLContext = ssl_context
        if not self.__ssl_context:
            self.__ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            self.__ssl_context.check_hostname = False
            if self.__ca_cert:
                self.__ssl_context.load_verify_locations(self.__ca_cert)
                self.__ssl_context.verify_mode = ssl.CERT_REQUIRED
            else:
                self.__ssl_context.verify_mode = ssl.CERT_NONE
            if self.__cert:
                self.__ssl_context.load_cert_chain(self.__cert, self.__key, self.__password)
            

    def connect(self) -> typing.Tuple[bool, str]:
        res = False
        error = "Failed to create session"
        if not self._sock:
            res, error = super().connect()
            if res:
                try:
                    ssock = self.__ssl_context.wrap_socket(self._sock)
                    self._sock.close() # we can call close but not shutdown on the original socket. This would raise an "OSError: Bad file descriptor"
                    self._sock = ssock # replace the original socket with the ssl socket
                except Exception as err:
                    res = False
                    error = error = redcat.utils.get_error(err)
        else:
            res = True
            error = ""
        return res, error