# -*- coding: utf-8 -*-
import xbmc, xbmcgui, xbmcaddon
import os
import uuid
import errno
from random import uniform
from time import sleep
from threading import Thread, Lock

from ActionHandler import ActionHandler

from .pylms.callbackserver import CallbackServer
from .pylms.artworkresolver import ArtworkResolver
from .image_cache import ImageCache
from .simplelms.simplelms import LMSServer

DEBUG_LEVEL = xbmc.LOGDEBUG

_A_ = xbmcaddon.Addon()
_S_ = _A_.getSetting

ADDON_PATH = _A_.getAddonInfo("path")
ADDON_PROFILE = xbmc.translatePath(_A_.getAddonInfo('profile')).decode('utf-8')

LMS_SERVER = _S_("server_ip")
LMS_TELNET = int(_S_("telnet_port"))
LMS_WEB = int(_S_("web_port"))

CACHE_PATH = os.path.join(ADDON_PROFILE, "cache")

IMG_BACKGROUND = "backgrounds"
IMG_ICON = "icons"
IMG_PROGRESS = "swatch"

ACTION_PREVIOUS_MENU = 10
ACTION_NAV_BACK = 92
CLOSING_ACTION = [ACTION_PREVIOUS_MENU, ACTION_NAV_BACK]

ACTION_VOLUME_UP = xbmcgui.ACTION_VOLUME_UP
ACTION_VOLUME_DOWN = xbmcgui.ACTION_MOVE_DOWN


ch = ActionHandler()


def debug(message):
    if isinstance (message, str):
        message = message.decode("utf-8")

    message = u"SQUEEZEINFO: {}".format(message)
    xbmc.log(msg=message.encode("utf-8"), level=DEBUG_LEVEL)

