import errno
import hashlib
import os
import requests
from StringIO import StringIO
import urllib2

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from PIL import ImageFilter

import xbmcaddon, xbmc

IMG_BACKGROUND = "backgrounds"
IMG_ICON = "icons"
IMG_PROGRESS = "swatch"

_A_ = xbmcaddon.Addon()

ADDON_PROFILE = xbmc.translatePath(_A_.getAddonInfo('profile')).decode('utf-8')

CACHE_PATH = os.path.join(ADDON_PROFILE, "cache")

CACHE_LOCATIONS = {IMG_BACKGROUND: IMG_BACKGROUND,
                   IMG_ICON: IMG_ICON,
                   IMG_PROGRESS: IMG_PROGRESS}

class ImageCache(object):

    def __init__(self):
        self.make_sure_path_exists(os.path.join(CACHE_PATH, IMG_ICON))
        self.make_sure_path_exists(os.path.join(CACHE_PATH, IMG_BACKGROUND))
        self.make_sure_path_exists(os.path.join(CACHE_PATH, IMG_PROGRESS))

    def make_sure_path_exists(self, path):
        try:
            os.makedirs(path)
        except OSError as exception:
            if exception.errno != errno.EEXIST:
                raise

    def get_dominant_colour(self, img):
        resize = 150
        tmp = img.resize((resize, resize))
        result = tmp.convert('P', palette=Image.ADAPTIVE, colors=1)
        result.putalpha(0)
        colors = result.getcolors(resize*resize)

        pal = Image.new('RGB', (5, 5))
        draw = ImageDraw.Draw(pal)

        draw.rectangle([0, 0, 5, 5], fill=colors[0][1])
        del draw

        return pal

    def save_images(self, url, img_name):
        bg_path = os.path.join(CACHE_PATH, IMG_BACKGROUND, img_name)
        icon_path = os.path.join(CACHE_PATH, IMG_ICON, "icon_{}".format(img_name))
        swatch_path = os.path.join(CACHE_PATH, IMG_PROGRESS, img_name)

        raw = requests.get(url)
        img = Image.open(StringIO(raw.content))
        img.save(icon_path)

        bg = img.resize((1920, 1920))
        bg= bg.filter(ImageFilter.GaussianBlur(radius=40))
        lyr = Image.new('RGBA', (1920, 1920))
        ld = ImageDraw.Draw(lyr)
        ld.rectangle([(0, 0), (1920, 1920)], fill=(0, 0, 0, 127))
        bg.paste(lyr, (0,0), mask=lyr)
        bg.save(bg_path)

        # img = img.resize((100, 100))


        # try:
        #     self.get_dominant_colour(img).save(swatch_path)
        # except:
        #     pass


    def getCachedImage(self, url, img_type, resize=False):

        if img_type not in CACHE_LOCATIONS:
            return

        subfolder = CACHE_LOCATIONS[img_type]
        folder = os.path.join(CACHE_PATH, subfolder)

        img_hash = hashlib.md5(url).hexdigest()
        img_name = "{}.jpg".format(img_hash)

        cached_file = os.path.join(folder, img_name)

        if not os.path.exists(cached_file):
            self.save_images(url, img_name)

        if img_type == IMG_ICON:
            img_name = "icon_{}".format(img_name)

        return os.path.join(folder, img_name)
