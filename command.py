import argparse
import typing
import shlex
import subprocess


class Command:

    def __init__(self, name: str, fct: typing.Callable, description = "") -> None:
        self.__name: str = name
        self.__fct: typing.Callable = fct
        self.__description: str = description
        self.__parser = argparse.ArgumentParser(prog=self.__name, description=description)

    @property
    def name(self) -> str:
        return self.__name

    @property
    def description(self) -> str:
        return self.__description

    @property
    def parser(self) -> argparse.ArgumentParser:
        return self.__parser

    @property
    def fct(self) -> typing.Callable:
        return self.__fct

    def exec(self, cmd_line: str) -> bool:
        res = False
        error = "invalid arguments"
        splits = shlex.split(cmd_line)
        name = splits[0]
        arguments = splits[1:]
        if name == self.__name:
            try:
                parsed_args = self.__parser.parse_args(arguments)
                kwargs = {k:v[0] if isinstance(v, list) and len(v) == 1 else v for k,v in parsed_args._get_kwargs() if v is not None}
                res, error = self.__fct(**kwargs)
            except SystemExit:
                res = True
                error = ""
        return res, error


class SystemCommand(Command):

    def __init__(self) -> None:
        super().__init__("system", self.__system, "run the command in a local shell")
        self.parser.add_argument("args", nargs=argparse.REMAINDER)

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
            subprocess.run(cmd, shell=True)
        return True, ""

