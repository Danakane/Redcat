import argparse
import readline
import shlex
import typing
import threading
import subprocess
import sys
import os
import signal
import time
import datetime
import getpass

import redcat.style
import redcat.command
import redcat.platform
import redcat.manager


class Engine:

    def __init__(self, name: str) -> None:
        self.__name: str = name
        self.__running: bool = False
        self.__user: str = getpass.getuser()
        self.__cwd: str = os.getcwd()
        # logs
        self.__logs: typing.List[str] = []
        self.__lock_logs: threading.Lock = threading.Lock()
        self.__logger_thread: threading.Thread = None
        # main thread interruptible section
        self.__interruptible_section: redcat.utils.MainThreadInterruptibleSection = redcat.utils.MainThreadInterruptibleSection()
        self.__input = self.__interruptible_section.interruptible(self.__input)
        self.__print_logs = self.__interruptible_section.interrupter(self.__print_logs)
        # sessions manager
        self.__manager: redcat.manager.Manager = redcat.manager.Manager(logger_callback=self.__on_log_message)
        # commands
        self.__commands: typing.Dict[str, redcat.command.Command] = {}
        # exit command
        cmd_exit = redcat.command.Command("exit", self, f"exit {self.__name}")
        @cmd_exit.command(None)
        def __exit(parent: Engine) -> typing.Tuple[bool, str]:
            parent.__running = False
            parent.manager.clear()
            return True, ""
        self.__commands[cmd_exit.name] = cmd_exit
        # clear command
        cmd_clear = redcat.command.Command("clear", self, "clear the screen")
        @cmd_clear.command(None)
        def __clear(parent) -> typing.Tuple[bool, str]:     
            subprocess.run("clear")
            return True, ""
        self.__commands[cmd_clear.name] = cmd_clear
        # connect command
        cmd_connect = redcat.command.Command("connect", self, "connect to a remote bind shell", self.__on_connect_completion)
        @cmd_connect.subcommand(
            "tcp",
            [
                redcat.command.argument("host", type=str, nargs=1, help="host to connect"),
                redcat.command.argument("port", type=int, nargs=1, help="port to connect"),
                redcat.command.argument("-m", "--platform", type=str, nargs=1, choices=[redcat.platform.LINUX, redcat.platform.WINDOWS], 
                    default=redcat.platform.LINUX, help="expected platform")
            ]
        )
        def connect_tcp(parent: Engine, platform: str, **kwargs) -> typing.Tuple[bool, str]:
            """
            connect to a tcp bind shell
            """
            res, error = parent.manager.connect(protocol=redcat.channel.ChannelProtocol.TCP, platform_name=platform, **kwargs)
            return res, error
        @cmd_connect.subcommand(
            "ssl",
            [
                redcat.command.argument("host", type=str, nargs=1, help="host to connect"),
                redcat.command.argument("port", type=int, nargs=1, help="port to connect"),
                redcat.command.argument("-m", "--platform", type=str, nargs=1, choices=[redcat.platform.LINUX, redcat.platform.WINDOWS], 
                    default=redcat.platform.LINUX, help="expected platform"),
                redcat.command.argument("--cert", type=str, nargs=1, help="path of the certificate of the ssl client"),
                redcat.command.argument("--key", type=str, nargs=1, help="path of the private key of the client's certificate"),
                redcat.command.argument("--password", type=str, nargs=1, help="password of the private key"),
                redcat.command.argument("--ca-cert", type=str, nargs=1, help="path of the CA certificate of the ssl bind shell")
            ]
        )
        def connect_ssl(parent: Engine, platform: str, **kwargs) -> typing.Tuple[bool, str]:
            """
            connect to a ssl bind shell
            """
            res, error = parent.manager.connect(protocol=redcat.channel.ChannelProtocol.SSL, platform_name=platform, **kwargs)
            return res, error
        self.__commands[cmd_connect.name] = cmd_connect
        # listen command
        cmd_listen = redcat.command.Command("listen", self, "listen for reverse shells", self.__on_listen_completion)
        @cmd_listen.subcommand(
            "tcp",
            [
                redcat.command.argument("-b", "--background", action="store_true", default=False, 
                    help="run the listener in the background to handle multiple connections"),
                redcat.command.argument("--host", type=str, nargs=1, default="::", help="host to bind"),
                redcat.command.argument("port", type=int, nargs=1, help="port to listen"),
                redcat.command.argument("-m", "--platform", type=str, nargs=1, choices=[redcat.platform.LINUX, redcat.platform.WINDOWS], 
                    default=redcat.platform.LINUX, help="expected platform")
            ]
        )
        def listen_tcp(parent: Engine, background: bool, platform: str, **kwargs) -> typing.Tuple[bool, str]:
            """
            listen for tcp reverse shells
            """
            res, error = parent.manager.listen(background=background, protocol=redcat.channel.ChannelProtocol.TCP, platform_name=platform, **kwargs)
            return res, error
        @cmd_listen.subcommand(
            "ssl",
            [
                redcat.command.argument("-b", "--background", action="store_true", default=False, 
                    help="run the listener in the background to handle multiple connections"),
                redcat.command.argument("--host", type=str, nargs=1, default="::", help="host to bind"),
                redcat.command.argument("port", type=int, nargs=1, help="port to listen"),
                redcat.command.argument("-m", "--platform", type=str, nargs=1, choices=[redcat.platform.LINUX, redcat.platform.WINDOWS], 
                    default=redcat.platform.LINUX, help="expected platform"),
                redcat.command.argument("cert", type=str, nargs=1, help="path of the certificate of the ssl listener"),
                redcat.command.argument("key", type=str, nargs=1, help="path of the private key of the listener's certificate"),
                redcat.command.argument("--password", type=str, nargs=1, help="password of the private key"),
                redcat.command.argument("--ca-cert", type=str, nargs=1, help="path of the CA certificate of the ssl reverse shell")
            ]
        )
        def listen_ssl(parent: Engine, background: bool, platform: str, **kwargs) -> typing.Tuple[bool, str]:
            """
            listen for ssl reverse shells
            """
            res, error = parent.manager.listen(background=background, protocol=redcat.channel.ChannelProtocol.SSL, platform_name=platform, **kwargs)
            return res, error
        self.__commands[cmd_listen.name] = cmd_listen
        # kill command
        cmd_kill = redcat.command.Command("kill", self, "kill the session or listener for a given id")
        @cmd_kill.command(
            [
                redcat.command.argument("type", type=str, nargs=1, choices=["session", "listener"], help="type of the object to kill"),
                redcat.command.argument("id", type=str, nargs=1, help="id of object to kill")
            ]
        )
        def kill(parent: Engine, **kwargs) -> typing.Tuple[bool, str]:
            """
            kill the session or listener for a given id
            """
            res, error = parent.manager.kill(**kwargs)
            return res, error
        self.__commands[cmd_kill.name] = cmd_kill
        # upgrade command
        cmd_upgrade = redcat.command.Command("upgrade", self, "upgrade a session with a pty using raindrop implant.")
        @cmd_upgrade.command(
            [
                redcat.command.argument("id", type=str, nargs="?", default="", help=("id of session to upgrade. "
                    "For Windows 10 / Windows Server 2019 (x64) version 1809 (build 10.0.17763) or higher"))
            ]
        )
        def upgrade(parent: Engine, id: str) -> typing.Tuple[bool, str]:
            """
            upgrade a session for a given id using raindrop implant. 
            Limitations: Windows 10 / Windows Server 2019 (x64) version 1809 (build 10.0.17763) or higher
            """
            return parent.manager.upgrade(id)
        self.__commands[cmd_upgrade.name] = cmd_upgrade
        # show command
        cmd_show = redcat.command.Command("show", self, "show available sessions or listeners")
        @cmd_show.command(
            [
                redcat.command.argument("type", type=str, nargs=1, choices=["sessions", "listeners"], help="type of the objects to display")
            ]
        )
        def show(parent: Engine, type: str) -> typing.Tuple[bool, str]:
            """
            show available sessions or listeners
            """
            res, error, serialization = self.manager.show(type)
            data = []
            if res:
                rows = serialization.split("\n")
                for row in rows:
                    if row:
                        data.append(row.split(","))
                if type == "sessions":
                    headers = ["ID", "User", "Remote host", "End point", "Protocol", "Platform"]
                    print("\n" + redcat.style.tabulate(headers, data) + "\n")
                    res = True
                elif type == "listeners":
                    headers = ["ID", "End point", "Protocol", "Expected platform"]
                    print("\n" + redcat.style.tabulate(headers, data) + "\n")
                    res = True
            return res, error
        self.__commands[cmd_show.name] = cmd_show
        # select session command
        cmd_session = redcat.command.Command("session", self, "select the session for a given id (none to unselect)")
        @cmd_session.command(
            [
                redcat.command.argument("id", type=str, nargs=1, help="id of the session")
            ]
        )
        def session(parent: Engine, **kwargs) -> typing.Tuple[bool, str]:
            """
            select the session for a given id (none to unselect)
            """
            res, error = parent.manager.select_session(**kwargs)
            return res, error
        self.__commands[cmd_session.name] = cmd_session
        # remote shell command
        cmd_shell = redcat.command.Command("shell", self, "spawn a remote shell for a given session id, use the selected session id if the id is not provided")
        @cmd_shell.command(
            [
                redcat.command.argument("id", type=str, nargs="?", help="id of session to spawn"),
            ]
        )
        def shell(parent: Engine, **kwargs) -> typing.Tuple[bool, str]:
            """
            spawn a remote shell for a given session id, use the selected session id if the id is not provided
            """
            res, error = parent.manager.remote_shell(**kwargs)
            return res, error
        self.__commands[cmd_shell.name] = cmd_shell
        # download command
        cmd_download = redcat.command.Command("download", self, 
            "download a file from the remote host of a given session", 
            self.__on_download_command_completion)
        @cmd_download.command(
            [
                redcat.command.argument("rfile", type=str, nargs=1, help="remote file to download"),
                redcat.command.argument("lfile", type=str, nargs=1, help="local path for the downloaded file"),
                redcat.command.argument("id", type=str, nargs="?", help="id of the session")
            ]
        )
        def download(parent: Engine, **kwargs) -> typing.Tuple[bool, str]:
            """
            download a file from the remote host for a given session
            use the selected session if no id is provided
            """
            return parent.manager.download(**kwargs)
        self.__commands[cmd_download.name] = cmd_download
        # upload commands
        cmd_upload = redcat.command.Command("upload", self, 
            "upload a file to the remote host of a given session (slow: not recommended for files bigger than a few mb)",
            self.__on_upload_command_completion)
        @cmd_upload.command(
            [
                redcat.command.argument("lfile", type=str, nargs=1, help="local file to upload"),
                redcat.command.argument("rfile", type=str, nargs=1, help="remote path for the uploaded file"),
                redcat.command.argument("id", type=str, nargs="?", help="id of the session")
            ]
        )
        def download(parent: Engine, **kwargs) -> typing.Tuple[bool, str]:
            """
            upload a file to the remote host of a given session
            use the selected session if no id is provided
            """
            return parent.manager.upload(**kwargs)
        self.__commands[cmd_upload.name] = cmd_upload
        # local command
        cmd_local = redcat.command.Command("local", self, "run a given command on the local system", self.__on_local_command_completion) 
        @cmd_local.command(
            [
                redcat.command.argument("args", nargs=argparse.REMAINDER)
            ]
        )
        def local(parent: Engine, args: typing.List[str]) -> typing.Tuple[bool, str]:
            """
            run a given command on the local system
            """
            cmd = ""
            if args:
                if isinstance(args, list):
                    cmd = " ".join(args).strip()
                else:
                    cmd = str(args).strip()
            if cmd:
                try:
                    subprocess.run(cmd, shell=True)
                except KeyboardInterrupt:
                    pass
            return True, ""
        self.__commands[cmd_local.name] = cmd_local
        # help command
        cmd_help = redcat.command.Command("help", self, "list commands or display the help for a given command")
        help_choices = ["help"] + [cmd_name for cmd_name in self.__commands.keys()]
        @cmd_help.command(
            [
                redcat.command.argument("name", type=str, nargs="?", choices=help_choices, help="name of the command to display")
            ]
        )
        def help(self, name: str = "") -> typing.Tuple[bool, str]:
            res = False
            error = redcat.style.bold(f"unknown command ") + redcat.style.bold(redcat.style.red(f"{name}"))
            if name:
                if name in self.__commands.keys():
                    self.__commands[name].parser.print_help()
                    res = True
                    error = ""
            else:
                headers = ["Command", "Description"]
                data = []
                for cmd in self.__commands.values():
                    data.append([cmd.name, cmd.description])
                print("\n" + redcat.style.tabulate(headers, data)+ "\n")
                res = True
                error = ""
            return res, error
        self.__commands[cmd_help.name] = cmd_help
        # for autocompletion
        readline.set_completer_delims(" \t\n;")
        readline.set_completer(self.__autocomplete)
        readline.parse_and_bind('tab: complete')
        self.__matches: typing.List[str] = []

    @property
    def manager(self) -> redcat.manager.Manager:
        return self.__manager

    @property
    def running(self) -> bool:
        return self.__running

    def __autocomplete(self, text: str, state: int) -> str:
        res = None
        if state == 0:
            matches = []
            buffer = readline.get_line_buffer()
            words = shlex.split(buffer, posix=False)
            if len(words) == 1:
                if buffer:
                    if text:
                        if text in self.__commands.keys():
                            if buffer[-1] != " ":
                                readline.insert_text(" ") 
                        else:
                            matches = [s + " " for s in self.__commands.keys() if text and s and s.startswith(text)]
                    else:
                        matches = self.__commands[words[0]].complete(buffer, "")
            elif len(words) > 1:
                cmd_name = words[0]
                matches = []
                if cmd_name in self.__commands.keys():
                    matches = self.__commands[cmd_name].complete(buffer, text)
            self.__matches = matches
        if state < len(self.__matches):
            res = self.__matches[state]
        return res

    def __complete_pie(self, name: str) -> typing.List[str]:
        matches = []
        dirs = os.getenv("PATH").split(":")
        for directory in dirs:
            if os.path.isdir(directory):
                if directory[-1] != "/":
                    directory += "/"
                matches += [item for item in os.listdir(directory) if item and
                          (os.path.isfile(f"{directory}{item}") or os.path.islink(f"{directory}{item}")) and
                          item.startswith(name)]
        matches = list(set(matches))
        return matches

    def __complete_local_path(self, path: str) -> typing.List[str]:
        dirname = os.path.dirname(path)
        basename = os.path.basename(path)
        items = []
        if not dirname:
            items = os.listdir(".")
        else:
            items = os.listdir(dirname)
        if dirname and dirname[-1] != "/":
            dirname += "/"
        for i in range(len(items)):
            item = f"{dirname}{items[i]}"
            if os.path.isdir(item):
                items[i] = item + "/"
            else:
                items[i] = item + " "
        matches = [item for item in items if item and item.startswith(path)]
        return matches

    def __on_connect_completion(self, buffer, text) -> typing.List[str]:
        matches = []
        if " --protocol ssl " in buffer:
            words = shlex.split(buffer)
            previous = words[-2] if text else words[-1]
            if previous in ["--cert", "--key", "--ca-cert"]:
                matches = [f"{s}" for s in self.__complete_local_path(text) if s]
        return matches

    def __on_listen_completion(self, buffer, text) -> typing.List[str]:
        matches = []
        if " --protocol ssl " in buffer:
            words = shlex.split(buffer)
            previous = words[-2] if text else words[-1]
            if previous in ["--cert", "--key", "--ca-cert"]:
                matches = [f"{s}" for s in self.__complete_local_path(text) if s]
        return matches

    def __on_upload_command_completion(self, buffer, text) -> typing.List[str]:
        matches = []
        words = shlex.split(buffer)
        if (len(words) == 1 and text == "") or (len(words) == 2 and text == words[1]):
            matches = [f"{s}" for s in self.__complete_local_path(text) if s]
        return matches

    def __on_download_command_completion(self, buffer, text) -> typing.List[str]:
        matches = []
        words = shlex.split(buffer)
        if (len(words) == 2 and text == "") or len(words) == 3 and text == words[2]:
            matches = [f"{s}" for s in self.__complete_local_path(text) if s]
        return matches

    def __on_local_command_completion(self, buffer, text) -> typing.List[str]: 
        matches = []
        if text:
            matches += [f"{s} " for s in self.__complete_pie(text) if s]
        matches += [f"{s}" for s in self.__complete_local_path(text) if s]
        return matches

    def __call(self, cmd: str) -> typing.Tuple[bool, str]:
        res = True
        error = ""
        if cmd:
            try:
                res = False
                name = shlex.split(cmd)[0]
                error = redcat.style.bold(f"unknown command ") + redcat.style.bold(redcat.style.red(f"{name}"))
                if name in self.__commands.keys():
                    res, error = self.__commands[name].exec(cmd)
            except ValueError as err:
                message = ": ".join([str(arg) for arg in err.args])
                error = redcat.style.bold(f"{message}: command ") + redcat.style.bold(redcat.style.red(f"{cmd}"))
        return res, error

    def __on_log_message(self, msg: str) -> None:
        log = f"{redcat.style.bold('[' + str(datetime.datetime.utcnow())[:-3] + ']')} " + msg
        if threading.current_thread() == threading.main_thread():
            print("\n\r" + log, end="\n\r")
        else:
            with self.__lock_logs:
                self.__logs.append(log)

    def __print_logs(self, logs: typing.List[str]) -> None:
        sys.stdout.write("\n\r\033[K")
        sys.stdout.flush()
        for log in logs:
            print(log, end="\n\r")
        sys.stdout.flush()

    def __logger(self) -> None:
        while self.__running:
            if self.__lock_logs.acquire(False):
                if self.__logs:
                    if self.__interruptible_section.is_interruptible:
                        self.__print_logs(self.__logs)
                        self.__logs.clear()
                self.__lock_logs.release()
            time.sleep(0.05)

    def __input(self, prompt: str) -> str:
        return input(prompt)

    def __get_cwd(self, max_length: int = 50) -> None:
        cwd = self.__cwd
        if len(self.__cwd) > max_length:
            directories = self.__cwd.split("/")
            if len(directories) > 2:
                cwd = f"/{directories[1]}/.."
                last_parts = ""
                for directory in reversed(directories):
                    if len(cwd) == 0:
                        cwd = directory
                    else:
                        if len(cwd) + len(directory) + len(last_parts) + 1 < max_length:
                            last_parts = "/" + directory + last_parts
                        else:
                            cwd += last_parts
                            break
        return cwd

    def __get_prompt(self) -> str:
        info = self.__manager.get_session_info()
        if not info:
            info = "None: @local"
        prompt = (
            f"{redcat.style.bg_green(redcat.style.bold(' ' + self.__user + ' ' * 4))}"
            f"{redcat.style.bg_white(redcat.style.bold(redcat.style.blue(' ' + self.__get_cwd() + ' ' * 4)))}" 
            f"{redcat.style.bg_cyan(redcat.style.bold(redcat.style.yellow(' ' + info + ' ' * 4)))}" 
            "\n"
            f"{redcat.style.bold(redcat.style.green(self.__name))}🐈 "
        )
        return prompt

    def run(self) -> None:
        """
        This is the Engine class main loop
        """
        # start manager
        self.__running = True
        self.__logger_thread = threading.Thread(target=self.__logger)
        self.__logger_thread.start()
        self.__manager.start()
        while self.__running:
            try:
                prompt = self.__get_prompt()
                cmd = self.__input(prompt)
                res, error = self.__call(cmd)
                if not res:
                    if not error:
                        error = "unspecified error"
                    self.__on_log_message(redcat.style.bold(redcat.style.red("[!] error: ")) + error)
            except EOFError:
                if self.__manager.selected_id:
                    self.__manager.remote_shell()
                else:
                    print()
            except KeyboardInterrupt:
                print()
            except redcat.utils.MainThreadInterrupt:
                pass
        # stop the manager
        self.__manager.stop()
        self.__logger_thread.join()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.__manager.clear()

