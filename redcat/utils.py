import typing
import socket
import tempfile
import datetime
import cryptography.x509, cryptography.x509.oid
import cryptography.hazmat.primitives.hashes, cryptography.hazmat.primitives.serialization, cryptography.hazmat.primitives.asymmetric

import redcat.style


def extract_data(raw: bytes, start: bytes, end: bytes=b"", reverse: bool=False) -> None:
    start_index = 0
    if reverse:
        start_index = raw.rfind(start)
    else:
        start_index = raw.find(start)
    extracted = b""
    if start_index != -1:
        if end:
            end_index = start_index + raw[start_index:].find(end)
            extracted = raw[start_index+len(start):end_index]
        else:
            extracted = raw[start_index+len(start):]
    return extracted

def get_remotes_and_families_from_hostname(hostname: str, port: int, socktype: int = 0) -> typing.Tuple[typing.Tuple[int], typing.Tuple[typing.Any, ...]]:
    addrinfo = None
    if not hostname:
        hostname = "::" # Use :: as default address. if /proc/sys/net/ipv6/bindv6only is set to 0 sockets will accept both IPv4 and IPv6 connections
    addrinfo = socket.getaddrinfo(hostname, port, 0, socktype)
    families = tuple([addrinfo[i][0] for i in range(len(addrinfo))])
    remotes = tuple([addrinfo[i][4] for i in range(len(addrinfo))])
    return families, remotes

def get_error(err: Exception) -> str:
    return redcat.style.bold(": ".join(str(arg) for arg in err.args))

def generate_self_signed_cert() -> str:
    """Generate a self-signed certificate"""
    filename = ""
    with tempfile.NamedTemporaryFile("wb", delete=False) as filp:
        key = cryptography.hazmat.primitives.asymmetric.rsa.generate_private_key(public_exponent=65537, key_size=4096)
        filp.write(
            key.private_bytes(
                encoding=cryptography.hazmat.primitives.serialization.Encoding.PEM,
                format=cryptography.hazmat.primitives.serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=cryptography.hazmat.primitives.serialization.NoEncryption(),
            )
        )
        # from: https://cryptography.io/en/latest/x509/tutorial/
        subject = issuer = cryptography.x509.Name(
            [
                cryptography.x509.NameAttribute(cryptography.x509.oid.NameOID.COUNTRY_NAME, u"US"),
                cryptography.x509.NameAttribute(cryptography.x509.oid.NameOID.COUNTRY_NAME, u"US"),
                cryptography.x509.NameAttribute(cryptography.x509.oid.NameOID.STATE_OR_PROVINCE_NAME, u"California"),
                cryptography.x509.NameAttribute(cryptography.x509.oid.NameOID.LOCALITY_NAME, u"San Francisco"),
                cryptography.x509.NameAttribute(cryptography.x509.oid.NameOID.ORGANIZATION_NAME, u"My Company"),
                cryptography.x509.NameAttribute(cryptography.x509.oid.NameOID.COMMON_NAME, u"mysite.com"),
            ]
        )
        cert = (
            cryptography.x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(cryptography.x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow())
            .not_valid_after(
                datetime.datetime.utcnow() + datetime.timedelta(days=365)
            )
            .add_extension(
                cryptography.x509.SubjectAlternativeName([cryptography.x509.DNSName(u"localhost")]),
                critical=False,
            )
            .sign(key, cryptography.hazmat.primitives.hashes.SHA512())
        )
        filp.write(cert.public_bytes(cryptography.hazmat.primitives.serialization.Encoding.PEM))
        filename = filp.name
    return filename