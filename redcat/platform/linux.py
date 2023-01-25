import os
import sys
import termios
import time
import tty
import typing
import base64
import shlex

import redcat.style
import redcat.channel
import redcat.transaction
from redcat.platform import Platform, LINUX


class Linux(Platform):

    PROMPTS = {
        "sh": """'$(command printf "[remote] $(whoami)@$(hostname):$PWD\\$ ")'""",
        "dash": """'$(command printf "[remote] $(whoami)@$(hostname):$PWD\\$ ")'""",
        "zsh": """'%B%F{red}[remote] %B%F{yellow}%n@%M%B%F{reset}:%B%F{cyan}%~%B%(#.%b%F{white}#.%b%F{white}$)%b%F{reset} '""",
        "bash": """'$(command printf "\\[\\033[01;31m\\][remote] \\[\\033[0m\\]\\[\\033[01;33m\\]$(whoami)@$(hostname)\\[\\033[0m\\]:\\[\\033[1;36m\\]\w\\[\\033[0m\\]\\$ ")'""",
        "default": """'$(command printf "\\[\\033[01;31m\\][remote] \\[\\033[0m\\]\\[\\033[01;33m\\]$(whoami)@$(hostname)\\[\\033[0m\\]:\\[\\033[1;36m\\]$PWD\\[\\033[0m\\]\\$ ")'"""
    }

    def __init__(self, chan: redcat.channel.Channel) -> None:
        super().__init__(chan, LINUX)
        self.__saved_settings = None
        self.__got_pty: bool = False
        self.__interactive: bool = False

    @property
    def is_interactive(self) -> bool:
        return self.__interactive

    def which(self, name: str, handle_echo: bool=True) -> typing.Tuple[bool, bool, str]:
        self.channel.purge()
        res, cmd_success, data = redcat.transaction.Transaction(f"which {name}".encode(), self, handle_echo).execute()
        return res, cmd_success, data.decode("utf-8")

    def hostname(self, handle_echo: bool=True) -> typing.Tuple[bool, str, bool, str]:
        self.channel.purge()
        res, cmd_success, data = redcat.transaction.Transaction(f"hostname".encode(), self, handle_echo).execute()
        if not cmd_success:
            data = b"" # if failure return empty string
        return res, cmd_success, data.decode("utf-8").replace("\r", "").replace("\n", "")

    def whoami(self, handle_echo: bool=True) -> typing.Tuple[bool, bool, str]:
        self.channel.purge()
        res, cmd_success, data = redcat.transaction.Transaction(f"whoami".encode(), self, handle_echo).execute()
        if not cmd_success:
            data = b"" # if failure return empty string
        return res, cmd_success, data.decode("utf-8").replace("\r", "").replace("\n", "")

    def disable_history(self, handle_echo: bool=True) -> typing.Tuple[bool, bool, str]:
        self.channel.purge()
        self.send_cmd("set +o history")
        res, cmd_success, data = redcat.transaction.Transaction(
            "unset HISTFILE && export HISTCONTROL=ignorespace && unset PROMPT_COMMAND".encode(), 
            self, handle_echo).execute()
        if not cmd_success:
            data = b"" # if failure return empty string
        return res, cmd_success, data.decode("utf-8").replace("\r", "").replace("\n", "")

    def download(self, rfile: str) -> typing.Tuple[bool, str, bytes]:
        res = False
        error = redcat.style.bold("failed to download remote file ") + redcat.style.bold(redcat.style.red(f"{rfile}"))
        data = b""
        self.channel.purge()
        with self.channel.transaction_lock:
            _, res, data = redcat.transaction.Transaction(f"head -1 {rfile} > /dev/null".encode(), self, True).execute()
            if not res:
                error = redcat.style.bold("can't download ") + redcat.style.bold(redcat.style.red(f"{rfile}"))+ redcat.style.bold(": " + data.decode("utf-8"))
            else:
                _, res, data = redcat.transaction.Transaction(f"base64 {rfile}".encode(), self, True).execute()
                if res:
                    data = base64.b64decode(data)
                    error = ""
                else:
                    error = redcat.style.bold("failed to download ") + redcat.style.bold(redcat.style.red(f"{rfile}")) + redcat.style.bold(": " + data.decode("utf-8"))
        return res, error, data

    def upload(self, rfile: str, data: bytes) -> typing.Tuple[bool, str]:
        res = False
        error = redcat.style.bold("failed to upload file ") + redcat.style.bold(redcat.style.red(f"{rfile}")) 
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
            res, cmd_success, data = redcat.transaction.Transaction(f"touch {tmp_file}".encode(), self, True).execute()
            if not cmd_success:
                res = False
                error = redcat.style.bold("can't upload ") + redcat.style.bold(redcat.style.red(f"{rfile}")) + redcat.style.bold(": " + data.decode("utf-8"))
            else:
                redcat.style.print_progress_bar(0, length, prefix = f"Upload {rfile}:", suffix = "Complete", length = 50)
                redcat.transaction.Transaction(b"echo " + chunks[0] + f" > {tmp_file}".encode(), self, True).execute()
                i = 1
                redcat.style.print_progress_bar(i, length, prefix = f"Upload {rfile}:", suffix = "Complete", length = 50)
                if length > 1:
                    for chunk in chunks[1:]:
                        i += 1
                        redcat.transaction.Transaction(b"echo " + chunk + f" >> {tmp_file}".encode(), self, False).execute()
                        redcat.style.print_progress_bar(i, length, prefix = f"Upload {rfile}:", suffix = "Complete", length = 50)
                print()
                # decode the temporary file into the final file and delete the temporary file
                rfile = shlex.quote(rfile)
                _, res, data = redcat.transaction.Transaction(f"base64 -d {tmp_file} > {rfile}".encode(), self, True).execute()
                redcat.transaction.Transaction(f"rm {tmp_file}".encode(), self, True).execute()
                if res:
                    error = ""
                else:
                    redcat.style.bold("failed to upload ") + redcat.style.bold(redcat.style.red(f"{rfile}")) + redcat.style.bold(": " + data.decode("utf-8"))
        return res, error

    def get_pty(self) -> bool:
        got_pty: bool = False
        self.disable_history(handle_echo=False) # disable history (don't have pty yet, so no echo)
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
                "{binary_path} -c \"import pty; pty.spawn('{shell}')\" 2>&1",
            ) 
        ]
        for binaries, payload_format in pty_options:
            for binary in binaries:
                _, cmd_success, resp = self.which(binary, False) # don't have pty yet, so no echo
                if cmd_success and binary in resp:
                    payload = payload_format.format(binary_path=binary, shell=best_shell)
                    got_pty, _ = self.send_cmd(payload)
                    self.disable_history()
                    #self.send_cmd("set +o history")
                    break
            if got_pty:
                self.__got_pty = got_pty
                break
        self.channel.wait_data(5)
        time.sleep(0.1)
        self.channel.purge()
        return got_pty

    def interactive(self, value: bool, session_id: str = None) -> bool:
        res = False
        if value:
            # save the terminal settings going in raw mode
            if not self.__interactive:
                self.__saved_settings = termios.tcgetattr(sys.stdin.fileno())
                tty.setraw(sys.stdin.fileno())
            #res, _ = self.send_cmd("set +o history")
            self.disable_history(handle_echo=False)
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
            )
            self.send_cmd(payload)
            if self.__got_pty and not self.__interactive:
                # we already have pty but have been backgrounded
                # call exit to leave sh shell that we called
                # when we backgrounded the shell
                res, _ = self.send_cmd("exit")
            elif (not self.__got_pty) and self.get_pty():
                best_shell = "sh"
                better_shells = ["zsh", "bash", "ksh", "fish", "dash"]
                for shell in better_shells:
                    _, res, resp = self.which(shell, True)
                    if res and shell in resp:
                        best_shell = shell
                        break
                res, _ = self.send_cmd(best_shell) 
                self.disable_history(handle_echo=False) # Don't handle echo here, shell prompt ansi escape sequence can corrupt the base64 string in the echo
                #res, _ = self.send_cmd("set +o history")
                prompt = Linux.PROMPTS["default"]
                if best_shell in Linux.PROMPTS.keys():
                    prompt = Linux.PROMPTS[best_shell]
                prompt = prompt.replace("remote", f"session {session_id}")
                redcat.transaction.Transaction(f"export PS1={prompt}".encode(), self, True).execute()
                #self.send_cmd(f"export PS1={prompt}")
            if res:
                self.channel.wait_data(1)
                time.sleep(0.5)
                self.channel.purge()
                res, _ = self.channel.send(b"\n")
            if res:
                self.__interactive = True
            else:
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self.__saved_settings)
        else: 
            # send ETX (CTRL+C) character to cancel any command that hasn't been entered
            # before exiting console raw mode
            res, _ = self.channel.send(b"\x03\n")
            # restore saved terminal settings
            if self.__interactive:
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self.__saved_settings)
            if res and self.channel.is_open:
                # use sh shell when backgrounded
                # we can't just call exit because user may have called another shell
                res, _ = self.send_cmd("sh")
                res, _, _ = self.disable_history()
                res, _ = self.send_cmd("unset PS1") # remove prompt
                self.channel.wait_data(1)
                time.sleep(0.2)
                self.channel.purge()
            self.__interactive = False
        return res


