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

    def __init__(self, logger_callback: typing.Callable = None) -> None:
        self.__logger_callback: typing.Callable = logger_callback
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
        self.__listeners: typing.Dict[str, redcat.listener.Listener] = {}
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
        with self.__lock_listeners:
        # stop all listeners
            for listen_endpoint in self.__listeners.values():
                listen_endpoint.stop()
            self.__listeners.clear()  
        with self.__lock_sessions:
            # stop and close all sessions
            for sess in self.__sessions.values():
                sess.stop()
                sess.interactive(False)
                sess.close()
            self.__sessions.clear()

    def __clean_broken_sessions_and_listeners(self) -> None:
        while not self.__stop_evt.is_set():
            with self.__lock_broken_sessions:
                if len(self.__broken_sessions) > 0:
                    for id in self.__broken_sessions:
                        with self.__lock_sessions:
                            if id in self.__sessions.keys():
                                self.kill("session", id)
                    self.__broken_sessions.clear()
            with self.__lock_broken_listeners:
                if len(self.__broken_listeners) > 0:
                    for id in self.__broken_listeners:
                        with self.__lock_listeners:
                            if id in self.__listeners.keys():
                                self.kill("listener", id)
                    self.__broken_listeners.clear()
            time.sleep(0.01)

    def __on_new_channel(self, sender: redcat.listener.Listener, chan: redcat.channel.Channel, platform_name: str) -> None:
        res = False
        id = None
        with self.__lock_sessions:
            id = str(self.__sessions_last_id)
            self.__sessions_last_id += 1
        sess = redcat.session.Session(id=id, error_callback=self.on_error, logger_callback=self.__logger_callback, chan=chan, platform_name=platform_name)
        sess.open()
        if sess.wait_open(15):
            res1 = sess.interactive(True, False) # getting pty immediately, but no raw mode in worker thread to not break the console
            res2 = sess.interactive(False)
            res = res1 and res2
            # we're not on the main thread. 
            # We must first wait for the session to terminate the shell setup 
            # before allowing any user interaction from the main thread
            if res:
                with self.__lock_sessions:
                    self.__sessions[sess.id] = sess
                    if not self.__selected_session:
                        self.__selected_session = sess
                        self.__selected_id = sess.id
                    res = True
                    if self.__logger_callback:
                        self.__logger_callback(f"{redcat.style.bold(redcat.style.blue(sess.protocol[1]))} " + 
                            f"session {redcat.style.bold(redcat.style.darkcyan(sess.id))}, " + 
                            f"connected to {redcat.style.bold(redcat.style.blue(sess.user + '@' + sess.hostname))}, is now ready")
        if not res:
            sess.close()

    def listen(self, background: bool=True, **kwargs) -> typing.Tuple[bool, str]:
        res = False
        error = redcat.style.bold("failed to create session")
        if not background:
            chan = None
            sess = None
            new_listener = None
            try:
                listener_id = None
                with self.__lock_listeners:
                    listener_id = str(self.__listeners_last_id)
                    self.__listeners_last_id += 1
                new_listener = redcat.listener.factory.get_listener(id=listener_id, error_callback=self.on_error, 
                    logger_callback=self.__logger_callback, **kwargs)
            except Exception as err:
                error = redcat.utils.get_error(err)
                new_listener = None
            if new_listener:
                try:
                    res, error, chan, platform_name = new_listener.listen_once()
                    if res and chan:
                        id = None
                        with self.__lock_sessions:
                            id = str(self.__sessions_last_id)
                            self.__sessions_last_id += 1
                        sess = redcat.session.Session(id=id, error_callback=self.on_error, 
                            logger_callback=self.__logger_callback, chan=chan, platform_name=platform_name)
                        res, error = sess.open()
                        if res:
                            sess.wait_open()
                        else:
                            sess.close()
                            sess = None
                except KeyboardInterrupt:
                    res = False
                    sess = None
                    error = redcat.style.bold("interrupted by user")
            if res:
                res1 = sess.interactive(True)
                if res1: 
                    sess.start()
                    sess.wait_stop()
                res2 = sess.interactive(False)
                res = res1 and res2
                if res:
                    with self.__lock_sessions:
                        self.__sessions[sess.id] = sess
                        if not self.__selected_session:
                            self.__selected_session = sess
                            self.__selected_id = sess.id
                    error = ""
                    self.__logger_callback(f"{redcat.style.bold(redcat.style.blue(sess.protocol[1]))} " + 
                        f"session {redcat.style.bold(redcat.style.darkcyan(sess.id))}, " + 
                        f"connected to {redcat.style.bold(redcat.style.blue(sess.user + '@' + sess.hostname))}, is now ready")
                else:
                    error = redcat.style.bold(f"session {sess.id} is broken")
                print()      
        else:
            new_listener = None
            try:
                listener_id = None
                with self.__lock_listeners:
                    listener_id = str(self.__listeners_last_id)
                    self.__listeners_last_id += 1
                new_listener = redcat.listener.factory.get_listener(id=listener_id, callback=self.__on_new_channel, 
                                    error_callback=self.on_error, logger_callback=self.__logger_callback, **kwargs)
            except Exception as err:
                error = redcat.utils.get_error(err)
                new_listener = None
            if new_listener:
                with self.__lock_listeners:
                    self.__listeners[new_listener.id] = new_listener
                res, error = new_listener.start()
        return res, error

    def connect(self, **kwargs) -> typing.Tuple[bool, str]:
        res = False
        error = redcat.style.bold("failed to create session")
        sess = None
        try:
            id = None
            with self.__lock_sessions:
                id = str(self.__sessions_last_id)
                self.__sessions_last_id += 1
            sess = redcat.session.Session(id=id, error_callback=self.on_error, logger_callback=self.__logger_callback, **kwargs)
        except Exception as err:
            error = redcat.utils.get_error(err)
            sess = None
        if sess:
            try:
                res, error = sess.open()
                if res:
                    sess.wait_open()
                else:
                    sess.close()
                    sess = None
            except KeyboardInterrupt:
                res = False
                sess = None
                error = redcat.style.bold("interrupted by user")
            if res:
                res1 = sess.interactive(True)
                if res1: 
                    sess.start()
                    sess.wait_stop()
                res2 = sess.interactive(False)
                res = res1 and res2
                if res:
                    with self.__lock_sessions:
                        self.__sessions[sess.id] = sess
                        if not self.__selected_session:
                            self.__selected_session = sess
                            self.__selected_id = sess.id
                    error = ""
                    self.__logger_callback(f"{redcat.style.bold(redcat.style.blue(sess.protocol[1]))} " + 
                        f"session {redcat.style.bold(redcat.style.darkcyan(sess.id))}, " + 
                        f"connected to {redcat.style.bold(redcat.style.blue(sess.user + '@' + sess.hostname))}, is now ready")
                else:
                    error = redcat.style.bold(f"session {sess.id} is broken")
                print()
        return res, error

    def kill(self, type: str, id: str) -> typing.Tuple[bool, str]:
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
                    self.__logger_callback(f"session {redcat.style.bold(redcat.style.darkcyan(id))} has been removed")
                else:
                    error = redcat.style.bold("unknown session id ") + redcat.style.bold(redcat.style.red(f"{id}"))
        elif type == "listener":
            with self.__lock_listeners:
                if id in self.__listeners.keys():
                    listen_endpoint = self.__listeners[id]
                    listen_endpoint.stop()
                    del self.__listeners[id]
                    res = True
                    self.__logger_callback(f"listener {redcat.style.bold(redcat.style.darkcyan(id))} has been removed")
                else:
                    error = redcat.style.bold("unknown listener id ") + redcat.style.bold(redcat.style.red(f"{id}"))
        return res, error

    def upgrade(self, id: str) -> typing.Tuple[bool, str]:
        res = False 
        if not id:
            id = self.__selected_id
        error = redcat.style.bold("unknown session id ") + redcat.style.bold(redcat.style.red(f"{id}"))
        with self.__lock_sessions:
            if id in self.__sessions.keys():
                res, error = self.__sessions[id].platform.upgrade()
                if res:
                    self.__logger_callback(f"session {redcat.style.bold(redcat.style.darkcyan(id))} has been successfully upgraded")
        return res, error

    def select_session(self, id: str) -> typing.Tuple[int, str]:
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

    def remote_shell(self, id: str = "") -> typing.Tuple[bool, str]:
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
                serializations.append((
                    f"{redcat.style.bold(redcat.style.cyan(id))},"
                    f"{redcat.style.bold(redcat.style.blue(sess.user))},"
                    f"{redcat.style.bold(redcat.style.blue(sess.hostname))},"
                    f"{redcat.style.bold(redcat.style.blue(sess.remote))},"
                    f"{redcat.style.bold(redcat.style.blue(sess.protocol[1]))},"
                    f"{redcat.style.bold(redcat.style.yellow(sess.platform_name))}"
                    )
                )
        elif type == "listeners":
            res = True
            for id, listen_point in self.__listeners.items():
                serializations.append((
                    f"{redcat.style.bold(redcat.style.darkcyan(id))},"
                    f"{redcat.style.bold(redcat.style.blue(listen_point.endpoint))},"
                    f"{redcat.style.bold(redcat.style.blue(listen_point.protocol[1]))},"
                    f"{redcat.style.bold(redcat.style.yellow(listen_point.platform_name))}"
                    )
                )
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

    def download(self, rfile: str, lfile: str, id: str = "") -> typing.Tuple[bool, str]:
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
                except IsADirectoryError:
                    res = False
                    error = redcat.style.bold("cannot write local file: ") + \
                                redcat.style.bold(redcat.style.red(f"{lfile}")) + \
                                redcat.style.bold(" is a directory")
                except FileNotFoundError:
                    res = False
                    error = redcat.style.bold("cannot write local file ") + \
                                redcat.style.bold(redcat.style.red(f"{lfile}")) + \
                                redcat.style.bold(": parent directory not found")
                except PermissionError:
                    res = False
                    error = redcat.style.bold("don't have permission to write local file ") + redcat.style.bold(redcat.style.red(f"{lfile}")) 
        else:
            if not id:
                error = redcat.style.bold("no session selected for the download operation")
            else:
                error = redcat.style.bold("unknown session id ") + redcat.style.bold(redcat.style.red(f"{id}"))
        return res, error
 
    def upload(self, lfile: str, rfile: str, id: str = "") -> typing.Tuple[bool, str]:
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

    def on_error(self, sender: typing.Any, error: str) -> None:
        if not threading.current_thread() is threading.main_thread():
            # on main thread, the error will be displayed after the command terminate
            self.__logger_callback(redcat.style.bold(redcat.style.red("[!] error: ") + error))
        if isinstance(sender, redcat.session.Session):
            if self.__selected_id == id:
                self.__selected_id = ""
                self.__selected_session = None
            with self.__lock_broken_sessions:
                self.__broken_sessions.append(sender.id)
        elif isinstance(sender, redcat.listener.Listener):
            with self.__lock_broken_sessions:
                self.__broken_listeners.append(sender.id)



