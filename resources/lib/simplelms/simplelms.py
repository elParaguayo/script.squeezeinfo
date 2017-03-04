"""
Simple python class definitions for interacting with Logitech Media Server.
This code uses the JSON interface.
"""
import urllib2
import json

DETAILED_TAGS = ["a", "c", "d", "j", "K", "l", "x"]


class LMSConnectionError(Exception):
    pass


class LMSPlayer(object):

    def __init__(self, ref, server):
        self.server = server
        self.ref = ref
        self.update()

    @classmethod
    def from_index(cls, index, server):
        ref = server.request(params="player id {} ?".format(index))["_id"]
        return cls(ref, server)

    def __repr__(self):
        return "SqueezePlayer: {}".format(self.ref)

    def __eq__(self, other):
        try:
            return self.ref == other.ref
        except AttributeError:
            if type(other) == str:
                return self.ref == other
            else:
                return False

    def update(self):
        self.name = self.get_name()

    def request(self, command):
        return self.server.request(self.ref, command)

    def play(self):
        """Play"""
        self.request("play")

    def stop(self):
        """Stop"""
        self.request("stop")

    def pause(self):
        """Pause On"""
        self.request("pause 1")

    def unpause(self):
        """Pause Off"""
        self.request("pause 0")

    def toggle(self):
        """Play/Pause Toggle"""
        self.request("pause")

    def next(self):
        """Next Track"""
        self.request("playlist jump +1")

    def prev(self):
        """Previous Track"""
        self.request("playlist jump -1")

    def set_name(self, name):
        self.request("name {}".format(name))

    def get_name(self):
        try:
            name = self.request("name ?")["_value"]
        except:
            name = "unnamed"

        return name

    def get_mode(self):
        self.mode = self.request("mode ?")["_mode"]
        return self.mode

    def get_wifi_signal_strength(self):
        self.wifi_signal_strength = self.request("signalstrength ?")
        return self.wifi_signal_strength.get("_signalstrength")

    def get_track_artist(self):
        self.track_artist = self.request("artist ?")
        return self.track_artist["_artist"]

    def get_track_album(self):
        self.track_album = self.request("album ?")
        return self.track_album["_album"]

    def get_track_title(self):
        self.track_title = self.request("title ?")
        return self.track_title["_title"]

    def get_track_duration(self):
        self.track_duration = float(self.request("duration ?")["_duration"])
        return self.track_duration

    def get_track_elapsed_and_duration(self):
        try:
            duration = self.get_track_duration()
            elapsed = self.get_time_elapsed()
        except:
            duration = 0.0
            elapsed = 0.0

        return elapsed, duration

    def get_time_elapsed(self):
        """Get Player Time Elapsed"""
        try:
            self.time = float(self.request("time ?")["_time"])
        except TypeError:
            self.time = float(0)
        return self.time

    def playlist_track_count(self):
        """Get the amount of tracks in the current playlist"""
        try:
            return int(self.request('playlist tracks ?')["_tracks"])
        except:
            return 0

    def playlist_play_index(self, index):
        """Play track at a certain position in the current playlist
        (index is zero-based)"""
        return self.request('playlist index {}'.format(index))

    def playlist_get_position(self):
        """Get the position of the current track in the playlist"""
        try:
            idx = self.request('playlist index ?')
            return int(idx["_index"])
        except:
            return 0

    def playlist_get_current_detail(self, amount=None):
        return self.playlist_get_info(start=self.playlist_get_position(),
                                      amount=amount,
                                      taglist=DETAILED_TAGS)

    def playlist_get_detail(self, start=None, amount=None):
        return self.playlist_get_info(start=start,
                                      amount=amount,
                                      taglist=DETAILED_TAGS)

    def playlist_get_info(self, taglist=None, start=None, amount=None):
        """Get info about the tracks in the current playlist"""
        if amount is None:
            amount = self.playlist_track_count()

        if start is None:
            start = 0

        tags = " tags:{}".format(",".join(taglist)) if taglist else ""
        response = self.request('status %i %i %s' % (start, amount, tags))
        try:
            return response["playlist_loop"]
        except:
            return []

    def get_volume(self):
        """Get Player Volume"""
        try:
            self.volume = int(self.request("mixer volume ?").get("_volume"))
        except TypeError:
            self.volume = -1
        except ValueError:
            self.volume = 0
        return self.volume

    def volume_up(self, interval=5):
        self.request("mixer volume +{}".format(interval))

    def volume_down(self, interval=5):
        self.request("mixer volume -{}".format(interval))

    def set_volume(self, volume):
        """Set Player Volume"""
        try:
            volume = int(volume)
            if volume < 0:
                volume = 0
            if volume > 100:
                volume = 100
            self.request("mixer volume {}".format(volume))
        except TypeError:
            pass

class LMSServer(object):
    """
    Class for Logitech Media Server.
    Provides access to JSON interface.
    """

    def __init__(self, host="localhost", port=9000):
        self.host = host
        self.port = port
        self.id = 1
        self.web = "http://{h}:{p}/".format(h=host, p=port)
        self.url = "http://{h}:{p}/jsonrpc.js".format(h=host, p=port)

    def request(self, player="-", params=None):
        """
        Send JSON request to server.
        """
        req = urllib2.Request(self.url)
        req.add_header('Content-Type', 'application/json')

        if type(params) == str:
            params = params.split()

        cmd = [player, params]

        data = {"id": self.id,
                "method": "slim.request",
                "params": cmd}

        try:
            response = urllib2.urlopen(req, json.dumps(data))
            self.id += 1
            return json.loads(response.read())["result"]

        except urllib2.URLError:
            raise LMSConnectionError("Could not connect to server.")

        except:
            return None

    def get_players(self):
        self.players = []
        player_count = self.get_player_count()
        for i in range(player_count):
            player = LMSPlayer.from_index(i, self)
            self.players.append(player)
        return self.players

    def get_player_count(self):
        try:
            count = self.request(params="player count ?")["_count"]
        except:
            count = 0

        return count

    def get_sync_groups(self):
        groups = self.request(params="syncgroups ?")
        syncgroups = [x.get("sync_members","").split(",") for x in groups.get("syncgroups_loop",dict())]
        return syncgroups

    def ping(self):

        try:
            self.request(params="ping")
            return True
        except LMSConnectionError:
            return False
