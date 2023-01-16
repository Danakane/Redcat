import os
import sys
import termios
import time
import tty
import typing
import base64
import shlex

import style
import channel
import transaction
from platform import Platform, LINUX


class Linux(Platform):

    def __init__(self, chan: channel.Channel) -> None:
        super().__init__(chan, LINUX)
        self.__saved_settings = None
        self.__got_pty: bool = False
        self.__interactive: bool = False

    def which(self, name: str, handle_echo: bool=True) -> str:
        self.channel.purge()
        res, data = transaction.Transaction(f"which {name}".encode(), self, handle_echo).execute()
        return data.decode("utf-8")

    def id(self, handle_echo: bool=True) -> str:
        self.channel.purge()
        res, data = transaction.Transaction(f"id -u".encode(), self, handle_echo).execute()
        return data.decode("utf-8")

    def whoami(self, handle_echo: bool=True) -> typing.Tuple[bool, str, str]:
        self.channel.purge()
        res, data = transaction.Transaction(f"whoami".encode(), self, handle_echo).execute()
        return res, "", data.decode("utf-8").replace("\r", "").replace("\n", "")

    def download(self, rfile: str) -> typing.Tuple[bool, str, bytes]:
        res = False
        error = style.bold("Failed to download remote file ") + style.bold(style.red(f"{rfile}"))
        self.channel.purge()
        with self.channel.transaction_lock:
            res, data = transaction.Transaction(f"head -1 {rfile} > /dev/null".encode(), self, True).execute()
            if b"No such file or directory" in data:
                res = False
                error = style.bold("can't find remote file ") + style.bold(style.red(f"{rfile}"))
            elif b"Is a directory" in data:
                res = False
                error = style.bold("remote ") + style.bold(style.red(f"{rfile}")) + style.bold(" is a directory")
            elif b"Permission denied" in data:
                res = False
                error = style.bold("don't have permission to read remote file ") + style.bold(style.red(f"{rfile}"))
            else:
                res, data = transaction.Transaction(f"base64 {rfile}".encode(), self, True).execute()
                data = base64.b64decode(data)
        return res, error, data

    def upload(self, rfile: str, data: bytes) -> typing.Tuple[bool, str]:
        res = False
        error = style.bold("Failed to upload file ") + style.bold(style.red(f"{rfile}")) 
        self.channel.purge()
        encoded = base64.b64encode(data)
        # devide encoded data into chunks of 4096 bytes at most
        n = 2048 # ash/dash shell severally limit the command line length
        chunks = [encoded[i:i+n] for i in range(0, len(encoded), n)]
        # then for each chunk execute a transaction to write into a temporary file
        # the lock is used for performance -> starve the session reader main loop 
        with self.channel.transaction_lock:
            length = len(chunks) 
            tmp_file = base64.b64encode(os.urandom(16)).decode("utf-8").replace("/", "_") + ".tmp"
            parent = os.path.dirname(rfile)
            if parent:
                tmp_file = f"{parent}/{tmp_file}"
            tmp_file = shlex.quote(tmp_file)
            res, data = transaction.Transaction(f"touch {tmp_file}".encode(), self, True).execute()
            if b"No such file or directory" in data:
                res = False
                error = style.bold("can't find remote parent directory")
            elif b"Permission denied" in data:
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
                res, _ = transaction.Transaction(f"base64 -d {tmp_file} > {rfile}".encode(), self, False).execute()
                res, _ = transaction.Transaction(f"rm {tmp_file}".encode(), self, False).execute()
                error = ""
        return res, error

    def get_pty(self) -> bool:
        got_pty: bool = False
        best_shell = "sh"
        pty_options = [ 
            (["script"], "{binary_path} -qc {shell} /dev/null 2>&1\n"),
            (
                [
                    "python",
                    "python2",
                    "python2.7",
                    "python3",
                    "python3.6",
                    "python3.8",
                    "python3.9",
                    "python3.10",
                    "python3.11"
                ],
                "{binary_path} -c \"import pty; pty.spawn('{shell}')\" 2>&1\n",
            ) 
        ]
        for binaries, payload_format in pty_options:
            for binary in binaries:
                resp = self.which(binary, False) # don't have pty yet, so no echo
                if resp and not (f"which: no {binary} in" in resp or "not found" in resp) and binary in resp:
                    payload = payload_format.format(binary_path=binary, shell=best_shell)
                    self.channel.send(payload.encode())
                    got_pty = True
                    break
            if got_pty:
                self.__got_pty = got_pty
                break
        self.channel.wait_data(5)
        time.sleep(0.1)
        self.channel.purge()
        return got_pty

    def interactive(self, value: bool) -> bool:
        res = False
        if value:
            # save the terminal settings going in raw mode
            self.__saved_settings = termios.tcgetattr(sys.stdin.fileno())
            tty.setraw(sys.stdin.fileno())
            term = os.environ.get("TERM", "xterm")
            columns, rows = os.get_terminal_size(0) 
            payload = (
                " ; ".join(
                    [
                        " stty sane",
                        f" stty rows {rows} columns {columns}",
                        f" export TERM='{term}'",
                    ]
                )
            ).encode()
            transaction.Transaction(payload, self).execute()
            if self.__got_pty and not self.__interactive:
                # we already have pty but have been backgrounded
                # call exit to leave sh shell that we called
                # when we backgrounded the shell
                self.channel.send(b"exit\n")
            elif (not self.__got_pty) and self.get_pty():
                best_shell = "sh"
                better_shells = ["zsh", "bash", "ksh", "fish"]
                for shell in better_shells:
                    resp = self.which(shell, True)
                    if resp and not (f"which: no {shell} in" in resp or "not found" in resp) and shell in resp:
                        best_shell = shell
                        break
                self.channel.send(best_shell.encode() + b"\n") 
            self.channel.wait_data(0.2)
            time.sleep(0.3)
            self.channel.purge()
            self.channel.send(b"\n")
            res = True
        else: 
            # send ETX (CTRL+C) character to cancel any command that hasn't been entered
            # before exiting console raw mode
            self.channel.send(b"\x03")
            # restore saved terminal settings
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self.__saved_settings)
            if self.channel.is_open:
                # use sh shell when backgrounded
                # we can't just call exit because user may have called another shell
                self.channel.send(b"sh\n")
                self.channel.wait_data(0.2)
                time.sleep(0.3)
                self.channel.purge()
        self.__interactive = res
        return self.__interactive


