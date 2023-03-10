import typing
import re


PURPLE = "\001\033[95m\002"
CYAN = "\001\033[96m\002"
DARKCYAN = "\001\033[36m\002"
BLUE = "\001\033[94m\002"
GREEN = "\001\033[92m\002"
YELLOW = "\001\033[93m\002"
RED = "\001\033[91m\002"

BG_BLACK = "\001\u001b[40m\002"
BG_RED = "\001\u001b[41m\002"
BG_GREEN = "\001\u001b[42m\002"
BG_YELLOW = "\001\u001b[43m\002"
BG_BLUE = "\001\u001b[44m\002"
BG_MAGENTA = "\001\u001b[45m\002"
BG_CYAN = "\001\u001b[46m\002"
BG_WHITE = "\001\u001b[47m\002"

END = "\001\033[0m\002"
BOLD = "\001\033[1m\002"
UNDERLINE = "\001\033[4m\002"
BOLDEND = "\001\033[22m\002"
UNDERLINEEND = "\001\033[24m\002"


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

def bg_black(string: str) -> str:
    return BG_BLACK + string + END

def bg_red(string: str) -> str:
    return BG_RED + string + END

def bg_green(string: str) -> str:
    return BG_GREEN + string + END

def bg_yellow(string: str) -> str:
    return BG_YELLOW + string + END

def bg_cyan(string: str) -> str:
    return BG_CYAN + string + END

def bg_blue(string: str) -> str:
    return BG_BLUE + string + END

def bg_magenta(string: str) -> str:
    return BG_MAGENTA + string + END

def bg_white(string: str) -> str:
    return BG_WHITE + string + END

def bold(string) -> str:
    return BOLD + string + BOLDEND

def underline(string) -> str:
    return UNDERLINE + string + UNDERLINEEND

def remove_all_occurrences(string: str, start: str, end: str) -> str:
    res = string
    start_idx = 0
    end_idx = 0
    while start_idx != -1 and end_idx != -1:
        start_idx = res.find(start)
        if start_idx != -1:
            end_idx = res.find(end, start_idx + len(start))
            if end_idx != -1:
                res = res[:start_idx] + res[end_idx + len(end):]
    return res

def tabulate(headers: typing.List[str], rows: typing.List[typing.List[str]]) -> str:
    # Determine column widths
    all_rows = [headers] + rows
    regex_filter = "\033\[[\d;]+m|[\x01\x02]"
    col_widths = [max(len(re.sub(regex_filter, "", str(row[i]))) for row in all_rows) for i in range(len(headers))]
    col_widths = [max(width, len(re.sub(regex_filter, "", str(header)))) for width, header in zip(col_widths, headers)]
    # Build table
    data_rows = []
    for row in rows:
        row_data = []
        for i, cell in enumerate(row):
            cell_width = len(re.sub(regex_filter, "", str(cell)))
            padding = col_widths[i] - cell_width
            row_data.append(f"{cell}{' ' * padding}")
        data_rows.append(" " * 4 + (4 * " ").join(row_data))
    header_row = []
    for i, cell in enumerate(headers):
        cell_width = len(re.sub(regex_filter, "", str(cell)))
        padding = col_widths[i] - cell_width
        header_row.append(f"{cell}{' ' * padding}")
    header_row = " " * 4 + (4 * " ").join(header_row)
    separator_row = [f"{'???' * (col_widths[i] + 4)}" for i, _ in enumerate(headers)]
    separator_row = 4* " " + "".join(separator_row)
    # Combine headers and data rows
    all_rows = [header_row] + [separator_row] + data_rows
    # Join all rows into table
    table = "\n".join(all_rows)
    return table

# https://stackoverflow.com/questions/3173320/text-progress-bar-in-terminal-with-block-characters?noredirect=1&lq=1
def print_progress_bar (iteration, total, prefix = "", suffix = "", decimals = 1, length = 100, fill = "???", print_end = "\r"):
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
    if iteration / total * 100 < 50:
        fill = red(fill)
    elif iteration / total * 100 < 100:
        fill = yellow(fill)
    else:
        # iteration == total
        fill = green(fill)
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + " " * (length - filled_length)
    print(f"\r{prefix} {bar} {percent}% {suffix}", end = print_end)
    # Print New Line on Complete
    if iteration == total: 
        print()