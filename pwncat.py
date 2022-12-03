#!/usr/bin/python

import os
import socket
import sys
import termios
import threading
import time
import tty
import argparse

import channel
import session

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = "pwncat tool")
    parser.add_argument("-l", "--bind", action="store_true", help="listening mode")
    parser.add_argument("addr", type=str, nargs="?", help="address to bind or to connect")
    parser.add_argument("port", type=int, nargs=1, help="port to bind or to connect")

    args = parser.parse_args()
    mode = channel.Channel.BIND if args.bind else channel.Channel.CONNECT
    addr = ""
    if args.addr:
        addr = args.addr
    port = args.port[0]

    with session.Session(addr, port, mode=mode) as sess:
        try:
            if sess.wait_open():
                sess.interactive(True)
                sess.start()
                sess.wait_stop()
        except KeyboardInterrupt:
            pass
        except Exception:
            pass
