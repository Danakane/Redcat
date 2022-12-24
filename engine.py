import readline
import shlex
import typing
import subprocess
import signal

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
        cmd_connect.parser.add_argument("-m", "--platform", type=str, nargs=1, help="expected platform (linux or windows)")
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
        cmd_kill = command.Command("kill", self.__manager.kill, "kill the session or listener of the given id")
        cmd_kill.parser.add_argument("type", type=str, nargs=1, help="type of object to kill: session or listener")
        cmd_kill.parser.add_argument("id", type=str, nargs=1, help="id of object to kill")
        self.__commands[cmd_kill.name] = cmd_kill
        # select session command
        cmd_session = command.Command("session", self.__manager.select_session, "select the session of the given id (-1 to unselect)")
        cmd_session.parser.add_argument("id", type=str, nargs=1, help="id of session to select")
        self.__commands[cmd_session.name] = cmd_session
        # remote shell command
        cmd_shell = command.Command("shell", self.__manager.remote_shell, "spawn a remote shell for a given session id, use the selected session id if the id is not provided")
        cmd_shell.parser.add_argument("id", type=str, nargs="?", help="id of session to spawn")
        self.__commands[cmd_shell.name] = cmd_shell
        # system command
        cmd_local = command.SystemCommand()
        self.__commands[cmd_local.name] = cmd_local

    def __call(self, cmd: str) -> typing.Tuple[bool, str]:
        res = True
        error = ""
        if cmd:
            name = shlex.split(cmd)[0]
            res = False
            error = f"unkown command {name}"
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
        error = f"unknown command {name}"
        if name:
            if name in self.__commands.keys():
                self.__commands[name].parser.print_help()
                res = True
                error = ""
                print()
        else:
            for cmd in self.__commands.values():
                print(f"{cmd.name}: {cmd.description}")
                res = True
                error = ""
            print()
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



    # -------------------------------------------------------------------------------------------#
    #                                       Public section                                       #
    # -------------------------------------------------------------------------------------------#
    def run(self) -> None:
        self.__running = True
        while self.__running:
            try:
                cmd =  input("(local) pwncat$ ")
                res, error = self.__call(cmd)
                if not res:
                    if not error:
                        error = "unspecified error"
                    print(f"[!] error: {error}")
            except EOFError:
                print()
                if self.__manager.selected_id:
                    self.__manager.remote_shell()
            except KeyboardInterrupt:
                print()
            except SystemExit:
                print()
                break

