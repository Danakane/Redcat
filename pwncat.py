#!/usr/bin/python

import argparse

import platform
import manager
import engine

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = "pwncat: a netcat on steroid for CTFs, pentests and red team exercises")
    parser.add_argument("-l", "--bind", action="store_true", help="use bind mode")
    parser.add_argument("-m", "--platform-name", type=str, nargs=1, help="expected platform (linux or windows)")
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
    platform_name = platform.Platform.LINUX
    if args.platform_name and args.platform_name[0] and args.platform_name[0].lower() == platform.Platform.WINDOWS:
        platform_name = args.platform[0]
    try:
        with engine.Engine() as pwncat:
            if port:
                pwncat.manager.create_session(addr, port, platform_name, bind)
            pwncat.run()
    except KeyboardInterrupt:
        pass

