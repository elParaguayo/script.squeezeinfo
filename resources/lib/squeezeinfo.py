# -*- coding: utf-8 -*-
import os
from threading import Thread, Lock
from time import sleep
from urllib import quote_plus

import xbmc, xbmcgui, xbmcaddon
from kodi65.actionhandler import ActionHandler

from .customhomemenu import CUSTOM_MENU
from .image_cache import ImageCache
from .pylms.callbackserver import CallbackServer
from .simplelms.artworkresolver import ArtworkResolver
from .simplelms.simplelms import LMSServer
from .simplelms.menu import LMSMenuHandler
from .simplelms.menuitems import menu_type as lms_menu_type

# Debugging level
DEBUG_LEVEL = xbmc.LOGDEBUG

# Initialise addon and get some basic info
_A_ = xbmcaddon.Addon()
_S_ = _A_.getSetting
ADDON_PATH = _A_.getAddonInfo("path")
ADDON_ID = _A_.getAddonInfo("id")
ADDON_PROFILE = xbmc.translatePath(_A_.getAddonInfo('profile')).decode('utf-8')

# Get key settings
LMS_SERVER = _S_("server_ip")
LMS_TELNET = int(_S_("telnet_port"))
LMS_WEB = int(_S_("web_port"))

# Define some paths and variable names for our images
CACHE_PATH = os.path.join(ADDON_PROFILE, "cache")
IMG_BACKGROUND = "backgrounds"
IMG_ICON = "icons"
IMG_PROGRESS = "swatch"

CONTROL_DEFAULT = 10
CONTROL_PLAYLIST = 50
CONTROL_MENU_GROUP = 100
CONTROL_MENU = 101
CONTROL_MENU_PLAY = 414141
CONTROL_AUDIO_SUBMENU = 410100
CONTROL_SEARCH_SUBMENU = 410101
CONTROL_PLAYER_CONTROL = 410500
SKIN_CONTROLS = [CONTROL_PLAYLIST, CONTROL_MENU, CONTROL_MENU_GROUP, CONTROL_MENU_PLAY, 1011, 1012, 1013]

SUBMENU_AUDIO_TYPES = ["audio", "playlist"]
SUBMENU_SEARCH_TYPES = ["search"]
SUBMENUS = {CONTROL_AUDIO_SUBMENU:
               [("Play", "play"),
                ("Play Next", "playnext"),
                ("Queue", "add")],
            CONTROL_SEARCH_SUBMENU:
                [("Search", "search")]
            }

PLAYER_CONTROLS = [("previous", "Previous Track"),
                   ("playpause", "Play/Pause"),
                   ("stop", "Stop"),
                   ("next", "Next Track"),
                   ("volume", "Adjust Volume")]

# Initialise the action handler
ch = ActionHandler()


def debug(message, level=DEBUG_LEVEL):
    """Basic debug function for outputting info to the log.

      Should not use anything higher than debug to avoid spamming the logfile.
    """
    # Make sure encoding is ok for log file
    if isinstance (message, str):
        message = message.decode("utf-8")

    # Format the message and send to the logfile
    message = u"{}: {}".format(ADDON_ID, message)
    xbmc.log(msg=message.encode("utf-8"), level=level)


