import argparse
import typing
import shlex
import subprocess


def argument(*name_or_flags, **kwargs):
    """Convenience function to properly format arguments to pass to the
    command and subcommand decorators.
    """
    return (list(name_or_flags), kwargs)


class Command:

    SUBCOMMAND: str = "subcommand"
    FUNC: str = "func"

    def __init__(self, name: str, parent: typing.Any, description: str, callback: typing.Callable = None) -> None:
        self.__name: str = name
        self.__parent: typing.Any = parent
        self.__description: str = description
        self.__completion_data: typing.Dict[typing.List[str], typing.List[str]] = {
            ("-h", "--help"): []
        }
        self.__completion_callback: typing.Callable = callback
        self.__func: typing.Callable = None
        self.__parser: argparse.ArgumentParser = argparse.ArgumentParser(prog=self.__name, description=description)
        self.__subparsers: argparse._SubParsersAction = None

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
    def func(self) -> typing.Callable:
        return self.__func

    def add_argument(self, *args: typing.Tuple[str, ...], **kwargs: typing.Dict[str, typing.Any]) -> None:
        if args[0].startswith("-"):
            # it's a named argument -> we add it to the completion list
            self.__completion_data[args] = []
            if "choices" in kwargs.keys():
                for choice in kwargs["choices"]:
                    self.__completion_data[args].append((choice))
        else:
            # it's positional argument
            if "choices" in kwargs.keys():
                self.__completion_data[tuple(kwargs["choices"])] = []
        self.__parser.add_argument(*args, **kwargs)

    def __get_completion_candidates(self, key: str = None, buffer: str = None) -> typing.List[str]:
        candidates = []
        if not key:
            for args in self.__completion_data.keys():
                if buffer:
                    already_in_buffer = False
                    for arg in args:
                        if f" {arg} " in buffer:
                            already_in_buffer = True
                    if not already_in_buffer:
                        candidates += list(args)
                else:
                    candidates += list(args)
        else:
            for args in self.__completion_data.keys():
                if key in args:
                    candidates = self.__completion_data[args]
                    break
        return candidates

    def complete(self, buffer, text) -> typing.List[str]: 
        matches = []
        words = shlex.split(buffer, posix=False)
        if len(words) == 1:
            if self.__completion_callback:
                matches += self.__completion_callback(buffer, text)
            if not matches:
                matches += [f"{s} " for s in self.__get_completion_candidates() if s]
        elif len(words) == 2:
            if self.__completion_callback:
                matches += self.__completion_callback(buffer, text)
            if not matches:
                if text:
                    matches += [f"{s} " for s in self.__get_completion_candidates() if s and s.startswith(text)]
                else:
                    previous = words[-1]
                    matches += [f"{s} " for s in self.__get_completion_candidates(previous) if s and s.startswith(text)]
                if not matches:
                    matches += [f"{s} " for s in self.__get_completion_candidates(buffer=buffer) if s and s.startswith(text)] 
        else:
            if self.__completion_callback:
                matches += self.__completion_callback(buffer, text)
            if not matches:
                previous = ""
                if text:
                    previous = words[-2]
                else:
                    previous = words[-1]
                if previous in self.__get_completion_candidates():
                    matches += [f"{s} " for s in self.__get_completion_candidates(previous) if s and s.startswith(text)]
                if not matches:
                    matches += [f"{s} " for s in self.__get_completion_candidates(buffer=buffer) if s and s.startswith(text)] 
        return matches

    def exec(self, cmd_line: str) -> bool:
        res = False
        error = "invalid arguments"
        splits = shlex.split(cmd_line, posix=False)
        name = splits[0]
        arguments = splits[1:]
        if name == self.__name:
            try:
                parsed_args = self.__parser.parse_args(arguments)
                kwargs = {k:v[0] if isinstance(v, list) and len(v) == 1 else v for k,v in parsed_args._get_kwargs() if v is not None}
                if Command.SUBCOMMAND in kwargs and kwargs[Command.SUBCOMMAND]:
                    del kwargs[Command.SUBCOMMAND]
                    del kwargs["func"]
                    res, error = parsed_args.func(self.__parent, **kwargs)
                else:
                    if Command.SUBCOMMAND in kwargs.keys():
                        del kwargs[Command.SUBCOMMAND]
                    if Command.FUNC in kwargs.keys():
                        del kwargs[Command.FUNC]
                    res, error = self.__func(self.__parent, **kwargs)
            except SystemExit:
                res = True
                error = ""
        return res, error

    def command(self, args: typing.List[typing.Any]) -> typing.Callable:
        """
        Decorator to define a new command in a sanity-preserving way.
        """
        def decorator(func: typing.Callable) -> typing.Callable:
            if args:
                for arg in args:
                    self.add_argument(*arg[0], **arg[1])
            self.__func = func
        return decorator

    def subcommand(self, name: str, args: typing.List[typing.Any]=None) -> typing.Callable:
        """
        Decorator to define a new subcommand in a sanity-preserving way.
        The function will be stored in the ``func`` variable when the parser
        parses arguments so that it can be called directly
        """
        def decorator(func) -> None:
            if not self.__subparsers:
                self.__subparsers = self.__parser.add_subparsers(dest=Command.SUBCOMMAND)
            parser = self.__subparsers.add_parser(name, description=func.__doc__)
            if args:
                for arg in args:
                    parser.add_argument(*arg[0], **arg[1])
            parser.set_defaults(func=func)
        return decorator
    

