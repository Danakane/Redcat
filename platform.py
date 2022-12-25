import os
import sys
import termios
import time
import tty
import abc
from abc import abstractmethod

import channel


class Platform(abc.ABC):

    LINUX="linux"
    WINDOWS="windows"

    def __init__(self, chan: channel.Channel, platform_name) -> None:
        self.__chan: channel.Channel = chan
        self.__platform_name: str = platform_name.lower()

    @property
    def platform_name(self) -> str:
        return self.__platform_name

    @property
    def channel(self) -> channel.Channel:
        return self.__chan

    @abstractmethod
    def interactive(self, value: bool) -> bool:
        pass


class Linux(Platform):

    def __init__(self, chan: channel.Channel) -> None:
        super().__init__(chan, Platform.LINUX)
        self.__stdin_fd = sys.stdin.fileno()
        self.__old_settings = termios.tcgetattr(self.__stdin_fd)
        self.__got_pty: bool = False

    def which(self, name: str) -> str:
        self.channel.purge()
        self.channel.send(f"which {name}\n".encode())
        self.channel.wait_data(5)
        time.sleep(0.1)
        res = self.channel.retrieve()
        return res.decode("UTF-8")

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
                    payload = payload_format.format(
                            binary_path=binary, shell=best_shell)
                    self.channel.send(payload.encode())
                    got_pty = True
                    break
            if got_pty:
                self.__got_pty = got_pty
                break
        self.channel.wait_data()
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
                    + "\n"
                )
                self.channel.send(payload.encode())
                self.channel.wait_data(2)
                time.sleep(0.5)
                self.channel.purge()
                self.channel.send(b"\n")
                res = True
        else:
            termios.tcsetattr(self.__stdin_fd, termios.TCSADRAIN, self.__old_settings)
        return res


class Windows(Platform):

    def __init__(self, chan: channel.Channel) -> None:
        super().__init__(chan, Platform.WINDOWS)

    def interactive(self, value: bool) -> bool:
        return value


def get_platform(chan: channel.Channel, platform_name: str) -> Platform:
    platform = None
    if platform_name.lower() == Platform.LINUX:
        platform = Linux(chan)
    elif platform_name.lower() == Platform.WINDOWS:
        platform = Windows(chan)
    return platform

