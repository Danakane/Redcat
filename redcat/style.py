import typing

PURPLE = '\033[95m'
CYAN = '\033[96m'
DARKCYAN = '\033[36m'
BLUE = '\033[94m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
END = '\033[0m'
BOLD = '\033[1m'
UNDERLINE = '\033[4m'
BOLDEND = '\033[22m'
UNDERLINEEND = '\033[24m'

def purple(string: str) -> str:
    return PURPLE + string + END

def cyan(string: str) -> str:
    return CYAN + string + END

def darkcyan(string: str) -> str:
    return DARKCYAN + string + END

def blue(string: str) -> str:
    return BLUE + string + END

def green(string: str) -> str:
    return GREEN + string + END

def yellow(string: str) -> str:
    return YELLOW + string + END

def red(string: str) -> str:
    return RED + string + END

def bold(string) -> str:
    return BOLD + string + BOLDEND

def underline(string) -> str:
    return UNDERLINE + string + UNDERLINEEND

def tabulate(headers: typing.List[str], data: typing.List[typing.List[str]]) -> str:
    columns_size = []
    table = [headers] + data
    if table:
        for j in range(len(table[0])):
            column = [row[j] for row in table if row]
            columns_size.append(len(max(column, key=len)) + 5)
    row_format = ""
    for column_size in columns_size:
        row_format += ("{" + f":<{column_size}" + "}")
    limits = []
    str_rows = []
    for row in table:
        if row:
            str_row = " " * 4 + row_format.format(*row)
            str_rows.append(str_row)
    max_row_length = len(max(str_rows, key=len)) - 2
    str_rows = [str_rows[0], " " * 2 + "─" * max_row_length] + str_rows[1:]
    str_table = "\n".join(str_rows)
    return str_table

# https://stackoverflow.com/questions/3173320/text-progress-bar-in-terminal-with-block-characters?noredirect=1&lq=1
def print_progress_bar (iteration, total, prefix = '', suffix = '', decimals = 1, length = 100, fill = '█', print_end = "\r"):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
        printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end = print_end)
    # Print New Line on Complete
    if iteration == total: 
        print()
