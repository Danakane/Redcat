import argparse
import readline
import shlex
import typing
import subprocess
import sys
import os

import redcat.style
import redcat.command
import redcat.manager

class Engine:

    # -------------------------------------------------------------------------------------------#
    #                                       Private section                                      #
    # -------------------------------------------------------------------------------------------#
    
    def __init__(self, name: str) -> None:
        self.__name: str = name
        self.__running: bool = False
        # sessions managerlis
        self.__manager: redcat.manager.Manager = redcat.manager.Manager()
        # commands
        self.__commands: typing.Dict[str, redcat.command.Command] = {}
        # exit command
        cmd_exit = redcat.command.Command("exit", self.__exit, f"exit {self.__name}")
        self.__commands[cmd_exit.name] = cmd_exit
        # clear command
        cmd_clear = redcat.command.Command("clear", self.__clear, "clear the screen")
        self.__commands[cmd_clear.name] = cmd_clear
        # connect command
        cmd_connect = redcat.command.Command("connect", self.__connect, "connect to a remote bind shell")
        cmd_connect.add_argument("addr", type=str, nargs=1, help="address to connect")
        cmd_connect.add_argument("port", type=int, nargs=1, help="port to connect to")
        cmd_connect.add_argument("-m", "--platform", type=str, nargs=1, choices=["linux", "windows"], help="expected platform (linux or windows)")
        self.__commands[cmd_connect.name] = cmd_connect
        # listen command
        cmd_listen = redcat.command.Command("listen", self.__listen, "listen for a reverse shell")
        cmd_listen.add_argument("addr", type=str, nargs="?", help="address to bind")
        cmd_listen.add_argument("port", type=int, nargs=1, help="port to bind on")
        cmd_listen.add_argument("-m", "--platform", type=str, nargs=1, choices=["linux", "windows"], help="expected platform (linux or windows)")
        cmd_listen.add_argument("-b", "--background", action="store_true", help="execute the listener in the background to handle multiple connections")
        self.__commands[cmd_listen.name] = cmd_listen
        # kill command
        cmd_kill = redcat.command.Command("kill", self.__manager.kill, "kill the session or listener for a given id")
        cmd_kill.add_argument("type", type=str, nargs=1, choices=["session", "listener"], help="type of object to kill")
        cmd_kill.parser.add_argument("id", type=str, nargs=1, help="id of object to kill")
        self.__commands[cmd_kill.name] = cmd_kill
        # show command
        cmd_show = redcat.command.Command("show", self.__show, "show available sessions or listeners")
        cmd_show.add_argument("type", type=str, nargs=1, choices=["sessions", "listeners"], help="the objects to display")
        self.__commands[cmd_show.name] = cmd_show
        # select session command
        cmd_session = redcat.command.Command("session", self.__manager.select_session, "select the session for a given id (none to unselect)")
        cmd_session.parser.add_argument("id", type=str, nargs=1, help="id of session to select")
        self.__commands[cmd_session.name] = cmd_session
        # remote shell command
        cmd_shell = redcat.command.Command("shell", self.__manager.remote_shell, "spawn a remote shell for a given session id, use the selected session id if the id is not provided")
        cmd_shell.parser.add_argument("id", type=str, nargs="?", help="id of session to spawn")
        self.__commands[cmd_shell.name] = cmd_shell
        # download command
        cmd_download = redcat.command.Command("download", self.__manager.download, "download a file from remote host for a given session id", self.__on_download_command_completion)
        cmd_download.parser.add_argument("rfile", type=str, nargs=1, help="remote file to download")
        cmd_download.parser.add_argument("lfile", type=str, nargs=1, help="local path for the downloaded file")
        cmd_download.parser.add_argument("id", type=str, nargs="?", help="id of the session")
        self.__commands[cmd_download.name] = cmd_download
        # upload commands
        cmd_upload = redcat.command.Command("upload", self.__manager.upload, "upload a file from remote host for a given session id (extremely slow, not recommended for files bigger than a few 100kb)",
                                     self.__on_upload_command_completion)
        cmd_upload.parser.add_argument("lfile", type=str, nargs=1, help="local file to upload")
        cmd_upload.parser.add_argument("rfile", type=str, nargs=1, help="remote path for the uploaded file")
        cmd_upload.parser.add_argument("id", type=str, nargs="?", help="id of the session")
        self.__commands[cmd_upload.name] = cmd_upload
        # local command
        cmd_local = redcat.command.Command("local", self.__system, "run the command in a local shell", self.__on_local_command_completion) 
        cmd_local.add_argument("args", nargs=argparse.REMAINDER)
        self.__commands[cmd_local.name] = cmd_local
        # help command
        cmd_help = redcat.command.Command("help", self.__help, "list commands or display the help for a given command")
        help_choices = ["help"] + [cmd_name for cmd_name in self.__commands.keys()]
        cmd_help.add_argument("name", type=str, nargs="?", choices=help_choices, help="name of the command to display")
        self.__commands[cmd_help.name] = cmd_help
        # for autocompletion
        readline.set_completer_delims(" \t\n;")
        readline.set_completer(self.__autocomplete)
        readline.parse_and_bind('tab: complete')
        self.__matches: typing.List[str] = []

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
            name = shlex.split(cmd)[0]
            res = False
            error = redcat.style.bold(f"unknown command ") + redcat.style.bold(redcat.style.red(f"{name}"))
            if name in self.__commands.keys():
                res, error = self.__commands[name].exec(cmd)
        return res, error

    def __system(self, args):
        cmd = ""
        if args:
            if isinstance(args, list) and len(args) > 1:
                cmd = " ".join(args)
            elif isinstance(args, list) and len(args) == 1:
                cmd = args[0]
            else:
                cmd = args
        cmd = cmd.strip()
        if cmd:
            try:
                subprocess.run(cmd, shell=True)
            except KeyboardInterrupt:
                pass
        return True, ""

    def __exit(self) -> typing.Tuple[bool, str]:
        self.__running = False
        self.__manager.clear()
        return True, ""

    def __clear(self) -> typing.Tuple[bool, str]:     
        subprocess.run("clear")
        return True, ""

    def __help(self, name: str = "") -> typing.Tuple[bool, str]:
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

    def __connect(self, addr: str, port: int, platform: str = "") -> typing.Tuple[bool, str]:
        res = True
        error = ""
        if platform:
            res, error = self.__manager.connect(addr, port, platform)
        else:
            res, error = self.__manager.connect(addr, port)
        return res, error

    def __listen(self, port: int, addr: str = "", platform: str = "", background: bool = False) -> typing.Tuple[bool, str]:
        res = True
        error = ""
        if platform:
            res, error = self.__manager.listen(addr, port, platform, background)
        else:
            res, error = self.__manager.listen(addr, port, background=background)
        return res, error

    def __show(self, type: str) -> typing.Tuple[bool, str]:
        res, error, serialization = self.__manager.show(type)
        data = []
        if res:
            rows = serialization.split("\n")
            for row in rows:
                if row:
                    data.append(row.split(","))
            if type == "sessions":
                headers = ["ID", "User", "Remote host", "End point", "Platform"]
                print("\n" + redcat.style.tabulate(headers, data) + "\n")
                res = True
            elif type == "listeners":
                headers = ["ID", "End point", "Expected platform"]
                print("\n" + redcat.style.tabulate(headers, data) + "\n")
                res = True
        return res, error

    def __get_prompt(self) -> str:
        info = self.__manager.get_session_info()
        if not info:
            info = "None: @local"
        prompt = redcat.style.bold(redcat.style.yellow(f"[{info}]")) + " " + redcat.style.bold(redcat.style.green(self.__name)) + "🐈 "
        return prompt

    # -------------------------------------------------------------------------------------------#
    #                                       Public section                                       #
    # -------------------------------------------------------------------------------------------#

    @property
    def manager(self) -> redcat.manager.Manager:
        return self.__manager

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

