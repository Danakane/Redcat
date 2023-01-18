import argparse
import typing
import shlex
import subprocess


class Command:

    def __init__(self, name: str, fct: typing.Callable, description, callback: typing.Callable = None) -> None:
        self.__name: str = name
        self.__fct: typing.Callable = fct
        self.__description: str = description
        self.__completion_data: typing.Dict[typing.List[str], typing.List[str]] = {
            ("-h", "--help"): []
        }
        self.__completion_callback: typing.Callable = callback
        self.__parser: argparse.ArgumentParser = argparse.ArgumentParser(prog=self.__name, description=description)

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
                res, error = self.__fct(**kwargs)
            except SystemExit:
                res = True
                error = ""
        return res, error
    

