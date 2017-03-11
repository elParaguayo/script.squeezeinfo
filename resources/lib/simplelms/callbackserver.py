"""
An asynchronous client that listens to messages broadcast by the server.

The client also accepts callback functions.

The client subclasses python threading so methods are built-in to the class
object.
"""
from threading import Thread
from telnetlib import IAC, NOP, Telnet
import socket
from time import sleep


class CallbackServerError(Exception):
    pass


class CallbackServer(Thread):

    MIXER_ALL = "mixer"
    VOLUME_CHANGE = "mixer volume"

    PLAYLIST_ALL = "playlist"
    PLAY_PAUSE = "playlist pause"
    PLAY = "playlist pause 0"
    PAUSE = "playlist pause 1"
    PLAYLIST_OPEN = "playlist open"
    PLAYLIST_CHANGE_TRACK = "playlist newsong"
    PLAYLIST_LOAD_TRACKS = "playlist loadtracks"
    PLAYLIST_ADD_TRACKS = "playlist addtracks"
    PLAYLIST_LOADED = "playlist load_done"
    PLAYLIST_REMOVE = "playlist delete"
    PLAYLIST_CLEAR = "playlist clear"
    PLAYLIST_CHANGED = [PLAYLIST_LOAD_TRACKS,
                        PLAYLIST_LOADED,
                        PLAYLIST_ADD_TRACKS,
                        PLAYLIST_REMOVE,
                        PLAYLIST_CLEAR]

    CLIENT_ALL = "client"
    CLIENT_NEW = "client new"
    CLIENT_DISCONNECT = "client disconnect"
    CLIENT_RECONNECT = "client reconnect"
    CLIENT_FORGET = "client forget"

    SERVER_ERROR = "server_error"
    SERVER_CONNECT = "server_connect"

    SYNC = "sync"

    def __init__(self,
                 hostname=None,
                 port=9090,
                 username="",
                 password=""):
        super(CallbackServer, self).__init__()
        self.callbacks = {}
        self.notifications = []
        self.abort = False
        self.charset = "utf8"
        self.ending = "\n".encode(self.charset)
        self.connected = False
        self.daemon = True
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.is_connected = False
        self.cb_class = None

    def connect(self, update=True):
        """
        Connect
        """
        if not self.hostname:
            raise CallbackServerError("No server details provided.")

        self.telnet_connect()
        self.login()
        self.is_connected = True

    def disconnect(self):
        self.telnet.close()
        self.is_connected = False

    def telnet_connect(self):
        """
        Telnet Connect
        """
        self.telnet = Telnet(self.hostname, self.port, timeout=2)

    def login(self):
        """
        Login
        """
        result = self.request("login %s %s" % (self.username, self.password))
        self.logged_in = (result == "******")
        if not self.logged_in:
            raise CallbackServerError("Unable to login. Check username and "
                                      "password.")

    def request(self, command_string, preserve_encoding=False):
        """
        Request
        """
        # self.logger.debug("Telnet: %s" % (command_string))
        self.telnet.write(self.__encode(command_string + "\n"))
        # Include a timeout to stop unnecessary blocking
        response = self.telnet.read_until(self.__encode("\n"),timeout=1)[:-1]
        if not preserve_encoding:
            response = self.__decode(self.__unquote(response))
        else:
            command_string_quoted = \
                command_string[0:command_string.find(':')] + \
                command_string[command_string.find(':'):].replace(
                    ':', self.__quote(':'))
        start = command_string.split(" ")[0]
        if start in ["songinfo", "trackstat", "albums", "songs", "artists",
                     "rescan", "rescanprogress"]:
            if not preserve_encoding:
                result = response[len(command_string)+1:]
            else:
                result = response[len(command_string_quoted)+1:]
        else:
            if not preserve_encoding:
                result = response[len(command_string)-1:]
            else:
                result = response[len(command_string_quoted)-1:]
        return result

    def __encode(self, text):
        return text.encode(self.charset)

    def __decode(self, bytes):
        return bytes.decode(self.charset)

    def __quote(self, text):
        try:
            import urllib.parse
            return urllib.parse.quote(text, encoding=self.charset)
        except ImportError:
            import urllib
            return urllib.quote(text)

    def __unquote(self, text):
        try:
            import urllib.parse
            return urllib.parse.unquote(text, encoding=self.charset)
        except ImportError:
            import urllib
            return urllib.unquote(text)

    def unquote(self, text):
        return self.__unquote(text)

    def set_server(self, hostname, port=9090, username="", password="",
                   parent_class=None):

        if self.is_connected:
            raise CallbackServerError("Server already logged in.")

        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        if parent_class:
            self.set_parent_class(parent_class)

        #self.connect()

    def set_parent_class(self, parent):
        self.cb_class = parent

    def event(self, eventname):

        def decorator(func):
            self.add_callback(eventname, func)

            return func

        return decorator

    def add_callback(self, event, callback):
        """Add a callback.

           Takes two parameter:
             event:    string of single notification or list of notifications
             callback: function to be run if server sends matching notification
        """
        if type(event) == list:
            for ev in event:
                self.__add_callback(ev, callback)

        else:
            self.__add_callback(event, callback)

    def __add_callback(self, event, callback):
        self.callbacks[event] = callback
        notification = event.split(" ")[0]
        if notification not in self.notifications:
            self.notifications.append(notification)

    def remove_callback(self, event):
        """Remove a callback.

           Takes one parameter:
             event: string of single notification or list of notifications
        """
        if type(event) == list:
            for ev in event:
                self.__remove_callback(ev)

        else:
            self.__remove_callback(event)

    def __remove_callback(self, event):
        del self.callbacks[event]

    def get_server(self):
        return Server(hostname=self.hostname, port=self.port)

    def check_event(self, event):
        """Checks whether any of the requested notification types match the
           received notification. If there's a match, we run the requested
           callback function passing the notification as the only parameter.
        """
        for cb in self.callbacks:
            if cb in event:
                callback = self.callbacks[cb]
                if self.cb_class:
                    callback(self.cb_class, self.unquote(event))
                else:
                    callback(self.unquote(event))
                break

    def check_connection(self):
        """Method to check whether we can still connect to the server.

           Sets the flag to stop the server if no collection is available.
        """
        # Create a socket object
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Set a timeout - we don't want this to block unnecessarily
        s.settimeout(2)

        try:
            # Try to connect
            s.connect((self.hostname, self.port))

        except socket.error:
            # We can't connect so stop the server
            self.abort = True

        # Close our socket object
        s.close()

    def run(self):

        while not self.abort:
            try:
                self.connect()
                self.connected = True
                self.check_event(CallbackServer.SERVER_CONNECT)
                break
            except:
                sleep(5)

        if self.abort:
            return

        # If we've already defined callbacks then we know which events we're
        # listening out for
        if self.notifications:
            nots = ",".join(self.notifications)
            self.request("subscribe {}".format(nots))

        # If not, let's just listen for everything.
        else:
            self.request("listen")

        while not self.abort:
            try:
                # Include a timeout to stop blocking if no server
                data = self.telnet.read_until(self.ending, timeout=1)[:-1]

                # We've got a notification, so let's see if it's one we're
                # watching.
                if data:
                    self.check_event(data)

            # Server is unavailable so exit gracefully
            except EOFError:
                self.check_event(CallbackServer.SERVER_ERROR)
                self.run()

        self.telnet.close()
        del self.telnet
