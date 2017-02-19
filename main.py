"""script.squeezeinfo

   by elParaguayo

   Basic Kodi window to display Now Playing information for your Logitech
   Media Server.

   See license.txt for licensing information.
"""
import os
import shutil
import sys

import xbmc, xbmcaddon

from resources.lib.squeezeinfo import SqueezeInfo

_A_ = xbmcaddon.Addon()

SKIN_PATH = _A_.getAddonInfo("path")
ADDON_PROFILE = xbmc.translatePath(_A_.getAddonInfo('profile')).decode('utf-8')
CACHE_PATH = os.path.join(ADDON_PROFILE, "cache")


def show_window():
    window = SqueezeInfo("squeeze.xml", SKIN_PATH, "Default", "1080i")
    window.doModal()
    del window

def delete_cache():
    shutil.rmtree(CACHE_PATH)

ACTIONS = {"clearcache": delete_cache,
           "default": show_window}

if len(sys.argv) > 1:
    mode = sys.argv[1]
else:
    mode = "default"


action = ACTIONS.get(mode, show_window)

action()
