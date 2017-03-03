import json

from menuitems import (NextMenuItem,
                       PlaylistMenuItem,
                       SearchMenuItem,
                       AudioMenuItem)

CUSTOM_MENU = "customhomemenu.json"

class LMSMenuHandler(object):

    def __init__(self, player):
        self.player = player
        self.rootmenu = ["menu", "items", 0, 1000, "direct:1"]

    def _request(self, menucmd):
        self.result = self.player.request(menucmd)
        return self.result

    def changePlayer(self, player):
        self.player = player

    def getCustomMenu(self, raw):
        processed = self._process_menu(raw)
        return processed

    def getHomeMenu(self):

        raw = self._request(self.rootmenu)
        processed = self._process_menu(raw)
        return processed

    def dump(self, menu, filename):
        with open(filename, "w") as dumpfile:
            json.dump(menu, dumpfile, indent=4)

    def getMenu(self, menucmd):

        raw = self._request(menucmd)
        processed = self._process_menu(raw)

        return processed

    def _process_menu(self, raw_menu):

        processed = []

        for item in raw_menu.get("item_loop"):

            menutype = item.get("type")
            style = item.get("style")

            kwargs = {"player": self.player,
                      "menuitem": item,
                      "base": raw_menu.get("base", None)}

            if menutype == "audio" or (menutype == "link" and style == "itemplay"):
                entry = AudioMenuItem(**kwargs)

            elif menutype == "playlist" or self.is_playable(item, raw_menu.get("base")):
                entry = PlaylistMenuItem(**kwargs)

            elif menutype == "search":
                entry = SearchMenuItem(**kwargs)

            else:
                entry = NextMenuItem(**kwargs)

            processed.append(entry)

        return processed

    def is_playable(self, item, base=None):
        playable = ["play", "playControl"]
        if base is None:
            return False

        item_act = item.get("goAction", False)
        if item_act in playable:
            return True
        else:
            return False
