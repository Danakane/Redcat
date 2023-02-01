import argparse
import readline
import shlex
import typing
import subprocess
import sys
import os

import redcat.style
import redcat.command
import redcat.platform
import redcat.manager


class Engine:
    
    def __init__(self, name: str) -> None:
        self.__name: str = name
        self.__running: bool = False
        # sessions manager
        self.__manager: redcat.manager.Manager = redcat.manager.Manager()
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
                redcat.command.argument("port", type=int, nargs=1, help="port to connect to"),
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
                redcat.command.argument("port", type=int, nargs=1, help="port to connect to"),
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
                redcat.command.argument("port", type=int, nargs=1, help="port to connect to"),
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
                redcat.command.argument("port", type=int, nargs=1, help="port to connect to"),
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
        cmd_session = redcat.command.Command("session", self.__manager.select_session, "select the session for a given id (none to unselect)")
        @cmd_session.command(None)
        def session(parent: Engine, **kwargs) -> typing.Tuple[bool, str]:
            """
            select the session for a given id (none to unselect)
            """
            res, error = parent.manager.session(**kwargs)
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

    def __get_prompt(self) -> str:
        info = self.__manager.get_session_info()
        if not info:
            info = "None: @local"
        prompt = redcat.style.bold(redcat.style.yellow(f"[{info}]")) + " " + redcat.style.bold(redcat.style.green(self.__name)) + "🐈 "
        return prompt

    def run(self) -> None:
        self.__manager.start()
        self.__running = True
        while self.__running:
            try:
                prompt = self.__get_prompt()
                cmd =  input(prompt) 
                res, error = self.__call(cmd)
                if not res:
                    if not error:
                        error = "unspecified error"
                    print(redcat.style.bold(redcat.style.red("[!] error: ")) + error)
            except EOFError:
                if self.__manager.selected_id:
                    self.__manager.remote_shell()
            except KeyboardInterrupt:
                print()
            except SystemExit:
                print()
                break
        self.__manager.stop()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.__manager.clear()

