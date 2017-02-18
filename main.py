import xbmcaddon

from resources.lib.squeezeinfo import SqueezeInfo

SKIN_PATH = xbmcaddon.Addon().getAddonInfo("path")

window = SqueezeInfo("squeeze.xml", SKIN_PATH, "Default", "1080i")
window.doModal()
del window
