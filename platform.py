import os
import sys
import termios
import time
import tty

import channel


class Platform:

    LINUX="linux"
    WINDOWS="windows"

    def __init__(self, chan: channel.Channel, platform_name="linux") -> None:
        self.__chan: channel.Channel = chan
        self.__platform_name: str = platform_name.lower()
        self.__stdin_fd = sys.stdin.fileno()
        self.__old_settings = termios.tcgetattr(self.__stdin_fd)    

    @property
    def platform_name(self) -> str:
        return self.__platform_name

    def which(self, name: str) -> str:
        res = b""
        if self.__platform_name == Platform.LINUX:
            self.__chan.purge()
            self.__chan.send(f"which {name}\n".encode())
            self.__chan.wait_data()
            res = self.__chan.retrieve()
        return res.decode("UTF-8")

    def get_pty(self) -> bool:
        got_pty: bool = False
        if self.__platform_name == Platform.LINUX:
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
                        payload = payload_format.format(
                                binary_path=binary, shell=best_shell)
                        self.__chan.send(payload.encode())
                        got_pty = True
                        break
                if got_pty:
                    break
        time.sleep(0.5)
        self.__chan.wait_data()
        self.__chan.purge()
        return got_pty

    def interactive(self, value: bool):
        if value: 
            tty.setraw(self.__stdin_fd)
            if self.get_pty():
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
                    + "\n"
                )
                self.__chan.send(payload.encode())
                self.__chan.wait_data()
                self.__chan.purge()
            else:
                termios.tcsetattr(self.__stdin_fd, termios.TCSADRAIN, self.__old_settings)
        else:
            termios.tcsetattr(self.__stdin_fd, termios.TCSADRAIN, self.__old_settings)

