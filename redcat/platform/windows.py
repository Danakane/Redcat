import base64
import os
import typing
import tty
import termios
import sys
import shlex

import redcat.style
import redcat.channel
import redcat.transaction
import redcat.platform


class Windows(redcat.platform.Platform):

    def __init__(self, chan: redcat.channel.Channel) -> None:
        super().__init__(chan, redcat.platform.WINDOWS)
        self.__interactive: bool = False

    def is_interactive(self) -> bool:
        return self.__interactive

    @redcat.platform.Platform._with_lock
    def interactive(self, value: bool, session_id: str = None, raw:bool =True) -> bool:
        self.__interactive = value
        self.channel.purge()
        res, _ = self.send_cmd("")
        return res

    def build_transaction(self, payload: bytes, start: bytes, end: bytes, control: bytes) -> bytes:
        return b"echo %b & (%b && echo %b) & echo %b\n" % (start, payload, control, end)

    def whoami(self) -> typing.Tuple[bool, bool, str]:
        self.channel.purge()
        res, cmd_success, data = redcat.transaction.Transaction(f"whoami".encode(), self, True).execute()
        if not cmd_success:
            data = b""
        return res, cmd_success, data.decode("utf-8").replace("\r", "").replace("\n", "").strip()

    def hostname(self) -> typing.Tuple[bool, bool, str]:
        self.channel.purge()
        res, cmd_success, data = redcat.transaction.Transaction(f"hostname".encode(), self, True).execute()
        if not cmd_success:
            data = b""
        return res, cmd_success, data.decode("utf-8").replace("\r", "").replace("\n", "").strip()

    def download(self, rfile: str) -> typing.Tuple[bool, str, bytes]:
        cmd_success = False
        rfile = rfile.replace("'", "\"")
        error = redcat.style.bold("failed to download remote file ") + redcat.style.bold(redcat.style.red(f"{rfile}"))
        data = b""
        self.channel.purge()
        with self.channel.transaction_lock:
            res, cmd_success, data = redcat.transaction.Transaction(f"type {rfile}".encode(), self, True).execute()
            if not cmd_success:
                res = False
                error = redcat.style.bold("can't download " + redcat.style.red(f"{rfile}") + ": " + data.decode("utf-8"))
            else:
                tmp_fname = base64.b64encode(os.urandom(16)).decode("utf-8").replace("/", "_").replace("=", "0") + ".tmp"
                tmp_file = f"\"C:\\windows\\tasks\\{tmp_fname}\""
                res, cmd_success, data = redcat.transaction.Transaction(f"certutil -encode {rfile} {tmp_file}".encode(), self, True).execute()
                if res and cmd_success:
                    res, cmd_success, data = redcat.transaction.Transaction(f"findstr /v CERTIFICATE {tmp_file}".encode(), self, True).execute()
                    if res and cmd_success:
                        data = base64.b64decode(data)
                        error = ""
                    else:
                        error = redcat.style.bold("failed to download " + redcat.style.red(f"{rfile}") + ": " + data.decode("utf-8"))
                    if res:
                        redcat.transaction.Transaction(f"del {tmp_file}".encode(), self, True).execute()
                else:
                    error = redcat.style.bold("failed to download " + redcat.style.red(f"{rfile}") + ": " + data.decode("utf-8"))
        return cmd_success, error, data

    def upload(self, rfile: str, data: bytes) -> typing.Tuple[bool, str]:
        cmd_success = False
        error = redcat.style.bold("Failed to upload file ") + redcat.style.bold(redcat.style.red(f"{rfile}")) 
        self.channel.purge()
        encoded = base64.b64encode(data)
        # devide encoded data into chunks of 4096 bytes at most
        n = 4096
        chunks = [encoded[i:i+n] for i in range(0, len(encoded), n)]
        # then for each chunk execute a transaction to write into a temporary file
        # the lock is used for performance -> starve the session reader main loop 
        with self.channel.transaction_lock:
            length = len(chunks) 
            tmp_file = base64.b64encode(os.urandom(16)).decode("utf-8").replace("/", "_").replace("=", "0") + ".tmp"
            parent = os.path.dirname(rfile)
            if parent:
                tmp_file = f"{parent}/{tmp_file}"
            tmp_file = shlex.quote(tmp_file).replace("'", "\"")
            res, cmd_success, data = redcat.transaction.Transaction(f"echo \"\" > {tmp_file}".encode(), self, True).execute()
            if not cmd_success:
                res = False
                error = redcat.style.bold("can't upload " + redcat.style.red(f"{rfile}") + ": " + data.decode("utf-8"))
            else:
                redcat.style.print_progress_bar(0, length, prefix = f"Upload {rfile}:", suffix = "Complete", length = 50)
                res, cmd_success, _ =  redcat.transaction.Transaction(b"echo " + chunks[0] + f" > {tmp_file}".encode(), self, True).execute()
                if cmd_success:
                    i = 1
                    redcat.style.print_progress_bar(i, length, prefix = f"Upload {rfile}:", suffix = "Complete", length = 50)
                    if length > 1:
                        for chunk in chunks[1:]:
                            i += 1
                            res, cmd_success, _ = redcat.transaction.Transaction(b"echo " + chunk + f" >> {tmp_file}".encode(), self, True).execute()
                            if not cmd_success:
                                break
                            redcat.style.print_progress_bar(i, length, prefix = f"Upload {rfile}:", suffix = "Complete", length = 50)
                print()
                if cmd_success:
                    # decode the temporary file into the final file and delete the temporary file
                    rfile = "\"" + rfile[1:-1] + "\""
                    res, cmd_success, data = redcat.transaction.Transaction(f"certutil -decode {tmp_file} {rfile}".encode(), self, True).execute()
                if res:
                    redcat.transaction.Transaction(f"del {tmp_file}".encode(), self, True).execute()
                if cmd_success:
                    error = ""
                else:
                    error = redcat.style.bold("failed to upload ") + redcat.style.bold(redcat.style.red(f"{rfile}")) + redcat.style.bold(": " + data.decode("utf-8"))
        return cmd_success, error
