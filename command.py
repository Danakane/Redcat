import copy
import typing
import shlex
import subprocess
import os

class Argument:

    def __init__(self, arg_name: str, has_value: bool, optional: bool, value: str = None, substitutes: typing.List[str] = None) -> None: 
        self.__arg_name: str = arg_name
        self.__has_value: bool = has_value
        self.__optional: bool = optional
        self.__value: typing.Optional[str] = value
        self.__present: bool = False
        self.__substitutes: typing.Optional[typing.List[str]] = substitutes

    @property
    def arg_name(self) -> str:
        return self.__arg_name
    
    @property
    def has_value(self) -> bool:
        return self.__has_value

    @property
    def optional(self) -> bool:
        return self.__optional

    @property
    def value(self) -> typing.Optional[str]:
        return self.__value
    @value.setter
    def value(self, value: str) -> None:
        self.__value = value

    @property
    def present(self) -> bool:
        return self.__present
    @present.setter
    def present(self, present: bool) -> None:
        self.__present = present

    @property
    def substitutes(self) -> typing.Optional[typing.List[str]]:
        return self.__substitutes

    def clone(self):
        return copy.deepcopy(self)


class CommandParser:

    def __init__(self, cmd_name: str, nargs_list: typing.List[Argument] = None,
                 nb_positionals: int = 0, completion_list: typing.List[str] = None) -> None:
        self.__cmd_name: str = cmd_name
        self.__args: typing.List[str] = []
        self.__nb_positionals: int = nb_positionals
        self.__kwargs: typing.Dict[str, Argument] = {}
        if nargs_list is not None:
            for narg in nargs_list:
                self.__kwargs[narg.__argname] = narg.clone()
        self.__completion_list: typing.List[str] = list(self.__kwargs.keys())
        if not completion_list:
            completion_list: typing.List[str] = []
        self.__completion_list += completion_list

    def __findarg(self, arg_name) -> typing.Optional[Argument]:
        arg = None
        if arg_name in self.__kwargs.keys():
            arg = self.__kwargs[arg_name]
        return arg

    def __validate(self) -> bool:
        res = True
        # check if all positionals arguments are present
        if len(self.__args) != self.__nb_positionals:
            res = False
        # check if all mandatory named arguments are present
        for arg_name, arg in self.__kwargs.items():
            # check only if the argument is mandatory
            if not arg.__optional:
                if arg.__present:
                    continue
                if arg.substitutes:
                    bfound: bool = False
                    for substitute in arg.substitutes:
                        sarg = self.__findarg(substitute)
                        if sarg and sarg.present:
                            bfound = True
                            break
                    if not bfound:
                        res = False
                else:
                    res = False
        return res

    def parse(self, cmd) -> typing.Tuple[bool, typing.List[str], typing.Dict[str, str]]:
        res = True
        wordlist = shlex.split(cmd, posix=False)
        # remove 1st element since it's the command name
        wordlist = wordlist[1:]
        i = 0
        while i < len(wordlist):
            arg = self.__findarg(wordslist[i])
            if arg is not None:
                arg.present = True
                if arg.has_value:
                    # it's an argument name
                    i += 1
                    if i < len(wordslist):
                        arg.value = wordlist[i]
                    else:
                        # Wrong number of arguments
                        res = False
            else:
                # it's not an argument name
                # maybe an positional argument
                if len(self.__args) < self.__nb_positionals:
                    self.__args.append(wordlist[i])
                else:
                    # Not even an cmd input, just exit
                    res = False   
            i += 1  # next step
        args = None
        kwargs = None
        if res:
            res = self.__validate()
            if res:
                args = self.__args
                kwargs = {}
                # parse the named arguments
                for key, arg in self.__kwargs.items():
                    if arg.present:
                        if arg.value:
                            kwargs[key] = arg.value
                        else:
                            kwargs[key] = "true"
        return res, args, kwargs

    def clone(self):
        # return a deep copy of the command object
        return copy.deepcopy(self)


class Command:
    
    def __init__(self, parser: CommandParser, fct: typing.Callable) -> None:
        self.__parser: CommandParser = parser
        self.__fct: typing.Callable = fct

    @property
    def parser(self) -> CommandParser:
        return self.__parser

    @property
    def fct(self) -> typing.Callable:
        return self.__fct

    def exec(self, cmd_line) -> bool:
        parser = self.__parser.clone()
        res, args, kwargs = parser.parse(cmd_line)
        if res:
            self.__fct(*args, **kwargs)
        return res


#r --------------------------------------------------------------------------------------------------#
#                                   Framework command line engine                                   #
# --------------------------------------------------------------------------------------------------#
class Engine:
    # -------------------------------------------------------------------------------------------#
    #                                       Private section                                      #
    # -------------------------------------------------------------------------------------------#
    def __init__(self) -> None:
        self.__running: bool = False
        cmd_exit_parser: CommandParser = CommandParser(cmd_name="exit")
        cmd_clear_parser: CommandParser = CommandParser(cmd_name="clear")
        self.__dictcmd: typing.Dict[str, CommandSlot] = {
            "exit": Command(parser=cmd_exit_parser, fct=self.__exit),
            "clear": Command(parser=cmd_clear_parser, fct=self.__clear)
        }

    def __call(self, cmd_line) -> None:
        res = False
        cmd_name: str = shlex.split(cmd_line)[0]  # trigger exception if empty cmdline
        if cmd_name == "local":
            self.__callsystem(cmd_line[len("local "):])
            res = True
        elif cmd_name in self.__dictcmd.keys():
            res = self.__dictcmd[cmd_name].exec(cmd_line)
        return res

    def __callsystem(self, cmd_line: str) -> None:
        subprocess.run(cmd_line, shell=True, executable=os.environ["SHELL"])

    def __exit(self) -> bool:
        self.__running = False
        return True

    def __clear(self) -> bool:     
        subprocess.run("clear", executable=os.environ["SHELL"])
        return True

    # -------------------------------------------------------------------------------------------#
    #                                       Public section                                       #
    # -------------------------------------------------------------------------------------------#
    def run(self) -> None:
        self.__running = True
        while self.__running:
            try:
                cmd_line =  input("(local) pwncat$ ")
                res = self.__call(cmd_line=cmd_line)
                if not res:
                    print("Error: command unknown")
            except KeyboardInterrupt:
                print()
            except SystemExit:
                print()
                break
        self.stop()

    def stop(self) -> None:
        pass

