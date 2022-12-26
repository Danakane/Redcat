import os
import sys
import termios
import time
import tty
import typing
import base64

import channel
import transaction
from platform import Platform, LINUX


class Linux(Platform):

    def __init__(self, chan: channel.Channel) -> None:
        super().__init__(chan, LINUX)
        self.__stdin_fd = sys.stdin.fileno()
        self.__old_settings = termios.tcgetattr(self.__stdin_fd)
        self.__got_pty: bool = False

    def which(self, name: str) -> str:
        self.channel.purge()
        res, data = transaction.Transaction(f"which {name}".encode(), self.channel, self, not self.interactive).execute()
        return data.decode("utf-8")

    def download(self, rfile: str) -> typing.Tuple[bool, str, bytes]:
        self.channel.purge()
        # passing has_echo parameter to True
        # because we're not in raw mode and
        # and the command if handled can pollute the output
        res, data = transaction.Transaction(f"base64 {rfile}".encode(), self.channel, self, True).execute()
        data = base64.b64decode(data)
        return res, "", data

    def upload(self, rfile: str, data: bytes) -> typing.Tuple[bool, str]:
        self.channel.purge()
        encoded = base64.b64encode(data)
        # passing has_echo parameter to False because True may cause channel to hang
        # And we don't care about the output anyway
        res, _ = transaction.Transaction(b"echo " + encoded + f" | base64 -d > {rfile}".encode(), self.channel, self, False).execute()
        return res, ""

    def get_pty(self) -> bool:
        got_pty: bool = False
        best_shell = "sh"
        better_shells = ["zsh", "bash", "ksh", "fish"]
        for shell in better_shells:
            res = self.which(shell)
            if shell in res:
                best_shell = shell
                break
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
                res = self.which(binary)
                if binary in res:
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
            if self.__got_pty or self.get_pty():
                tty.setraw(self.__stdin_fd)
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
                transaction.Transaction(payload, self.channel, self, True).execute()
                self.channel.wait_data(5)
                time.sleep(0.1)
                self.channel.purge()
                self.channel.send(b"\n")
                res = True
        else:
            termios.tcsetattr(self.__stdin_fd, termios.TCSADRAIN, self.__old_settings)
        return res


