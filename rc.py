#!/usr/bin/python

import argparse

import redcat.style
import redcat.platform
import redcat.manager
import redcat.engine

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = "redcat: a remote shell handler implemented in python for CTFs, pentests and red team exercises.")
    parser.add_argument("-l", "--bind", action="store_true", help="use bind mode")
    parser.add_argument("-m", "--platform", type=str, nargs=1, choices=["linux", "windows"], help="expected platform")
    parser.add_argument("-a", "--addr", type=str, nargs=1, help="address to bind or to connect")
    parser.add_argument("-p", "--port", type=int, nargs=1, help="port to bind or to connect")
    args = parser.parse_args()
    bind = args.bind
    addr = ""
    if args.addr and args.addr[0]:
        addr = args.addr[0]
    port = 0
    if args.port and args.port[0]:
        port = args.port[0]
    platform_name = redcat.platform.LINUX
    if args.platform and args.platform[0] and args.platform[0].lower() == redcat.platform.WINDOWS:
        platform_name = args.platform[0]
    res = True
    error = ""
    with redcat.engine.Engine("redcat") as rcat:
        if port:
            if bind:
                res, error = rcat.manager.listen(addr, port, platform_name)
            else:
                res, error = rcat.manager.connect(addr, port, platform_name)
        if res:
            rcat.run()
        else:
            print(redcat.style.bold(redcat.style.red("[!] error:")) + f" {error}")

