#!/usr/bin/python

import sys
import argparse

import redcat.style
import redcat.channel
import redcat.platform
import redcat.manager
import redcat.engine

if __name__ == "__main__":
    cli = argparse.ArgumentParser(description = "redcat: a remote shell handler implemented in python for CTFs, pentest and red team engagements.", add_help=False)
    cli.add_argument("--protocol", type=str, nargs=1, choices=["tcp", "ssl"], default="tcp", help="channel protocol")
    cli.add_argument("-l", "--bind", action="store_true", default=False, help="use bind mode")
    cli.add_argument("-m", "--platform", type=str, nargs=1, choices=[redcat.platform.LINUX, redcat.platform.WINDOWS], 
        default=redcat.platform.LINUX, help="expected platform")
    main_args, _ = cli.parse_known_args()
    parser = argparse.ArgumentParser(parents=[cli], conflict_handler="resolve")
    if main_args.bind:
        parser.add_argument("--host", type=str, nargs="?", default="::", help="host to bind")
        parser.add_argument("port", type=int, nargs="?", help="port to bind")
    else:
        parser.add_argument("host", type=str, nargs="?", help="host to connect")
        parser.add_argument("port", type=int, nargs="?", help="port to connect")
    if main_args.protocol[0] == "ssl":
        parser.add_argument("--cert", type=str, nargs=1, help="path to the certificate of the ssl listener or client")
        parser.add_argument("--key", type=str, nargs=1, help="path to the private key of the listener/client's certificate")
        parser.add_argument("--password", type=str, nargs=1, help="password of the private key")
        parser.add_argument("--ca-cert", type=str, nargs=1, help="path to the CA certificate of the ssl bind or reverse shell")
    args = parser.parse_args()
    with redcat.engine.Engine("redcat") as rcat:
        res = True
        error = ""
        if len(sys.argv) > 1:
            args = parser.parse_args()
            kwargs = {k:v[0] if isinstance(v, list) and len(v) == 1 else v for k,v in args._get_kwargs() if v is not None}
            del kwargs["bind"]
            kwargs["protocol"] = redcat.channel.ChannelProtocol.SSL if kwargs["protocol"] == "ssl" else redcat.channel.ChannelProtocol.TCP
            kwargs["platform_name"] = kwargs["platform"]
            del kwargs["platform"]
            if args.bind:
                res, error = rcat.manager.listen(False, **kwargs)
            else:
                res, error = rcat.manager.connect(**kwargs)
        if res:
            rcat.run()
        else:
            print(redcat.style.bold(redcat.style.red("[!] error:")) + f" {error}")

