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
import redcat.platform


class Linux(redcat.platform.Platform):

    PROMPTS = {
        "sh": """'$(command printf "[remote] $(whoami)@$(hostname):$PWD\\$ ")'""",
        "dash": """'$(command printf "[remote] $(whoami)@$(hostname):$PWD\\$ ")'""",
        "zsh": """'%B%F{red}[remote] %B%F{yellow}%n@%M%B%F{reset}:%B%F{cyan}%~%B%(#.%b%F{white}#.%b%F{white}$)%b%F{reset} '""",
        "bash": """'$(command printf "\\[\\033[01;31m\\][remote] \\[\\033[0m\\]\\[\\033[01;33m\\]$(whoami)@$(hostname)\\[\\033[0m\\]:\\[\\033[1;36m\\]\w\\[\\033[0m\\]\\$ ")'""",
        "default": """'$(command printf "\\[\\033[01;31m\\][remote] \\[\\033[0m\\]\\[\\033[01;33m\\]$(whoami)@$(hostname)\\[\\033[0m\\]:\\[\\033[1;36m\\]$PWD\\[\\033[0m\\]\\$ ")'"""
    }

    def __init__(self, chan: redcat.channel.Channel) -> None:
        super().__init__(chan, redcat.platform.LINUX)

    def which(self, name: str) -> typing.Tuple[bool, bool, str]:
        self.channel.purge()
        res, cmd_success, data = redcat.transaction.Transaction(f"which {name}".encode(), self, False).execute()
        return res, cmd_success, data.decode("utf-8")

    def hostname(self) -> typing.Tuple[bool, str, bool, str]:
        self.channel.purge()
        res, cmd_success, data = redcat.transaction.Transaction(f"hostname".encode(), self, False).execute()
        if not cmd_success:
            data = b"" # if failure return empty string
        return res, cmd_success, data.decode("utf-8").replace("\r", "").replace("\n", "")

    def whoami(self) -> typing.Tuple[bool, bool, str]:
        self.channel.purge()
        res, cmd_success, data = redcat.transaction.Transaction(f"whoami".encode(), self, False).execute()
        if not cmd_success:
            data = b"" # if failure return empty string
        return res, cmd_success, data.decode("utf-8").replace("\r", "").replace("\n", "")

    def disable_history(self) -> typing.Tuple[bool, str]:
        return self.send_cmd("set +o history;unset HISTFILE;export HISTCONTROL=ignorespace;unset PROMPT_COMMAND")

    def disable_echo(self) -> typing.Tuple[bool, str]:
        return self.send_cmd("stty -echo")

    def download(self, rfile: str) -> typing.Tuple[bool, str, bytes]:
        cmd_success = False
        error = redcat.style.bold("failed to download remote file " + redcat.style.red(f"{rfile}"))
        data = b""
        self.channel.purge()
        with self.channel.transaction_lock:
            res, cmd_success, data = redcat.transaction.Transaction(f"head -1 {rfile} > /dev/null".encode(), self, False).execute()
            if not cmd_success:
                error = redcat.style.bold("can't download " + redcat.style.red(f"{rfile}") + ": " + data.decode("utf-8"))
            else:
                res, cmd_success, data = redcat.transaction.Transaction(f"base64 {rfile}".encode(), self, False).execute()
                if res and cmd_success:
                    data = base64.b64decode(data)
                    error = ""
                else:
                    error = redcat.style.bold("failed to download " + redcat.style.red(f"{rfile}") + ": " + data.decode("utf-8"))
        return res, error, data

    def upload(self, rfile: str, data: bytes) -> typing.Tuple[bool, str]:
        cmd_success = False
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
            res, cmd_success, data = redcat.transaction.Transaction(f"touch {tmp_file}".encode(), self, False).execute()
            if not cmd_success:
                error = redcat.style.bold("can't upload " + redcat.style.red(f"{rfile}") + ": " + data.decode("utf-8"))
            else:
                redcat.style.print_progress_bar(0, length, prefix = f"Upload {rfile}:", suffix = "Complete", length = 50)
                res, cmd_success, _ = redcat.transaction.Transaction(b"echo " + chunks[0] + f" > {tmp_file}".encode(), self, False).execute()
                i = 1
                if cmd_success:
                    redcat.style.print_progress_bar(i, length, prefix = f"Upload {rfile}:", suffix = "Complete", length = 50)
                    if length > 1:
                        for chunk in chunks[1:]:
                            i += 1
                            res, cmd_success, _ = redcat.transaction.Transaction(b"echo " + chunk + f" >> {tmp_file}".encode(), self, False).execute()
                            if not cmd_success:
                                break
                            redcat.style.print_progress_bar(i, length, prefix = f"Upload {rfile}:", suffix = "Complete", length = 50)
                print()
                if cmd_success:
                    # decode the temporary file into the final file and delete the temporary file
                    rfile = shlex.quote(rfile)
                    res, cmd_success, data = redcat.transaction.Transaction(f"base64 -d {tmp_file} > {rfile}".encode(), self, False).execute()
                if res:
                    redcat.transaction.Transaction(f"rm {tmp_file}".encode(), self, False).execute()
                if res and cmd_success:
                    error = ""
                else:
                    error = redcat.style.bold("failed to upload " + redcat.style.red(f"{rfile}") + ": " + data.decode("utf-8"))
        return cmd_success, error

    def get_pty(self) -> bool:
        got_pty: bool = False
        self.disable_history() # disable history
        self.disable_echo() # disable echo
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
                _, cmd_success, resp = self.which(binary)
                if cmd_success and binary in resp:
                    payload = payload_format.format(binary_path=binary, shell=best_shell)
                    got_pty, _ = self.send_cmd(payload)
                    self.disable_history()
                    self.disable_echo() # disable echo
                    break
            if got_pty:
                self._has_pty = got_pty
                break
        self.channel.wait_data(5)
        time.sleep(0.1)
        self.channel.purge()
        return got_pty

    @redcat.platform.Platform._with_lock
    def interactive(self, value: bool, session_id: str = None, raw: bool = True) -> bool:
        res = False
        if value != self._interactive:
            if value:
                # save the terminal settings going in raw mode
                if not self._interactive:
                    self._saved_settings = termios.tcgetattr(sys.stdin.fileno())
                    if raw:
                        tty.setraw(sys.stdin.fileno())
                        self._raw = True
                self.disable_history()
                self.disable_echo() # disable echo
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
                if self._has_pty and not self._interactive:
                    # we already have pty but have been backgrounded
                    # call exit to leave sh shell that we called
                    # when we backgrounded the shell
                    res, _ = self.send_cmd("exit")
                elif (not self._has_pty) and self.get_pty():
                    best_shell = "sh"
                    better_shells = ["zsh", "bash", "ksh", "fish", "dash"]
                    for shell in better_shells:
                        _, res, resp = self.which(shell)
                        if res and shell in resp:
                            best_shell = shell
                            break
                    res, _ = self.send_cmd(best_shell) 
                    self.disable_history() 
                    prompt = Linux.PROMPTS["default"]
                    if best_shell in Linux.PROMPTS.keys():
                        prompt = Linux.PROMPTS[best_shell]
                    prompt = prompt.replace("remote", f"session {session_id}")
                    redcat.transaction.Transaction(f"export PS1={prompt}".encode(), self, False).execute()
                if res:
                    self.channel.wait_data(1)
                    time.sleep(0.5)
                    self.channel.purge()
                    res, _ = self.send_cmd("")
                if res:
                    self._interactive = True
                else:
                    termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._saved_settings)
                    self._raw = False
            else: 
                # send ETX (CTRL+C) character to cancel any command that hasn't been entered
                # before exiting console raw mode
                res, _ = self.send_cmd("\x03")
                # restore saved terminal settings
                if self._interactive:
                    termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._saved_settings)
                    self._raw = False
                if res and self.channel.is_open:
                    # use sh shell when backgrounded
                    # we can't just call exit because user may have called another shell
                    self.send_cmd("sh")
                    self.disable_history()
                    self.disable_echo()
                    self.send_cmd("unset PS1") # remove prompt
                    self.channel.wait_data(1)
                    time.sleep(0.2)
                    self.channel.purge()
                self._interactive = False
        else:
            res = True
        return res


