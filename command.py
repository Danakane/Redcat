import copy
import typing
import shlex


class Argument:

    def __init__(self, arg_name: str, has_value: bool, optional: bool, value: str = None, substitutes: typing.List[str] = None) -> None: 
        self.__arg_name: str = arg_name
        self.__has_value: bool = has_value
        self.__optional: bool = optional
        self.__value: typing.Optional[str] = value
        self.__present: bool = False
        self.__substitutes: typing.Optional[typing.List[str]] = substitutes

    def clone(self):
        return copy.deepcopy(self)


class Command:

    def __init__(self, cmd_name: str, nargs_list: typing.List[Argument] = None,
                 nb_positionals: int = 0, completion_list: typing.List[str] = None) -> None:
        self.__cmd_name: str = cmdname.lower()
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

    def __findarg(self, argname) -> typing.Optional[Argument]:
        arg = None
        try:
            arg = self.__kwargs[argname.lower()]
        except KeyError:
            pass
        return arg

    def __validate(self) -> bool:
        pass


    def parse(self, cmdline) -> typing.Tuple[typing.List[str], typing.Dict[str, str]]:
        wordslist: typing.List[str] = shlex.split(cmdline, posix=False)
        # remove 1st element since it's the command name
        wordlist = wordlist[1:]
        i: int = 0
        while i < len(wordlist):
            arg = self.__findarg(wordslist[i])
            if arg is not None:
                arg.__present = True
                if arg.__hasvalue:
                    # it's an argument name
                    i += 1
                    if i < len(wordslist):
                        arg.__value = wordslist[i]
                    else:
                        # Wrong number of arguments, raise error
                        raise exception.ErrorException("Wrong number of " +
                                                       "arguments for the command " +
                                                       self.__cmdname__)
            else:
                # it's not an argument name
                # maybe an positional argument
                if len(self.__args__) < self.__nbpositionals__:
                    self.__args__.append(wordslist[i])
                else:
                    # Not even an cmd input, just exit
                    raise exception.ErrorException("Unexpected argument " +
                                                   wordslist[i] + " for the command " +
                                                   self.__cmdname__)
            i += 1  # next step
        self.__validate__()
        args: typing.List[str] = self.__args__
        kwargs: typing.Dict[str, str] = {}
        # parse the named arguments
        for key, arg in self.__kwargs__.items():
            if arg.__present__:
                if arg.__value__:
                    kwargs[key] = arg.__value__
                else:
                    kwargs[key] = "true"
        return args, kwargs

    def clone(self):
        # return a deep copy of the command object
        return copy.deepcopy(self)

    
