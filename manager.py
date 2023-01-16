import typing
import threading
import shlex

import style
import channel
import platform
import listener, listener.factory
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
        for listen_endpoint in self.__listeners.values():
            listen_endpoint.stop()
        with self.__lock_listeners:
            self.__listeners.clear()
        # stop and close all sessions
        for sess in self.__sessions.values():
            sess.stop()
            sess.interactive(False)
            sess.close()
        with self.__lock_sessions:
            self.__sessions.clear()

    def __on_new_channel(self, sender: listener.Listener, chan: channel.Channel, platform_name: str) -> None:
        sess = session.Session(chan, platform_name=platform_name)
        sess.open()
        id = -1
        while sender.running:
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
                    print()
                    break
        if not sender.running:
            if id == -1:
                with self.__lock_sessions:
                    sess.stop()
                    sess.close()
                    sess = None

    def listen(self, addr: str, port: int, platform_name: str = platform.LINUX, background: bool = False) -> typing.Tuple[bool, str]:
        res = False
        error = style.bold("failed to create session")
        if not background:
            chan = None
            sess = None
            id = -1
            new_listener = listener.factory.get_listener(addr, port, platform_name)
            try:
                chan, platform_name = new_listener.listen_once()
                if chan:
                    sess = session.Session(chan, platform_name=platform_name)
                    sess.open()
                    if sess.wait_open():
                        with self.__lock_sessions:
                            id = str(self.__sessions_last_id)
                            self.__sessions[id] = sess
                            self.__sessions_last_id += 1
                            if not self.__selected_session:
                                self.__selected_session = sess
                                self.__selected_id = id
            except KeyboardInterrupt:
                if sess:
                    sess.stop()
                    sess.close()
                    sess = None
                    if id != -1 and id in self.__sessions.keys():
                        del self.__sessions[id]
            if sess:
                sess.interactive(True) 
                sess.start()
                sess.wait_stop()
                sess.interactive(False)
                print()
                res = True
                error = ""
        else:
            new_listener = listener.factory.get_listener(addr, port, platform_name, callback=self.__on_new_channel)
            with self.__lock_listeners:
                self.__listeners[str(self.__listeners_last_id)] = new_listener
                self.__listeners_last_id += 1
            new_listener.start()
            res = True
            error = ""
        return res, error

    def connect(self, addr: str, port: int, platform_name: str = platform.LINUX) -> typing.Tuple[bool, str]:
        res = False
        error = style.bold("failed to create session")
        sess = session.Session(addr=addr, port=port, platform_name=platform_name)
        sess.open()
        id = -1
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
            if sess:
                sess.stop()
                sess.close()
                sess = None
                if id != -1 and id in self.__sessions.keys():
                    del self.__sessions[id]
        if sess:
            sess.interactive(True) 
            sess.start()
            sess.wait_stop()
            sess.interactive(False)
            print()
            res = True
            error = ""
        return res, error

    # kill a session or a listener
    def kill(self, type: str, id: str) -> typing.Tuple[bool, str]:
        res = False
        error = style.bold("invalid parameter ") + style.bold(style.red(f"{type}"))
        if type == "session":
            with self.__lock_sessions:
                if id in self.__sessions.keys():
                    sess = self.__sessions[id]
                    sess.stop()
                    sess.close()
                    del self.__sessions[id]
                    res = True
                    if id == self.__selected_id:
                        self.__selected_id = ""
                        self.__selected_session = None
                else:
                    error = style.bold("unknown session id ") + style.bold(style.red(f"{id}"))
        elif type == "listener":
            with self.__lock_listeners:
                if id in self.__listeners.keys():
                    listen_endpoint = self.__listeners[id]
                    listen_endpoint.stop()
                    del self.__listeners[id]
                    res = True
                else:
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

    def show(self, type: str) -> typing.Tuple[bool, str, str]:
        res = False
        error = style.bold("invalid parameter ") + style.bold(style.red(f"{type}"))
        serializations = []
        if type == "sessions":
            res = True
            for id, sess in self.__sessions.items():
                res, error, user = sess.platform.whoami()
                serializations.append(f"{id},{user},{sess.remote},{sess.platform_name}")
        elif type == "listeners":
            res = True
            for id, listen_point in self.__listeners.items():
                serializations.append(f"{id},{listen_point.endpoint},{listen_point.platform_name}")
        return res, error, "\n".join(serializations)

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