class SqueezeInfo(xbmcgui.WindowXML):

    def __init__(self,strXMLname, strFallbackPath, strDefaultName, forceFallback):
        # Changing the three varibles passed won't change, anything
        # Doing strXMLname = "bah.xml" will not change anything.
        # don't put GUI sensitive stuff here (as the xml hasn't been read yet
        # Idea to initialize your variables here
        #super(SqueezeInfo, self).__init__()
        debug("Initialising screen")
        self.player = None
        self.players = None
        self.cur_player = None
        self.lock = Lock()
        self.duration = 0
        self.elapsed = 0
        self.playing = False
        self.connected = False

        self.hostname = LMS_SERVER
        self.telnet_port = LMS_TELNET
        self.web_port = LMS_WEB

        self.cmdserver = LMSServer(host=self.hostname, port=self.web_port)

        debug("Creating artwork resolver and cache")
        self.awr = ArtworkResolver(host=self.hostname, port=self.web_port)
        self.cache = ImageCache()

        debug("Creating callback server")
        self.cbserver = CallbackServer(hostname=self.hostname, port=self.telnet_port)
        self.cbserver.daemon = True

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
        # Put your List Populating code/ and GUI startup stuff here
        debug("OnInit called")
        debug("OnInit - Setting windowID and properties")
        self.windowID = xbmcgui.getCurrentWindowId()
        self.setProperty("SQUEEZEINFO_SERVER_CONNECTED", "true")
        self.setProperty("SQUEEZEINFO_HAS_PLAYER", "false")
        self.setProperty("SQUEEZEINFO_HAS_NEXT_TRACK", "false")

        self.setProperty("SQUEEZE_IMAGE_FOLDER", os.path.join(CACHE_PATH, IMG_ICON))

        debug("OnInit - Getting server")
        self.get_server()

        if self.server_connected:
            debug("OnInit - getting players")
            self.get_squeeze_players()
        else:
            debug("OnInit - no players")

        if self.player:
            debug("OnInit - getting player state")
            try:
                self.playing = self.player.get_mode() == "play"
                debug("OnInit - player status: {}".format(self.playing))
            except:
                debug("OnInit - player state error - setting as False")
                self.playing = False

        debug("OnInit - starting callback server")
        self.cbserver.start()

        self.progress = self.getControl(41)
        debug("OnInit - Progress control: {}".format(self.progress))
        debug("OnInit - starting progress bar thread")
        track_progress = Thread(target=self.show_progress)
        track_progress.daemon = True
        track_progress.start()

        if self.player:
            debug("Player found: get track info.")
            self.get_info()

    def onAction(self, action):

        act = action.getId()

        if act in CLOSING_ACTION:
            debug("Action {} is a closing action. Closing window.".format(action.getId()))
            self.close()
        # elif act == ACTION_VOLUME_UP:
        #     debug("Volume Up!")
        #     self.vol_up()
        # elif act == ACTION_VOLUME_DOWN:
        #     debug("Volume Down!")
        #     self.vol_down()
        else:
            # debug("Unhandled action ID: {}".format(action.getId()))
            ch.serve_action(action, self.getFocusId(), self)

        return

    def onClick(self, controlID):
        """
            Notice: onClick not onControl
            Notice: it gives the ID of the control not the control object
        """
        pass

    def onFocus(self, controlID):
        pass

    def setProperty(self, propname, value):
        debug(u"Setting property {} = {}".format(propname, value))
        xbmcgui.Window(self.windowID).setProperty(propname, value)

    def clearProperty(self, propname):
        debug("Clearing property {}".format(propname))
        xbmcgui.Window(self.windowID).clearProperty(propname)

    def get_server(self):
        debug("Checking server connection...")
        connected = self.cmdserver.ping()
        debug("Server is {}connected".format("" if connected else "not "))
        state = "true" if connected else "false"
        self.setProperty("SQUEEZEINFO_SERVER_CONNECTED", state)
        self.server_connected = connected

    def get_cur_player(self):
        debug("Getting current player.")
        if self.cur_player in self.players:
            debug("Current player found in list of players")
            return self.players[self.players.index(self.cur_player)]

        else:
            debug("Current player not found. Setting new default player")
            debug("{} {}".format(self.cur_player, self.players))
            debug("{} {}".format(self.cur_player in self.players, type(self.cur_player)))
            pl = self.players[0]
            self.cur_player = str(pl.ref)
            return pl

    def get_squeeze_players(self):
        debug("Getting list of available players")
        if not self.server_connected:
            self.get_server()

        if self.server_connected:
            self.players = self.cmdserver.get_players()
            debug("{} available players: {}".format(len(self.players), self.players))

            if self.players:
                self.setProperty("SQUEEZEINFO_HAS_PLAYER", "true")
                self.player = self.get_cur_player()
                self.get_sync_groups()

            else:
                self.setProperty("SQUEEZEINFO_HAS_PLAYER", "false")
        else:
            debug("Can't connect to server. No players.")
            self.players = []

    def get_info(self):
        debug("Getting track info.")
        try:
            debug("Retrieving playlist info for player {}...".format(self.player))
            track = self.player.playlist_get_current_detail(amount=2)
            debug("{} track(s) found.\n{}".format(len(track), track))

        except AttributeError:
            debug("get_info: AttributeError - exiting.")
            return

        if len(track) > 0:
            self.set_now_playing(track[0])

        if len(track) == 2:
            self.setProperty("SQUEEZEINFO_HAS_NEXT_TRACK", "true")
            self.set_next_up(track[1])
        else:
            self.setProperty("SQUEEZEINFO_HAS_NEXT_TRACK", "false")

        try:
            e, d = self.player.get_track_elapsed_and_duration()
        except:
            e = d = 0.0

        with self.lock:
            self.elapsed = e
            self.duration = d

    def get_metadata(self, track):
        title = track.get("title", "Unknown Track")
        album = track.get("album", "Unknown Album")
        artist = track.get("artist", "Unknown Artist")
        img_icon = ""
        img_bg = ""

        debug("Metadata: {}".format(track))

        debug("Getting artwork url...")
        try:
            url = self.awr.getURL(track)
        except:
            debug("Error in artwork resolver")
            raise
        debug("Artwork url: {}".format(url))

        try:
            debug("Getting cached image paths.")
            #img_icon = self.cache.getCachedImage(url, IMG_ICON)
            img_bg = self.cache.getCachedImage(url, IMG_BACKGROUND)
            img_icon = url
        except:
            debug("Error retrieving cache paths")

        return title, album, artist, img_icon, img_bg

    def set_next_up(self, track):
        debug("Setting next track info")
        title, album, artist, icon, _ = self.get_metadata(track)
        self.setProperty("SQUEEZEINFO_NEXT_TITLE", title)
        self.setProperty("SQUEEZEINFO_NEXT_ARTIST", artist)
        self.setProperty("SQUEEZEINFO_NEXT_ALBUM", album)
        self.setProperty("SQUEEZEINFO_NEXT_ICON", icon)

    def set_now_playing(self, track):
        debug("Setting now playing track info")
        title, album, artist, icon, bg = self.get_metadata(track)
        self.setProperty("SQUEEZEINFO_NP_TITLE", title)
        self.setProperty("SQUEEZEINFO_NP_ARTIST", artist)
        self.setProperty("SQUEEZEINFO_NP_ALBUM", album)
        self.setProperty("SQUEEZEINFO_NP_BACKGROUND", bg)
        self.setProperty("SQUEEZEINFO_NP_ICON", icon)
        #self.setProperty("SQUEEZEINFO_NP_PROGRESS", prog)
        #xbmc.log("PROG TEXTURE {}".format(prog))

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
        try:
            self.sync_groups = self.cmdserver.get_sync_groups()
        except:
            self.sync_groups = []

        debug("Sync groups: {}".format(self.sync_groups))

    def track_changed(self, event=None):
        debug("track_changed")
        debug(event)
        if self.cur_or_sync(self.getCallbackPlayer(event)):
            self.get_info()

    def no_server(self, event=None):
        debug("no_server: {}".format(event))
        self.setProperty("SQUEEZEINFO_SERVER_CONNECTED", "false")


    def server_connect(self, event=None):
        debug("server_connect: {}".format(event))
        self.setProperty("SQUEEZEINFO_SERVER_CONNECTED", "true")
        self.get_squeeze_players()

    def vol_change(self, event=None):
        debug("vol_change: {}".format(event))
        pass

    def vol_up(self):
        try:
            self.player.volume_up()
        except:
            pass

    def vol_down(self):
        try:
            self.player.volume_down()
        except:
            pass

    def play_pause(self, event=None):
        debug("play_pause: {}".format(event))
        if self.cur_or_sync(self.getCallbackPlayer(event)):
            if event.split()[3] == "1":
                self.playing = False
            else:
                self.playing = True
            debug("Player playing state now: {}".format(self.playing))

    def client_change(self, event=None):
        debug("client_change: {}".format(event))
        self.get_squeeze_players()
        if self.players:
            self.get_info()

    def show_progress(self):

        # No debugs here to avoid massive spamming

        i = 0

        while not xbmc.abortRequested:

            if not (i % 20):
                try:
                    self.playing = self.player.get_mode() == "play"
                except:
                    self.playing = False

                try:
                    e, d = self.player.get_track_elapsed_and_duration()
                except:
                    e = d = 0.0

                with self.lock:
                    self.elapsed = e
                    self.duration = d

            else:
                if self.playing:
                    with self.lock:
                        self.elapsed += 0.25

            try:
                percent = float(self.elapsed/self.duration) * 100
            except:
                percent = 0

            self.progress.setPercent(percent)

            i = (i + 1) % 20

            sleep(0.25)

    @ch.action("volumeup", "*")
    def test_act(self, controlid):
        debug("VOLUME UP!")
        self.vol_up()
