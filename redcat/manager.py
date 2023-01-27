import argparse
import time
import typing
import threading
import shlex

import redcat.style
import redcat.channel
import redcat.platform
import redcat.listener, redcat.listener.factory
import redcat.session


class Manager:

    def __init__(self) -> None:
        self.__lock_sessions: threading.Lock = threading.RLock()
        self.__sessions: typing.Dict[str, redcat.session.Session] = {}
        self.__lock_broken_sessions: threading.Lock = threading.RLock()
        self.__broken_sessions: typing.List[str] = []
        self.__lock_broken_listeners: threading.Lock = threading.RLock()
        self.__broken_listeners: typing.List[str] = []
        self.__selected_id: str = ""
        self.__selected_session: redcat.session.Session = None
        self.__sessions_last_id: int = 0
        self.__lock_listeners: threading.Lock = threading.RLock()
        self.__listeners: typing.Dict[str, typing.Tuple(threading.Thread, threading.Event)] = {}
        self.__listeners_last_id: int = 0
        self.__garbage_collector: threading.Thread = None
        self.__stop_evt: threading.Event = threading.Event()

    @property
    def sessions(self) -> typing.Dict[str, redcat.session.Session]:
        return self.__sessions

    @property
    def selected_id(self) -> str:
        return self.__selected_id

    @property
    def selected_session(self) -> redcat.session.Session:
        return self.__selected_session

    def start(self) -> None:
        if not self.__garbage_collector:
            self.__stop_evt.clear()
            self.__garbage_collector = threading.Thread(target=self.__clean_broken_sessions_and_listeners)
            self.__garbage_collector.start()

    def stop(self) -> None:
        if self.__garbage_collector:
            self.__stop_evt.set()
            self.__garbage_collector.join()
            self.__garbage_collector = None

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

    def __clean_broken_sessions_and_listeners(self) -> None:
        while not self.__stop_evt.is_set():
            with self.__lock_broken_sessions:
                if len(self.__broken_sessions) > 0:
                    for id in self.__broken_sessions:
                        self.kill(None, "session", id)
                self.__broken_sessions.clear()
            with self.__lock_broken_listeners:
                if len(self.__broken_listeners) > 0:
                    for id in self.__broken_listeners:
                        self.kill(None, "listener", id)
                self.__broken_listeners.clear()
            time.sleep(0.05)

    def __on_new_channel(self, sender: redcat.listener.Listener, chan: redcat.channel.Channel, platform_name: str) -> None:
        sess = redcat.session.Session(error_callback=self.on_error, chan=chan, platform_name=platform_name)
        sess.open()
        id = None
        while sender.running:
            if sess.wait_open(0.1):
                with self.__lock_sessions:
                    id = str(self.__sessions_last_id)
                    self.__sessions_last_id += 1
                    res1 = sess.interactive(True, id) # getting pty immediately
                    res2 = sess.interactive(False)
                    res = res1 and res2
                    # we're not on the main thread. 
                    # We must first wait for the session to terminate the shell setup 
                    # before allowing any user interaction from the main thread
                    if res:
                        self.__sessions[id] = sess
                        if not self.__selected_session:
                            self.__selected_session = sess
                            self.__selected_id = id
                break
        if not sender.running:
            if not id:
                sess.stop()
                sess.close()
                sess = None

    def listen(self, background: bool=True, **kwargs) -> typing.Tuple[bool, str]:
        res = False
        error = redcat.style.bold("failed to create session")
        if not background:
            id = None
            chan = None
            sess = None
            new_listener = None
            try:
                new_listener = redcat.listener.factory.get_listener(error_callback=self.on_error, **kwargs)
            except Exception as err:
                error = redcat.utils.get_error(err)
                new_listener = None
            if new_listener:
                try:
                    res, error, chan, platform_name = new_listener.listen_once()
                    if res and chan:
                        sess = redcat.session.Session(error_callback=self.on_error, chan=chan, platform_name=platform_name)
                        sess.open()
                        if sess.wait_open():
                            with self.__lock_sessions:
                                id = str(self.__sessions_last_id)
                                self.__sessions_last_id += 1
                except KeyboardInterrupt:
                    res = False
                    sess = None
                    error = redcat.style.bold("interrupted by user")
            if sess:
                res1 = sess.interactive(True, id)
                if res1: 
                    sess.start()
                    sess.wait_stop()
                res2 = sess.interactive(False)
                res = res1 and res2
                if res:
                    with self.__lock_sessions:
                        self.__sessions[id] = sess
                        if not self.__selected_session:
                            self.__selected_session = sess
                            self.__selected_id = id
                        error = ""
                else:
                    error = redcat.style.bold(f"session {id} is broken")
                print()      
        else:
            new_listener = None
            try:
                new_listener = redcat.listener.factory.get_listener(callback=self.__on_new_channel, error_callback=self.on_error, **kwargs)
            except Exception as err:
                error = redcat.utils.get_error(err)
                new_listener = None
            if new_listener:
                with self.__lock_listeners:
                    self.__listeners[str(self.__listeners_last_id)] = new_listener
                    self.__listeners_last_id += 1
                res, error = new_listener.start()
        return res, error

    def connect(self, **kwargs) -> typing.Tuple[bool, str]:
        res = False
        error = redcat.style.bold("failed to create session")
        sess = None
        try:
            sess = redcat.session.Session(error_callback=self.on_error, **kwargs)
        except Exception as err:
            error = redcat.utils.get_error(err)
            sess = None
        if sess:
            res, error = sess.open()
            id = None
            if res:
                try:
                    if sess.wait_open():
                        with self.__lock_sessions:
                            id = str(self.__sessions_last_id)
                            self.__sessions_last_id += 1
                except KeyboardInterrupt:
                    res = False
                    sess = None
                    error = redcat.style.bold("interrupted by user")
                if sess:
                    res1 = sess.interactive(True, id)
                    if res1: 
                        sess.start()
                        sess.wait_stop()
                    res2 = sess.interactive(False)
                    res = res1 and res2
                    if res:
                        with self.__lock_sessions:
                            self.__sessions[id] = sess
                            if not self.__selected_session:
                                self.__selected_session = sess
                                self.__selected_id = id
                        error = ""
                    else:
                        error = redcat.style.bold(f"session {id} is broken")
                else:
                    error = redcat.style.bold("failed to create session")
                print()
        return res, error

    # kill a session or a listener
    def kill(self, sender: argparse.ArgumentParser, type: str, id: str) -> typing.Tuple[bool, str]:
        res = False
        error = redcat.style.bold("invalid parameter ") + redcat.style.bold(redcat.style.red(f"{type}"))
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
                    error = redcat.style.bold("unknown session id ") + redcat.style.bold(redcat.style.red(f"{id}"))
        elif type == "listener":
            with self.__lock_listeners:
                if id in self.__listeners.keys():
                    listen_endpoint = self.__listeners[id]
                    listen_endpoint.stop()
                    del self.__listeners[id]
                    res = True
                else:
                    error = redcat.style.bold("unknown listener id ") + redcat.style.bold(redcat.style.red(f"{id}"))
        return res, error

    def select_session(self, sender: argparse.ArgumentParser, id: str) -> typing.Tuple[int, str]:
        res = False
        error = redcat.style.bold("unknown session id ") + redcat.style.bold(redcat.style.red(f"{id}"))
        if id == "none":
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

    def remote_shell(self, sender: argparse.ArgumentParser, id: str = "") -> typing.Tuple[bool, str]:
        res = False 
        if not id:
            id = self.__selected_id
        error = redcat.style.bold("unknown session id ") + redcat.style.bold(redcat.style.red(f"{id}"))
        if id in self.__sessions.keys():
            sess = self.__sessions[id]
            if sess.is_open:
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
            else:
                error = redcat.style.bold("session " + redcat.style.red(id) + " is broken")
        return res, error

    def show(self, type: str) -> typing.Tuple[bool, str, str]:
        res = False
        error = redcat.style.bold("invalid parameter ") + redcat.style.bold(redcat.style.red(f"{type}"))
        serializations = []
        if type == "sessions":
            res = True
            for id, sess in self.__sessions.items():
                res, error, user = sess.platform.whoami()
                serializations.append(f"{id},{user},{sess.hostname},{sess.remote},{sess.protocol[1]},{sess.platform_name}")
        elif type == "listeners":
            res = True
            for id, listen_point in self.__listeners.items():
                serializations.append(f"{id},{listen_point.endpoint},{listen_point.protocol[1]},{listen_point.platform_name}")
        return res, error, "\n".join(serializations)

    def get_session_info(self, id: str = "") -> str:
        info = ""
        if not id:
            id = self.__selected_id
        if id in self.__sessions.keys():
            sess = self.__sessions[id]
            try:
                info = f"session {id}: {sess.user}@{sess.hostname}"
            except:
                info = ""
        return info

    def download(self, sender: argparse.ArgumentParser, rfile: str, lfile: str, id: str = "") -> typing.Tuple[bool, str]:
        res = False
        error = redcat.style.bold("download operation failed")
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
                    error = redcat.style.bold("cannot write local file ") + redcat.style.bold(redcat.style.red(f"{lfile}")) + redcat.style.bold(": parent directory not found")
                except PermissionError:
                    res = False
                    error = redcat.style.bold("don't have permission to write local file ") + redcat.style.bold(redcat.style.red(f"{lfile}")) 
        else:
            if not id:
                error = redcat.style.bold("no session selected for the download operation")
            else:
                error = redcat.style.bold("unknown session id ") + redcat.style.bold(redcat.style.red(f"{id}"))
        return res, error
 
    def upload(self, sender: argparse.ArgumentParser, lfile: str, rfile: str, id: str = "") -> typing.Tuple[bool, str]:
        res = False
        error = redcat.style.bold("upload operation failed")
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
                error = redcat.style.bold("local file ") + redcat.style.bold(redcat.style.red(f"{lfile}")) + redcat.style.bold(" not found")
            except IsADirectoryError:
                res = False
                error = redcat.style.bold("local ") + redcat.style.bold(redcat.style.red(f"{lfile}")) + redcat.style.bold(" is a directory")
            except PermissionError:
                res = False
                error = redcat.style.bold("don't have permission to read local file ") + redcat.style.bold(redcat.style.red(f"{lfile}")) 
        else:
            if not id:
                error = redcat.style.bold("no session selected for the upload operation")
            else:
                error = redcat.style.bold("unknown session id ") + redcat.style.bold(redcat.style.red(f"{id}"))
        return res, error

    def on_error(self, obj: typing.Any, error: str) -> None:
        if not threading.current_thread() is threading.main_thread():
            # on main thread, the error will be displayed after the command terminate
            print(redcat.style.bold(redcat.style.red("[!] error: ") + error))
        found = False
        with self.__lock_sessions:
            for id, sess in self.__sessions.items():
                if sess == obj:
                    found = True
                    if self.__selected_id == id:
                        self.__selected_id = ""
                        self.__selected_session = None
                    with self.__lock_broken_sessions:
                        self.__broken_sessions.append(id)
                    break
        if not found:
            with self.__lock_listeners:
                for id, listen_point in self.__listeners.items():
                    if listen_point == obj:
                        found = True
                        with self.__lock_broken_sessions:
                            self.__broken_listeners.append(id)
                        break



