import readline
import shlex
import typing
import subprocess
import signal

import style
import command
import manager

class Engine:

    # -------------------------------------------------------------------------------------------#
    #                                       Private section                                      #
    # -------------------------------------------------------------------------------------------#
    
    def __init__(self) -> None:
        self.__running: bool = False
        # sessions manager
        self.__manager: manager.Manager = manager.Manager()
        # commands
        self.__commands: typing.Dict[str, command.Command] = {}
        # exit command
        cmd_exit = command.Command("exit", self.__exit, "exit pwncat")
        self.__commands[cmd_exit.name] = cmd_exit
        # clear command
        cmd_clear = command.Command("clear", self.__clear, "clear the screen")
        self.__commands[cmd_clear.name] = cmd_clear
        # help command
        cmd_help = command.Command("help", self.__help, "help")
        cmd_help.parser.add_argument("name", type=str, nargs="?", help="name of the command to display")
        self.__commands[cmd_help.name] = cmd_help
        # connect command
        cmd_connect = command.Command("connect", self.__connect, "connect to a remote bind shell")
        cmd_connect.parser.add_argument("addr", type=str, nargs=1, help="address to connect")
        cmd_connect.parser.add_argument("port", type=int, nargs=1, help="port to connect to")
        cmd_connect.parser.add_argument("-m", "--platform-name", type=str, nargs=1, help="expected platform (linux or windows)")
        cmd_connect.parser.add_argument("-b", "--background", action="store_true", help="execute the action in background")
        self.__commands[cmd_connect.name] = cmd_connect
        # listen command
        cmd_listen = command.Command("listen", self.__listen, "listen for a reverse shell")
        cmd_listen.parser.add_argument("addr", type=str, nargs="?", help="address to bind")
        cmd_listen.parser.add_argument("port", type=int, nargs=1, help="port to bind on")
        cmd_listen.parser.add_argument("-m", "--platform", type=str, nargs=1, help="expected platform (linux or windows)")
        cmd_listen.parser.add_argument("-b", "--background", action="store_true", help="execute the action in background")
        self.__commands[cmd_listen.name] = cmd_listen
        # kill command
        cmd_kill = command.Command("kill", self.__manager.kill, "kill the session or listener for a given id")
        cmd_kill.parser.add_argument("type", type=str, nargs=1, help="type of object to kill: session or listener")
        cmd_kill.parser.add_argument("id", type=str, nargs=1, help="id of object to kill")
        self.__commands[cmd_kill.name] = cmd_kill
        # show command
        cmd_show = command.Command("show", self.__show, "show available sessions or listeners")
        cmd_show.parser.add_argument("type", type=str, nargs=1, help="type of the objects to display: sessions or listeners")
        self.__commands[cmd_show.name] = cmd_show
        # select session command
        cmd_session = command.Command("session", self.__manager.select_session, "select the session for a given id (-1 to unselect)")
        cmd_session.parser.add_argument("id", type=str, nargs=1, help="id of session to select")
        self.__commands[cmd_session.name] = cmd_session
        # remote shell command
        cmd_shell = command.Command("shell", self.__manager.remote_shell, "spawn a remote shell for a given session id, use the selected session id if the id is not provided")
        cmd_shell.parser.add_argument("id", type=str, nargs="?", help="id of session to spawn")
        self.__commands[cmd_shell.name] = cmd_shell
        # download command
        cmd_download = command.Command("download", self.__manager.download, "download a file from remote host for a given session id")
        cmd_download.parser.add_argument("rfile", type=str, nargs=1, help="remote file to download")
        cmd_download.parser.add_argument("lfile", type=str, nargs=1, help="local path for the downloaded file")
        cmd_download.parser.add_argument("id", type=str, nargs="?", help="id of the session")
        self.__commands[cmd_download.name] = cmd_download
        # upload commands
        cmd_upload = command.Command("upload", self.__manager.upload, "upload a file from remote host for a given session id (extremely slow, not recommended for files bigger than a few 10kb)")
        cmd_upload.parser.add_argument("lfile", type=str, nargs=1, help="local file to upload")
        cmd_upload.parser.add_argument("rfile", type=str, nargs=1, help="remote path for the uploaded file")
        cmd_upload.parser.add_argument("id", type=str, nargs="?", help="id of the session")
        self.__commands[cmd_upload.name] = cmd_upload
        # system command
        cmd_local = command.SystemCommand("local")
        self.__commands[cmd_local.name] = cmd_local
        # for autocompletion
        self.__keywords = sorted(self.__commands.keys())
        readline.set_completer_delims("\t\n;")
        readline.set_completer(self.__autocomplete)
        readline.parse_and_bind('tab: complete')

    def __autocomplete(self, text: str, state: int) -> str:
        res = None
        buffer = readline.get_line_buffer()
        words = shlex.split(buffer)
        if len(words) == 1:
            matches = [s for s in self.__keywords if s and s.startswith(buffer)]
            # return match indexed by state
            if state < len(matches):
                res = matches[state]
        elif len(words) == 2:
            word = words[1]
            matches = []
            if words[0] == "help":
                matches = [s for s in self.__keywords if s and s.startswith(word)]
            elif words[0] == "show":
                matches = [s for s in ["sessions", "listeners"] if s and s.startswith(word)]
            elif words[0] == "kill":
                matches = [s for s in ["session", "listener"] if s and s.startswith(word)]
            if state < len(matches):
                res = f"{words[0]} {matches[state]}"
        return res

    def __call(self, cmd: str) -> typing.Tuple[bool, str]:
        res = True
        error = ""
        if cmd:
            name = shlex.split(cmd)[0]
            res = False
            error = style.bold(f"unknown command ") + style.bold(style.red(f"{name}"))
            if name in self.__commands.keys():
                res, error = self.__commands[name].exec(cmd)
        return res, error

    def __exit(self) -> typing.Tuple[bool, str]:
        self.__running = False
        self.__manager.clear()
        return True, ""

    def __clear(self) -> typing.Tuple[bool, str]:     
        subprocess.run("clear")
        return True, ""

    def __help(self, name: str = "") -> typing.Tuple[bool, str]:
        res = False
        error = style.bold(f"unknown command ") + style.bold(style.red(f"{name}"))
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
            print("\n" + style.tabulate(headers, data)+ "\n")
            res = True
            error = ""
        return res, error

    def __connect(self, addr: str, port: int, platform: str = "", background: bool = False) -> typing.Tuple[bool, str]:
        res = True
        error = ""
        if platform:
            res, error = self.__manager.create_session(addr, port, platform)
        else:
            res, error = self.__manager.create_session(addr, port)
        return res, error

    def __listen(self, port: int, addr: str = "", platform: str = "", background: bool = False) -> typing.Tuple[bool, str]:
        res = True
        error = ""
        if platform:
            res, error = self.__manager.create_session(addr, port, platform, True, background)
        else:
            res, error = self.__manager.create_session(addr, port, bind=True, background=background)
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
                headers = ["ID", "User", "Remote host", "Platform"]
                print("\n" + style.tabulate(headers, data) + "\n")
                res = True
            elif type == "listeners":
                headers = ["ID", "End point", "Expected platform"]
                print("\n" + style.tabulate(headers, data) + "\n")
                res = True
        return res, error

    def __get_prompt(self) -> str:
        host = self.__manager.get_session_remote()
        if not host:
            host = "@localhost"
        prompt = style.bold(style.yellow(f"[{host}]")) + " " + style.bold(style.green("pwncat")) + "🐈 "
        return prompt

    # -------------------------------------------------------------------------------------------#
    #                                       Public section                                       #
    # -------------------------------------------------------------------------------------------#

    @property
    def manager(self) -> manager.Manager:
        return self.__manager

    def run(self) -> None:
        self.__running = True
        while self.__running:
            try:
                prompt = self.__get_prompt()
                cmd =  input(prompt) 
                res, error = self.__call(cmd)
                if not res:
                    if not error:
                        error = "unspecified error"
                    print(style.bold(style.red("[!] error:")) + f" {error}")
            except EOFError:
                print()
                if self.__manager.selected_id:
                    self.__manager.remote_shell()
            except KeyboardInterrupt:
                print()
            except SystemExit:
                print()
                break

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.__manager.clear()

