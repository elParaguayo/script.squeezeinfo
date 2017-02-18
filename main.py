"""script.squeezeinfo

   by elParaguayo

   Basic Kodi window to display Now Playing information for your Logitech
   Media Server.

   See license.txt for licensing information.
"""
import xbmcaddon

from resources.lib.squeezeinfo import SqueezeInfo

SKIN_PATH = xbmcaddon.Addon().getAddonInfo("path")

window = SqueezeInfo("squeeze.xml", SKIN_PATH, "Default", "1080i")
window.doModal()
del window
