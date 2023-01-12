import typing
import threading
import shlex

import style
import channel
import platform
import session


class Manager:

    def __init__(self) -> None:
        self.__lock_sessions: threading.Lock = threading.Lock()
        self.__sessions: typing.Dict[str, session.Session] = {}
        self.__selected_id: str = ""
        self.__selected_session: session.Session = None
        self.__sessions_last_id: int = 0
        self.__lock_listeners: threading.Lock = threading.Lock()
        self.__listeners: typing.Dict[str, typing.Tuple(threading.Thread, threading.Event)] = {}
        self.__listeners_last_id: int = 0

    @property
    def sessions(self) -> typing.Dict[str, session.Session]:
        return self.__sessions

    @property
    def selected_id(self) -> str:
        return self.__selected_id

    @property
    def selected_session(self) -> session.Session:
        return self.__selected_session

    def clear(self) -> None:
        # stop all listeners
        for thread, stop_event, _, _, _ in self.__listeners.values():
            stop_event.set()
        for thread, stop_event, _, _, _ in self.__listeners.values():
            thread.join()
        with self.__lock_listeners:
            self.__listeners.clear()
        # stop and close all sessions
        for sess in self.__sessions.values():
            sess.stop()
            sess.interactive(False)
            sess.close()
        with self.__lock_sessions:
            self.__sessions.clear()

    # create a session
    def __do_create_session(self, addr: str, port: int, platform_name: str, bind: bool, listener_id: str = "", stop_event: threading.Event = None) -> session.Session:
        mode = channel.BIND if bind else channel.CONNECT
        sess = session.Session(addr, port, mode=mode, platform_name=platform_name)
        sess.open()
        id = -1
        if stop_event:
            while not stop_event.is_set():
                if sess.wait_open(0.1):
                    with self.__lock_sessions:
                        id = str(self.__sessions_last_id)
                        self.__sessions[id] = sess
                        self.__sessions_last_id += 1
                        if not self.__selected_session:
                            self.__selected_session = sess
                            self.__selected_id = id
                        sess.interactive(True) # getting pty immediately
                        sess.interactive(False)
                        break
            if stop_event.is_set():
                sess.stop()
                sess.close()
                sess = None
                if id != -1:
                    with self.__lock_sessions:
                        del self.__sessions[id]
        else:
            try:
                if sess.wait_open():
                    with self.__lock_sessions:
                        id = str(self.__sessions_last_id)
                        self.__sessions[id] = sess
                        self.__sessions_last_id += 1
                        if not self.__selected_session:
                            self.__selected_session = sess
                            self.__selected_id = id
            except KeyboardInterrupt:
                sess.stop()
                sess.close()
        if sess:
            with self.__lock_listeners:
                if listener_id in self.__listeners.keys():
                    del self.__listeners[listener_id]
        if sess and not sess.is_open:
            sess = None
        return sess

    def create_session(self, addr: str, port: int, platform_name: str = platform.LINUX, bind: bool = False, background: bool = False) -> typing.Tuple[bool, str]:
        res = False
        error = style.bold("failed to create session")
        stop_event = threading.Event()
        if not background:
            sess = self.__do_create_session(addr, port, platform_name, bind)
            if sess:
                sess.interactive(True) 
                sess.start()
                sess.wait_stop()
                sess.interactive(False)
                print()
                res = True
                error = ""
        else:
            with self.__lock_listeners:
                stop_event = threading.Event()
                thread = threading.Thread(target=self.__do_create_session, args = (addr, port, platform_name, bind, str(self.__listeners_last_id), stop_event))
                self.__listeners[str(self.__listeners_last_id)] = (thread, stop_event, addr, port, platform_name)
                thread.start()
                self.__listeners_last_id += 1
                res = True
                error = ""
        return res, error

    # kill a session or a listener
    def kill(self, type: str, id: str) -> typing.Tuple[bool, str]:
        res = True
        error = ""
        if type == "session":
            with self.__lock_sessions:
                if id in self.__sessions.keys():
                    sess = self.__sessions[id]
                    sess.stop()
                    sess.close()
                    del self.__sessions[id]
                    if id == self.__selected_id:
                        self.__selected_id = ""
                        self.__selected_session = None
                else:
                    res = False
                    error = style.bold("unknown session id ") + style.bold(style.red(f"{id}"))
        elif type == "listener":
            thread = None
            stop_event = None
            with self.__lock_listeners:
                if id in self.__listeners.keys():
                    thread, stop_event, _, _, _ = self.__listeners[id]
                    stop_event.set()
                    thread.join()
                    del self.__listeners[id]
                else:
                    res = False
                    error = style.bold("unknown listener id ") + style.bold(style.red(f"{id}"))
        return res, error

    def select_session(self, id: str) -> typing.Tuple[int, str]:
        res = False
        error = style.bold("unknown session id ") + style.bold(style.red(f"{id}"))
        if id == "-1":
            self.__selected_id = ""
            self.__selected_session = None
            res = True
            error = ""
        elif id in self.__sessions.keys():
            self.__selected_id = id
            self.__selected_session = self.__sessions[id]
            res = True
            error = ""
        return res, error

    def remote_shell(self, id: str = "") -> typing.Tuple[bool, str]:
        res = False 
        if not id:
            id = self.__selected_id
        error = style.bold("unknown session id ") + style.bold(style.red(f"{id}"))
        if id in self.__sessions.keys():
            sess = self.__sessions[id]
            sess.interactive(True) 
            sess.start()
            stopped = False
            while not stopped:
                try:
                    stopped = sess.wait_stop()
                except KeyboardInterrupt:
                    # ignore keyboard interrupt for non raw mode shell like windows
                    pass
            sess.interactive(False)
            print()
            res = True
            error = ""
        return res, error

    def show(self, type: str) -> typing.Tuple[bool, str]:
        res = False
        serializations = []
        if type == "sessions":
            res = True
            for id, sess in self.__sessions.items():
                res, error, user = sess.platform.whoami()
                serializations.append(f"{id},{user},{sess.remote},{sess.platform_name}")
        elif type == "listeners":
            res = True
            for id, value in self.__listeners.items():
                serializations.append(f"{id},@{value[2]}:{value[3]},{value[4]}")
        return res, "\n".join(serializations)

    def get_session_remote(self, id: str = "") -> str:
        host = ""
        if not id:
            id = self.__selected_id
        if id in self.__sessions.keys():
            sess = self.__sessions[id]
            host = sess.remote
        return host

    def download(self, rfile: str, lfile: str, id: str = "") -> typing.Tuple[bool, str]:
        res = False
        error = style.bold("download operation failed")
        rfile = shlex.quote(rfile) # to avoid remote command injection though it's kinda useless
        if not id:
            id = self.__selected_id
        if id in self.__sessions.keys():
            sess = self.__sessions[id]
            res, error, data = sess.download(rfile)
            if res:
                try:
                    with open(lfile, "wb") as f:
                        f.write(data)
                except FileNotFoundError:
                    res = False
                    error = style.bold("cannot write local file ") + style.bold(style.red(f"{lfile}")) + style.bold(": parent directory not found")
                except PermissionError:
                    res = False
                    error = style.bold("don't have permission to write local file ") + style.bold(style.red(f"{lfile}")) 
        else:
            if not id:
                error = style.bold("no session selected for the download operation")
            else:
                error = style.bold("unknown session id ") + style.bold(style.red(f"{id}"))
        return res, error
 
    def upload(self, lfile: str, rfile: str, id: str = "") -> typing.Tuple[bool, str]:
        res = False
        error = style.bold("upload operation failed")
        if not id:
            id = self.__selected_id
        if id in self.__sessions.keys():
            sess = self.__sessions[id]
            try:
                with open(lfile, "rb") as f:
                    data = f.read()
                    res, error = sess.upload(rfile, data)
            except FileNotFoundError:
                res = False
                error = style.bold("local file ") + style.bold(style.red(f"{lfile}")) + style.bold(" not found")
            except IsADirectoryError:
                res = False
                error = style.bold("local ") + style.bold(style.red(f"{lfile}")) + style.bold(" is a directory")
            except PermissionError:
                res = False
                error = style.bold("don't have permission to read local file ") + style.bold(style.red(f"{lfile}")) 
        else:
            if not id:
                error = style.bold("no session selected for the upload operation")
            else:
                error = style.bold("unknown session id ") + style.bold(style.red(f"{id}"))
        return res, error


