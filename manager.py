import typing
import threading

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
        for thread, stop_event in self.__listeners.values():
            stop_event.set()
        for thread, stop_event in self.__listeners.values():
            thread.join()
        self.__listeners.clear()
        # stop and close all sessions
        for sess in self.__sessions.values():
            sess.stop()
            sess.interactive(False)
            sess.close()
        self.__sessions.clear()

    # create a session
    def __do_create_session(self, addr: str, port: int, platform: str, bind: bool, listener_id: str = "", stop_event: threading.Event = None) -> session.Session:
        mode = channel.Channel.BIND if bind else channel.Channel.CONNECT
        sess = session.Session(addr, port, mode=mode, platform_name=platform)
        sess.open()
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
        else:
            if sess.wait_open():
                with self.__lock_sessions:
                    id = str(self.__sessions_last_id)
                    self.__sessions[id] = sess
                    self.__sessions_last_id += 1
                    if not self.__selected_session:
                        self.__selected_session = sess
                        self.__selected_id = id
        if sess:
            with self.__lock_listeners:
                if listener_id in self.__listeners.keys():
                    del self.__listeners[listener_id]
        return sess

    def create_session(self, addr: str, port: int, platform: str = platform.Platform.LINUX, bind: bool = False, background: bool = False) -> typing.Tuple[bool, str]:
        res = False
        error = "failed to create session"
        stop_event = threading.Event()
        if not background:
            sess = self.__do_create_session(addr, port, platform, bind)
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
                thread = threading.Thread(target=self.__do_create_session, args = (addr, port, platform, bind, str(self.__listeners_last_id), stop_event))
                self.__listeners[str(self.__listeners_last_id)] = (thread, stop_event)
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
                    error = f"unknown session id {id}"
        elif type == "listener":
            with self.__lock_listeners:
                if id in self.__listeners.keys():
                    thread, stop_event = self.__listeners[id]
                    stop_event.set()
                    thread.join()
                    del self.__listeners[id]
                else:
                    res = False
                    error = f"unknown listener id {id}"
        else:
            res = False
            error = f"unknown type {type}"
        return res, error

    def select_session(self, id: str) -> typing.Tuple[int, str]:
        res = False
        error = f"unknown session id {id}"
        with self.__lock_sessions:
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
        error = f"unknown session id {id}"
        with self.__lock_sessions:
            if id in self.__sessions.keys():
                sess = self.__sessions[id]
                sess.interactive(True) 
                sess.start()
                sess.wait_stop()
                sess.interactive(False)
                print()
                res = True
                error = ""
        return res, error

