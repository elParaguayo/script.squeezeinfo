"""
An asynchronous client that listens to messages broadcast by the server.

The client also accepts callback functions.

The client subclasses python threading so methods are built-in to the class
object.
"""
from threading import Thread
from telnetlib import IAC, NOP
import socket
from time import sleep

from .server import Server


class CallbackServer(Server, Thread):

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

    def __init__(self, **kwargs):
        super(CallbackServer, self).__init__(**kwargs)
        self.callbacks = {}
        self.notifications = []
        self.abort = False
        self.ending = "\n".encode(self.charset)
        self._server = self.get_server()
        self.connected = False
        self.daemon = True

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
                self.callbacks[cb](self.unquote(event))
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
