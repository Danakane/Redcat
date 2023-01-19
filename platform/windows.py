import base64
import os
import typing
import tty
import termios
import sys
import shlex

import style
import channel
import transaction
from platform import Platform, WINDOWS


class Windows(Platform):

    def __init__(self, chan: channel.Channel) -> None:
        super().__init__(chan, WINDOWS)
        self.__interactive: bool = False

    def is_interactive(self) -> bool:
        return self.__interactive

    def interactive(self, value: bool, session_id: str = None) -> bool:
        self.__interactive = value
        return True

    def build_transaction(self, payload: bytes, start: bytes, end: bytes) -> bytes:
        return b"echo " + start + b" & " + payload + b" & " + b"echo " + end + b"\n"

    def whoami(self) -> typing.Tuple[bool, str, str]:
        self.channel.purge()
        res, data = transaction.Transaction(f"whoami".encode(), self, True).execute()
        return res, "", data.decode("utf-8").replace("\r", "").replace("\n", "").strip()

    def hostname(self) -> typing.Tuple[bool, str, str]:
        self.channel.purge()
        res, data = transaction.Transaction(f"hostname".encode(), self, True).execute()
        return res, "", data.decode("utf-8").replace("\r", "").replace("\n", "").strip()

    def download(self, rfile: str) -> typing.Tuple[bool, str, bytes]:
        res = False
        rfile = rfile.replace("'", "\"")
        error = style.bold("Failed to download remote file ") + style.bold(style.red(f"{rfile}"))
        self.channel.purge()
        with self.channel.transaction_lock:
            res, data = transaction.Transaction(f"type {rfile}".encode(), self, True).execute()
            if b"The system cannot find the file specified." in data:
                res = False
                error = style.bold("can't find remote file ") + style.bold(style.red(f"{rfile}"))
            elif b"The parameter is incorrect." in data:
                res = False
                error = style.bold("remote ") + style.bold(style.red(f"{rfile}")) + style.bold(" is a directory")
            elif b"Access is denied." in data:
                res = False
                error = style.bold("don't have permission to read remote file ") + style.bold(style.red(f"{rfile}"))
            else:
                tmp_fname = base64.b64encode(os.urandom(16)).decode("utf-8").replace("/", "_").replace("=", "0") + ".tmp"
                tmp_file = f"\"C:\\windows\\tasks\\{tmp_fname}\""
                res, _ = transaction.Transaction(f"certutil -encode {rfile} {tmp_file}".encode(), self, False).execute()
                res, data = transaction.Transaction(f"findstr /v CERTIFICATE {tmp_file}".encode(), self, True).execute()
                res, _ = transaction.Transaction(f"del {tmp_file}".encode(), self, False).execute()
                data = base64.b64decode(data)
        return res, error, data

    def upload(self, rfile: str, data: bytes) -> typing.Tuple[bool, str]:
        res = False
        rfile = rfile.replace("'", "\"")
        error = style.bold("Failed to upload file ") + style.bold(style.red(f"{rfile}")) 
        self.channel.purge()
        encoded = base64.b64encode(data)
        # devide encoded data into chunks of 4096 bytes at most
        n = 4096
        chunks = [encoded[i:i+n] for i in range(0, len(encoded), n)]
        # then for each chunk execute a transaction to write into a temporary file
        # the lock is used for performance -> starve the session reader main loop 
        with self.channel.transaction_lock:
            length = len(chunks) 
            tmp_file = base64.b64encode(os.urandom(16)).decode("utf-8").replace("/", "_").replace("=", "0") + ".tmp"
            parent = os.path.dirname(rfile)
            if parent:
                tmp_file = f"{parent}/{tmp_file}"
            tmp_file = shlex.quote(tmp_file).replace("'", "\"")
            res, data = transaction.Transaction(f"echo \"\" > {tmp_file}".encode(), self, True).execute()
            if b"The system cannot find the path specified." in data:
                res = False
                error = style.bold("can't find remote parent directory")
            elif b"Access is denied." in data:
                res = False
                error = style.bold("don't have permission to write in remote parent directory")
            else:
                style.print_progress_bar(0, length, prefix = f"Upload {rfile}:", suffix = "Complete", length = 50)
                # Don't handle echo, it's less error prone and we don't care about the output anyway
                res, _ = transaction.Transaction(b"echo " + chunks[0] + f" > {tmp_file}".encode(), self, False).execute()
                i = 1
                style.print_progress_bar(i, length, prefix = f"Upload {rfile}:", suffix = "Complete", length = 50)
                if length > 1:
                    for chunk in chunks[1:]:
                        i += 1
                        res, _ = transaction.Transaction(b"echo " + chunk + f" >> {tmp_file}".encode(), self, False).execute()
                        style.print_progress_bar(i, length, prefix = f"Upload {rfile}:", suffix = "Complete", length = 50)
                print()
                # decode the temporary file into the final file and delete the temporary file
                rfile = shlex.quote(rfile)
                res, _ = transaction.Transaction(f"certutil -decode {tmp_file} {rfile}".encode(), self, False).execute()
                res, _ = transaction.Transaction(f"del {tmp_file}".encode(), self, False).execute()
                error = ""
        return res, error
