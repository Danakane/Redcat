#!/usr/bin/python

import argparse

import redcat.style
import redcat.channel
import redcat.platform
import redcat.manager
import redcat.engine

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = "redcat: a remote shell handler implemented in python for CTFs, pentests and red team exercises.")
    parser.add_argument("-l", "--bind", action="store_true", default=False, help="use bind mode")
    parser.add_argument("-m", "--platform", type=str, nargs=1, choices=[redcat.platform.LINUX, redcat.platform.WINDOWS], 
        default=redcat.platform.LINUX, help="expected platform")
    parser.add_argument("--host", type=str, nargs="?", help="host to bind or to connect")
    parser.add_argument("port", type=int, nargs="?", help="port to bind or to connect")
    parser.add_argument("--protocol", type=str, nargs=1, choices=["tcp", "ssl"], default="tcp", help="channel protocol")
    parser.add_argument("--cert", type=str, nargs=1, help="path of certificate for the ssl shell listener")
    parser.add_argument("--key", type=str, nargs=1, help="path of private key of the listener certificate")
    parser.add_argument("--password", type=str, nargs=1, help="password of the private key")
    parser.add_argument("--ca-cert", type=str, nargs=1, help="CA certificate of the ssl reverse shell")
    args = parser.parse_args()
    port = 0
    if args.port:
        port = args.port
    res = True
    error = ""
    with redcat.engine.Engine("redcat") as rcat:
        if port:
            kwargs = {k:v[0] if isinstance(v, list) and len(v) == 1 else v for k,v in args._get_kwargs() if v is not None}
            bind = args.bind
            del kwargs["bind"]
            if not bind and "host" not in kwargs.keys():
                parser.error("redcat require --host flag in connect mode")
            kwargs["protocol"] = redcat.channel.ChannelProtocol.SSL if kwargs["protocol"] == "ssl" else redcat.channel.ChannelProtocol.TCP
            kwargs["platform_name"] = kwargs["platform"]
            del kwargs["platform"]
            if kwargs["protocol"] == redcat.channel.ChannelProtocol.TCP:
                if "cert" in kwargs.keys() or "key" in kwargs.keys() or "password" in kwargs.keys() or "ca_cert" in kwargs.keys():
                    parser.error("redcat doesn't accept --cert, --key, --password and --ca-cert flags when not using protocol ssl")
            if bind:
                if not "host" in kwargs.keys():
                    kwargs["host"] = "::"
                if kwargs["protocol"] == redcat.channel.ChannelProtocol.SSL:
                    if not ("cert" in kwargs.keys() and "key" in kwargs.keys()): 
                        parser.error("redcat requires --cert and --key flags when using protocol ssl in bind mode")
                res, error = rcat.manager.listen(False, **kwargs)
            else:
                if not "host" in kwargs.keys(): 
                    parser.error("redcat requires --host flag in connect mode")
                res, error = rcat.manager.connect(**kwargs)
        if res:
            rcat.run()
        else:
            print(redcat.style.bold(redcat.style.red("[!] error:")) + f" {error}")