class SqueezeInfo(xbmcgui.WindowXML):
    """Window class definition for showing now playing information from a
       Logitech Media Server.
    """

    def __init__(self,strXMLname, strFallbackPath, strDefaultName,
                 forceFallback):

        # Define some basic variables
        debug("Initialising screen and defining variables...")
        self.player = None
        self.players = None
        self.cur_player = None
        self.lock = Lock()
        self.duration = 0
        self.elapsed = 0
        self.playing = False
        self.connected = False
        self.abort = False
        self.show_playlist = False
        self.show_menu = False
        self.menu_history = []
        self.server_connected = False
        self.has_playlist = False
        self.has_player = False


        # Set the location of the server
        self.hostname = LMS_SERVER
        self.telnet_port = LMS_TELNET
        self.web_port = LMS_WEB

        # Get a basic server object for retrieving data
        self.cmdserver = LMSServer(host=self.hostname, port=self.web_port)

        # Get the artwwork resolver to create urls for now playing tracks
        # The ImageCache processes images and saves to userdata folder
        debug("Creating artwork resolver and cache")
        self.awr = ArtworkResolver(host=self.hostname, port=self.web_port)
        self.cache = ImageCache()

        # Create a callback server to receive asynchronous announcements from
        # the server
        debug("Creating callback server")
        self.cbserver = CallbackServer(hostname=self.hostname,
                                       port=self.telnet_port)
        self.cbserver.daemon = True

        # Define the events that we want to listen for and assign callbacks
        debug("Adding callbacks")
        self.cbserver.add_callback(CallbackServer.PLAYLIST_CHANGED,
                                   callback=self.track_changed)
        self.cbserver.add_callback(CallbackServer.PLAYLIST_CHANGE_TRACK,
                                   callback=self.track_changed)
        self.cbserver.add_callback(CallbackServer.SERVER_ERROR,
                                   callback=self.no_server)
        self.cbserver.add_callback(CallbackServer.SERVER_CONNECT,
                                   callback=self.server_connect)
        self.cbserver.add_callback(CallbackServer.VOLUME_CHANGE,
                                   callback=self.vol_change)
        self.cbserver.add_callback(CallbackServer.PLAY_PAUSE,
                                   callback=self.play_pause)
        self.cbserver.add_callback(CallbackServer.CLIENT_ALL,
                                   callback=self.client_change)

    def onInit(self):
        # Once window has been initialised we can start setting properties
        debug("OnInit called")
        debug("OnInit - Setting windowID and properties")
        self.windowID = xbmcgui.getCurrentWindowId()
        self.setProperty("SQUEEZEINFO_SERVER_CONNECTED", "true")
        self.setProperty("SQUEEZEINFO_HAS_PLAYER", "false")
        self.setProperty("SQUEEZEINFO_HAS_NEXT_TRACK", "false")
        self.setProperty("SQUEEZEINFO_SHOW_MENU", "false")
        self.setProperty("SQUEEZEINFO_SHOW_CONTROLS", "false")
        self.setProperty("SQUEEZE_IMAGE_FOLDER",
                         os.path.join(CACHE_PATH, IMG_ICON))

        self.playlistbox = self.getControl(CONTROL_PLAYLIST)
        self.playlistbox.setVisibleCondition("String.IsEqual(Window.Property(SQUEEZEINFO_SHOW_PLAYLIST),true)")

        self.menubox = self.getControl(CONTROL_MENU_GROUP)
        self.menubox.setVisibleCondition("String.IsEqual(Window.Property(SQUEEZEINFO_SHOW_MENU),true)")

        self.playercontrols = self.getControl(410400)
        self.playercontrols.setVisibleCondition("String.IsEqual(Window.Property(SQUEEZEINFO_SHOW_CONTROLS),true)")

        self.audiosubmenu = self.getControl(CONTROL_AUDIO_SUBMENU)
        self.searchsubmenu = self.getControl(CONTROL_SEARCH_SUBMENU)
        self.build_submenus()
        self.build_player_controls()
        # self.submenubox.setVisibleCondition("String.IsEqual(Container(101).ListItem(0).Property(showsubmenu),true)")

        # Let's see if the server is working
        debug("OnInit - Getting server")
        self.get_server()

        # If the server's available then we need to see if there are any
        # squeezeplayers
        if self.server_connected:
            debug("OnInit - getting players")
            self.get_squeeze_players()
        else:
            debug("OnInit - no players")

        # ...and if we've got a player then we should get the metadata
        if self.player:
            debug("Player found: get track info.")
            self.get_info()

            # Check if track is playing
            debug("OnInit - getting player state")
            try:

                self.playing = self.player.get_mode() == "play"
                debug("OnInit - player status: {}".format(self.playing))
            except:
                debug("OnInit - player state error - setting as False")
                self.playing = False

        # Get the progress bar control reference
        self.progress = self.getControl(41)
        debug("OnInit - Progress control: {}".format(self.progress))
        debug("OnInit - starting progress bar thread")

        # Start a thread to update the progress bar
        track_progress = Thread(target=self.show_progress)
        track_progress.daemon = True
        track_progress.start()

        # Start the callback server to listen for events
        debug("OnInit - starting callback server")
        self.cbserver.start()

    def onAction(self, action):
        # Let the action handler deal with this using decorators on methods
        ch.serve_action(action, self.getFocusId(), self)

    def onClick(self, controlID):
        pass

    def onFocus(self, controlID):
        pass

    def setProperty(self, propname, value):
        """Simple method for setting window properties."""
        debug(u"Setting property {} = {}".format(propname, value))
        xbmcgui.Window(self.windowID).setProperty(propname, value)

    def clearProperty(self, propname):
        """Simple method for clearing window properties."""
        debug("Clearing property {}".format(propname))
        xbmcgui.Window(self.windowID).clearProperty(propname)

    def set_default_focus(self):
        self.setFocusId(CONTROL_DEFAULT)

    def get_server(self):
        """Method to check whether Logitech Media Server is online.

           Returns True if online and False if not.
        """
        debug("Checking server connection...")
        connected = self.cmdserver.ping()
        debug("Server is {}connected".format("" if connected else "not "))
        state = "true" if connected else "false"
        self.setProperty("SQUEEZEINFO_SERVER_CONNECTED", state)
        self.server_connected = connected

    def get_cur_player(self):
        """Method to get the current player. If the last used player is no
           longer available then a new player is assigned to be the current
           player.

           Returns a player object.
        """
        debug("Getting current player.")
        if self.cur_player in self.players:
            debug("Current player found in list of players")
            return self.players[self.players.index(self.cur_player)]

        else:
            debug("Current player not found. Setting new default player")
            pl = self.players[0]
            self.cur_player = str(pl.ref)
            return pl

    def get_squeeze_players(self):
        """Method to obtain list of squeezeplayers connected to the server.

           Method assigns result to self.players and does not return any output.
        """
        debug("Getting list of available players")

        # Server needs to be online. If it's not, try connecting one last time.
        if not self.server_connected:
            self.get_server()

        # If the server is online then get the players
        if self.server_connected:
            self.players = self.cmdserver.get_players()
            debug("{} available players: {}".format(len(self.players),
                                                    self.players))

            if self.players:
                # Setting this property will cause the "Now Playing" bar to be
                # displayed on the skin.
                self.setProperty("SQUEEZEINFO_HAS_PLAYER", "true")
                self.has_player = True
                self.player = self.get_cur_player()
                self.setProperty("SQUEEZEINFO_PLAYER_NAME", self.player.name)
                self.set_vol_label()
                self.get_sync_groups()

            else:
                # No players so we need to hide the "Now Playing" bar
                self.setProperty("SQUEEZEINFO_HAS_PLAYER", "false")
                self.has_player = False
        else:
            debug("Can't connect to server. No players.")
            self.players = []

    def get_info(self):
        """Method to get track information from the current player."""
        debug("Getting track info.")
        try:
            debug("Retrieving playlist info for player {}...".format(self.player))

            # Get the current and next track info
            # (hard coded 2 tracks for now)
            track = self.player.playlist_get_current_detail(amount=2)
            debug("{} track(s) found.\n{}".format(len(track), track))

        # If we can't get track info then we need to exit this method
        except AttributeError:
            debug("get_info: AttributeError - exiting.")
            return

        # If there's at least one track then we can display the Now Playing info
        if len(track) > 0:
            self.set_now_playing(track[0])
        else:
            self.setProperty("SQUEEZEINFO_HAS_PLAYLIST", "false")
            self.has_playlist = False

        # If there are two tracks then we should display the next track too
        if len(track) == 2:
            self.setProperty("SQUEEZEINFO_HAS_NEXT_TRACK", "true")
            self.set_next_up(track[1])

        # or hide the next track info if there's no track.
        else:
            self.setProperty("SQUEEZEINFO_HAS_NEXT_TRACK", "false")

        # Get track progress information
        try:
            e, d = self.player.get_track_elapsed_and_duration()
        except:
            e = d = 0.0

        # These variables can be written in other places so let's make sure it
        # only happens at one time with a Lock
        with self.lock:
            self.elapsed = e
            self.duration = d

        # If the now playing bar is currently hidden, we only want to show it
        # after the data has been populated.
        if track:
            self.setProperty("SQUEEZEINFO_HAS_PLAYLIST", "true")
            self.has_playlist = True

    def get_metadata(self, track, process_image=True):
        """Method to output the track metadata."""
        title = track.get("title", "Unknown Track")
        album = track.get("album", "Unknown Album")
        artist = track.get("artist", "Unknown Artist")

        debug("Metadata: {}".format(track))

        # Use the ArtworkResolver to get the URL for the track.
        debug("Getting artwork url...")
        try:
            url = self.awr.getURL(track)
        except:
            debug("Error in artwork resolver")
            url = ""

        # By default, we'll use the URL for the image (but we'll see if we can
        # process it below)
        img_icon = url
        img_bg = url

        debug("Artwork url: {}".format(url))

        if process_image:

            # Despite the name this image cache also handles the image processing.
            try:
                debug("Getting cached image paths.")
                img_bg = self.cache.getCachedImage(url, IMG_BACKGROUND)

                # For some reason, the cache isn't loading for the icon so we'll
                # use the url for now...
                # img_icon = self.cache.getCachedImage(url, IMG_ICON)
            except:
                debug("Error retrieving cache paths")

        # Return the necessary metadata
        return title, album, artist, img_icon, img_bg

    def set_now_playing(self, track):
        """Method to set window properties for the current track."""
        debug("Setting now playing track info")
        title, album, artist, icon, bg = self.get_metadata(track)
        pos = track.get("playlist index", -1)
        self.setProperty("SQUEEZEINFO_NP_TITLE", title)
        self.setProperty("SQUEEZEINFO_NP_ARTIST", artist)
        self.setProperty("SQUEEZEINFO_NP_ALBUM", album)
        self.setProperty("SQUEEZEINFO_NP_BACKGROUND", bg)
        self.setProperty("SQUEEZEINFO_NP_ICON", icon)
        self.setProperty("SQUEEZEINFO_CURRENT_TRACK", str(pos + 1))

    def set_next_up(self, track):
        """Method to set window properties for the next track."""
        debug("Setting next track info")
        title, album, artist, icon, _ = self.get_metadata(track)
        self.setProperty("SQUEEZEINFO_NEXT_TITLE", title)
        self.setProperty("SQUEEZEINFO_NEXT_ARTIST", artist)
        self.setProperty("SQUEEZEINFO_NEXT_ALBUM", album)
        self.setProperty("SQUEEZEINFO_NEXT_ICON", icon)

    def getCallbackPlayer(self, event):
        """Return the player reference from the callback event."""
        player = self.cur_player if event is None else event.split(" ")[0]
        debug("Callback player ref: {}".format(player))
        return player

    def cur_or_sync(self, ref):
        """Method to determine if the event player is our player or in a sync
           group with our player.
        """
        if ref == self.cur_player:
            debug("Event matches current player")
            return True

        else:
            debug("Checking event in sync groups")
            for gr in self.sync_groups:
                if ref in gr and self.cur_player in gr:
                    debug("Event from player in sync group")
                    return True

        debug("Event doesn't match player or sync group")
        return False

    def get_sync_groups(self):
        """Method to retrieve sync groups defined on the server."""
        try:
            self.sync_groups = self.cmdserver.get_sync_groups()
        except:
            self.sync_groups = []

        debug("Sync groups: {}".format(self.sync_groups))

    def track_changed(self, event=None):
        """Method to trigger actions when a new track is triggered on server."""
        debug("track_changed")
        debug(event)
        if self.cur_or_sync(self.getCallbackPlayer(event)):
            self.get_info()

    def no_server(self, event=None):
        """Method to trigger actions when server becomes unavailable."""
        debug("no_server: {}".format(event))
        self.setProperty("SQUEEZEINFO_SERVER_CONNECTED", "false")

    def server_connect(self, event=None):
        """Method to trigger actions when server becomes available."""
        debug("server_connect: {}".format(event))
        self.setProperty("SQUEEZEINFO_SERVER_CONNECTED", "true")
        self.get_squeeze_players()

    def play_pause(self, event=None):
        """Method to trigger actions when player state changes."""
        debug("play_pause: {}".format(event))
        if self.cur_or_sync(self.getCallbackPlayer(event)):
            if event.split()[3] == "1":
                self.playing = False
            else:
                self.playing = True
            debug("Player playing state now: {}".format(self.playing))

    def client_change(self, event=None):
        """Method to trigger actions when client connects or disconnects."""
        debug("client_change: {}".format(event))
        self.get_squeeze_players()
        if self.players:
            self.get_info()

    def vol_change(self, event=None):
        """Method to trigger actions when volume changes."""
        if self.getCallbackPlayer(event) == self.cur_player:
            self.set_vol_label()

    def change_player(self, step):
        self.setProperty("SQUEEZEINFO_CHANGE_PLAYER", "false")
        sleep(0.05)
        debug("Changing player. Index step {}".format(step))
        index = self.players.index(self.cur_player)
        index = (index + step) % len(self.players)
        self.player = self.players[index]
        self.cur_player = str(self.player.ref)
        debug("New player: {}".format(self.player.name))
        debug("Updating screen...")
        self.setProperty("SQUEEZEINFO_PLAYER_NAME", self.player.name)
        self.setProperty("SQUEEZEINFO_CHANGE_PLAYER", "true")
        self.get_info()

    def set_vol_label(self):
        label = "{}%".format(self.player.get_volume())
        self.setProperty("SQUEEZEINFO_PLAYER_VOLUME", label)

    def vol_up(self):
        """Method to increase current player's volume."""
        try:
            self.player.volume_up()
            self.set_vol_label()

        except:
            pass

    def vol_down(self):
        """Method to decrease current player's volume."""
        try:
            self.player.volume_down()
            self.set_vol_label()
        except:
            pass

    def get_text(self, heading):
        text = xbmcgui.Dialog().input(heading, type=xbmcgui.INPUT_ALPHANUM)
        return text

    def display_playlist(self, hide=False):

        if hide:
            self.show_playlist = False
            self.setProperty("SQUEEZEINFO_SHOW_PLAYLIST", "false")
            self.set_default_focus()
        else:
            if not self.has_playlist:
                return
            self.set_playlist()
            self.show_playlist = True
            self.setProperty("SQUEEZEINFO_SHOW_PLAYLIST", "true")
            listbox = self.getControl(50)
            debug("Listbox control: {}".format(listbox))
            sleep(0.6)
            self.setFocus(listbox)

    def display_menu(self, hide=False):
        if hide:
            self.show_menu = False
            current_item = self.getControl(CONTROL_MENU).getSelectedItem()
            current_item.setProperty("showaudiosubmenu", "false")
            current_item.setProperty("showsearchsubmenu", "false")
            self.setProperty("SQUEEZEINFO_SHOW_MENU", "false")
            self.setFocusId(CONTROL_DEFAULT)
        else:
            if not self.has_player:
                return
            self.set_menu()
            self.show_menu = True
            self.setProperty("SQUEEZEINFO_SHOW_MENU", "true")
            sleep(0.6)
            self.setFocusId(CONTROL_MENU)

    def menu_back(self):
        menucmd = None

        if len(self.menu_history) > 1:
            self.menu_history.pop()
            menucmd = self.menu_history.pop()
        else:
            self.menu_history = []

        self.set_menu(menucmd)
        sleep(0.1)
        self.setFocusId(CONTROL_MENU)

    def menu_action(self):
        menu = self.getControl(CONTROL_MENU)
        item = menu.getSelectedItem()
        if item.getProperty("Type") in ["menu", "playlist"]:
            self.set_menu(item.getProperty("cmd"))
            sleep(0.1)
            self.setFocusId(CONTROL_MENU)

    def submenu_action(self, controlid):
        menu = self.getControl(CONTROL_MENU)
        menuitem = menu.getSelectedItem()

        submenu = self.getControl(controlid)
        item = submenu.getSelectedItem()
        action = item.getProperty("action")

        if controlid == CONTROL_AUDIO_SUBMENU:
            cmd = menuitem.getProperty(action)
            self.player.request(cmd)

        elif controlid == CONTROL_SEARCH_SUBMENU:
            text = self.get_text("Enter search terms...")
            if text:
                text = quote_plus(text)
                cmd = menuitem.getProperty("search")
                debug("COMMAND: {}".format(cmd), level=xbmc.LOGNOTICE)
                cmd = cmd.replace("__TAGGEDINPUT__", text)
                debug("COMMAND_REPLACE: {}".format(cmd), level=xbmc.LOGNOTICE)
                self.set_menu(menucmd=cmd)
                sleep(0.5)
                self.setFocusId(CONTROL_MENU)
                self.getControl(CONTROL_MENU).selectItem(0)

    def display_submenu(self):
        menu = self.getControl(CONTROL_MENU)
        item = menu.getSelectedItem()
        it_type = item.getProperty("Type")
        if it_type in ["audio", "playlist"]:
            self.setFocusId(CONTROL_AUDIO_SUBMENU)
        elif it_type in ["search"]:
            self.setFocusId(CONTROL_SEARCH_SUBMENU)

    def set_playlist(self):
        listbox = self.getControl(CONTROL_PLAYLIST)

        listbox.reset()

        pl_items = self.player.playlist_get_detail()

        items = []

        for i, plitm in enumerate(pl_items):
            item = xbmcgui.ListItem()
            title, _, artist, icon, _ = self.get_metadata(plitm,
                                                          process_image=False)
            item.setInfo("music", {"tracknumber": i + 1, "Title": title, "Artist": artist})
            item.setIconImage(icon)
            items.append(item)

        listbox.addItems(items)

        pos = self.player.playlist_get_position()
        listbox.selectItem(pos)

    def set_menu(self, menucmd=None):
        handle = LMSMenuHandler(self.player)
        menubox = self.getControl(CONTROL_MENU)

        if not menucmd:
            menu = handle.getCustomMenu(CUSTOM_MENU)
        else:
            self.menu_history.append(menucmd)
            menu = handle.getMenu(menucmd=menucmd)

        menubox.reset()

        items = []

        for item in menu:
            l_item = xbmcgui.ListItem()
            m_type = lms_menu_type(item)
            play = getattr(item, "cmd_play", "")
            playnext = getattr(item, "cmd_play_next", "")
            add = getattr(item, "cmd_add", "")
            search = getattr(item, "cmd_search", "")
            if m_type == "playlist":
                cmd = item.show_items_cmd
            else:
                cmd = item.cmdstring

            if m_type in SUBMENU_AUDIO_TYPES:
                showaudiosubmenu = "true"
            else:
                showaudiosubmenu = "false"

            if m_type in SUBMENU_SEARCH_TYPES:
                showsearchsubmenu = "true"
                debug("SEARCH_COMMAND: {}".format(search), level=xbmc.LOGNOTICE)
            else:
                showsearchsubmenu = "false"

            lines = item.text.split("\n")
            if len(lines) > 1:
                l_item.setProperty("multiline", "true")
                l_item.setLabel(lines[0])
                l_item.setLabel2(lines[1])
            else:
                l_item.setProperty("multiline", "false")
                l_item.setLabel(lines[0])

            l_item.setInfo("music", {"Title": item.text})
            l_item.setProperty("Type", m_type)
            l_item.setProperty("cmd", cmd)
            l_item.setProperty("play", play)
            l_item.setProperty("playnext", playnext)
            l_item.setProperty("add", add)
            l_item.setProperty("search", search)
            l_item.setProperty("showaudiosubmenu", showaudiosubmenu)
            l_item.setProperty("showsearchsubmenu", showsearchsubmenu)
            l_item.setIconImage(item.icon)
            items.append(l_item)

        menubox.addItems(items)

    def _build_submenu(self, control, items):
        submenu = self.getControl(control)
        submenu.reset()
        for item in items:
            l = xbmcgui.ListItem()
            l.setLabel(item[0])
            l.setProperty("action", item[1])
            submenu.addItem(l)

    def build_submenus(self):
        for control, items in SUBMENUS.iteritems():
            self._build_submenu(control, items)

    def build_player_controls(self):
        control = self.getControl(CONTROL_PLAYER_CONTROL)
        control.reset()
        for item_name, item_label in PLAYER_CONTROLS:
            l = xbmcgui.ListItem()
            l.setProperty("action", item_name)
            l.setLabel(item_label)
            debug("squeezeinfo-{}.png".format(item_name), level=xbmc.LOGNOTICE)
            l.setIconImage("squeezeinfo-{}.png".format(item_name))
            control.addItem(l)
        control.setVisibleCondition("true")

    # def set_submenu(self, menutype=None):
    #     debug(menutype, level=xbmc.LOGNOTICE)
    #     menu = {"audio":
    #                [("Play", "play"),
    #                 ("Play Next", "playnext"),
    #                 ("Queue", "add")],
    #             "playlist":
    #                [("Play", "play"),
    #                 ("Play Next", "playnext"),
    #                 ("Queue", "add")],
    #             "search":
    #                 [("Search", "search")]
    #             }
    #
    #     if menutype in menu:
    #         self.submenubox.reset()
    #
    #         for item in menu[menutype]:
    #             l = xbmcgui.ListItem()
    #             l.setLabel(item[0])
    #             l.setProperty("action", item[1])
    #             self.submenubox.addItem(l)
    #
    #         return True
    #
    #     else:
    #
    #         return False


    def show_progress(self):
        """Method to increase progress bar state. Should be run as a thread to
           prevent blocking.
        """

        # No debugs here to avoid massive spamming

        i = 0

        # start a loop which stops when Kodi exits
        while not (xbmc.abortRequested or self.abort):

            # Every 20 cycles we make request to the server to check..
            if not (i % 20):
                try:
                    # ... playing status
                    self.playing = self.player.get_mode() == "play"
                except:
                    self.playing = False

                try:
                    # ... track position
                    e, d = self.player.get_track_elapsed_and_duration()
                except:
                    e = d = 0.0

                with self.lock:
                    self.elapsed = e
                    self.duration = d

                debug(self.getControl(CONTROL_PLAYER_CONTROL).getPosition(), level=xbmc.LOGNOTICE)

            # Otherwise, just manually increase progress bar
            else:
                if self.playing:
                    with self.lock:
                        self.elapsed += 0.25

            try:
                percent = float(self.elapsed/self.duration) * 100
            except:
                percent = 0

            # Draw the new progress bar state
            self.progress.setPercent(percent)

            # Increment our counter
            i = (i + 1) % 20

            # And sleep...
            sleep(0.25)

        if not self.abort:
            self.exit("*")

    ############ ACTIONS #######################################################

    ## Now Playing #############################################################

    @ch.action("parentdir", CONTROL_DEFAULT)
    @ch.action("previousmenu", CONTROL_DEFAULT)
    @ch.action("previousmenu", CONTROL_PLAYER_CONTROL)
    def exit(self, controlid):
        self.cbserver.abort = True
        self.cbserver.join()
        if not self.abort:
            self.abort = True
        del self.cbserver
        del self.cmdserver
        del self.awr
        del self.cache
        del self.player
        self.close()

    @ch.action("left", CONTROL_DEFAULT)
    def on_left(self, controlid):
        self.change_player(-1)

    @ch.action("right", CONTROL_DEFAULT)
    def on_right(self, controlid):
        self.change_player(1)

    @ch.action("number0", CONTROL_DEFAULT)
    @ch.action("number0", CONTROL_PLAYLIST)
    def toggle_playlist(self, controlid):
        if self.show_playlist:
            self.display_playlist(hide=True)
        else:
            self.display_playlist()

    @ch.action("number9", CONTROL_DEFAULT)
    def toggle_menu(self, controlid):
        if self.show_menu:
            self.show_menu = False
            self.setProperty("SQUEEZEINFO_SHOW_MENU", "false")
            self.setFocusId(10)
        else:
            self.set_menu()
            self.show_menu = True
            self.setProperty("SQUEEZEINFO_SHOW_MENU", "true")
            sleep(0.6)
            self.setFocusId(CONTROL_MENU)

    @ch.action("number8", CONTROL_DEFAULT)
    def show_player_controls(self, controlid):
        self.setProperty("SQUEEZEINFO_SHOW_CONTROLS","true")
        sleep(0.1)
        self.setFocusId(CONTROL_PLAYER_CONTROL)

    ## Playlist ################################################################

    @ch.action("parentdir", CONTROL_PLAYLIST)
    @ch.action("previousmenu", CONTROL_PLAYLIST)
    def close_playlist(self, controlid):
        self.display_playlist(hide=True)

    @ch.action("select", CONTROL_PLAYLIST)
    def click_playlist(self, controlid):
        listbox = self.getControl(controlid)
        index = listbox.getSelectedPosition()
        self.player.playlist_play_index(index)

    ## Squeezemenu #############################################################

    @ch.action("right", CONTROL_MENU)
    def show_submenu(self, controlid):
        self.display_submenu()

    @ch.action("previousmenu", CONTROL_MENU)
    def close_menu(self, controlid):
        self.menu_history = []
        self.display_menu(hide=True)

    @ch.action("parentdir", CONTROL_MENU)
    def previous_menu(self, controlid):
        if self.menu_history:
            self.menu_back()
        else:
            self.close_menu(controlid)

    @ch.action("select", CONTROL_MENU)
    def menu_select(self, controlid):
        self.menu_action()

    ## Squeezemenu - submenu ###################################################

    @ch.action("parentdir", CONTROL_AUDIO_SUBMENU)
    @ch.action("parentdir", CONTROL_SEARCH_SUBMENU)
    def submenu_back(self, controlid):
        if self.menu_history:
            self.menu_back()
            self.setFocusId(CONTROL_MENU)
        else:
            self.close_menu(controlid)

    @ch.action("previousmenu", CONTROL_AUDIO_SUBMENU)
    @ch.action("previousmenu", CONTROL_SEARCH_SUBMENU)
    def close_submenu(self, controlid):
        self.menu_history = []
        self.display_menu(hide=True)

    @ch.action("select", CONTROL_AUDIO_SUBMENU)
    @ch.action("select", CONTROL_SEARCH_SUBMENU)
    def clickaction(self, controlid=None):
        self.submenu_action(controlid)

    ## Player controls #########################################################

    @ch.action("up", CONTROL_PLAYER_CONTROL)
    def pl_vol_up(self, controlid):
        control = self.getControl(controlid)
        action = control.getSelectedItem().getProperty("action")
        if action == "volume":
            self.vol_up()

    @ch.action("down", CONTROL_PLAYER_CONTROL)
    def pl_vol_up(self, controlid):
        control = self.getControl(controlid)
        action = control.getSelectedItem().getProperty("action")
        if action == "volume":
            self.vol_down()

    @ch.action("select", CONTROL_PLAYER_CONTROL)
    def player_control_select(self, controlid):
        control = self.getControl(controlid)
        action = control.getSelectedItem().getProperty("action")

        if not self.has_player:
            return

        if action == "previous":
            self.player.prev()

        elif action == "playpause":
            self.player.toggle()

        elif action == "stop":
            self.player.stop()

        elif action == "next":
            self.player.next()

    @ch.action("previousmenu", CONTROL_PLAYER_CONTROL)
    @ch.action("previousmenu", CONTROL_PLAYER_CONTROL)
    def close_player_controls(self, controlid):
        self.setProperty("SQUEEZEINFO_SHOW_CONTROLS","false")
        sleep(0.1)
        self.setFocusId(CONTROL_DEFAULT)
