import errno
import hashlib
import os
import requests
from StringIO import StringIO

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from PIL import ImageFilter

import xbmcaddon, xbmc


# Define some constants
IMG_BACKGROUND = "backgrounds"
IMG_ICON = "icons"
IMG_PROGRESS = "swatch"

# Initialise addon instance
_A_ = xbmcaddon.Addon()

# Get the userdata folder path
ADDON_PROFILE = xbmc.translatePath(_A_.getAddonInfo('profile')).decode('utf-8')

# Define the cache path
CACHE_PATH = os.path.join(ADDON_PROFILE, "cache")
CACHE_LOCATIONS = {IMG_BACKGROUND: IMG_BACKGROUND,
                   IMG_ICON: IMG_ICON,
                   IMG_PROGRESS: IMG_PROGRESS}


class ImageCache(object):
    """Class to process images and cache image files."""

    def __init__(self):
        # Create the relevant folders
        self.make_sure_path_exists(os.path.join(CACHE_PATH, IMG_ICON))
        self.make_sure_path_exists(os.path.join(CACHE_PATH, IMG_BACKGROUND))

        # This was for a coloured progress bar but it doesn't seem to work
        # at the moment
        # self.make_sure_path_exists(os.path.join(CACHE_PATH, IMG_PROGRESS))

    def make_sure_path_exists(self, path):
        """Does what it says on the tin..."""
        try:
            os.makedirs(path)
        except OSError as exception:
            if exception.errno != errno.EEXIST:
                raise

    def get_dominant_colour(self, img):
        """Retrieves the main colour from the image and returns a 5x5 image in
           this colour.
        """
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
        """Processes the images and saves them to the cache locations."""
        bg_path = os.path.join(CACHE_PATH, IMG_BACKGROUND, img_name)
        # icon_path = os.path.join(CACHE_PATH, IMG_ICON,
        #                          "icon_{}".format(img_name))
        icon_path = os.path.join(CACHE_PATH, IMG_ICON, img_name)
        swatch_path = os.path.join(CACHE_PATH, IMG_PROGRESS, img_name)

        # Get the image from the URL
        raw = requests.get(url)
        img = Image.open(StringIO(raw.content))

        # The icon file is just the unprocessed image
        img.save(icon_path)

        # Process the background image...

        # 1) Resize
        bg = img.resize((1920, 1920))

        # 2) Apply blur to hide pixellation
        bg= bg.filter(ImageFilter.GaussianBlur(radius=40))

        # 4) Create a semi-transparent black layer
        lyr = Image.new('RGBA', (1920, 1920))
        ld = ImageDraw.Draw(lyr)
        ld.rectangle([(0, 0), (1920, 1920)], fill=(0, 0, 0, 127))

        # 5) Paste this over our image
        bg.paste(lyr, (0,0), mask=lyr)

        # 6) Save the image
        bg.save(bg_path)

        return

    def getCachedImage(self, url, img_type, resize=False):
        """Returns a path to the locally stored image."""

        if img_type not in CACHE_LOCATIONS:
            return

        # Get the cache folder
        subfolder = CACHE_LOCATIONS[img_type]
        folder = os.path.join(CACHE_PATH, subfolder)

        # File name is the md5 hash of the url
        img_hash = hashlib.md5(url).hexdigest()
        img_name = "{}.jpg".format(img_hash)

        # if img_type == IMG_ICON:
        #     cached_file = os.path.join(folder, "icon_{}".format(img_name))
        # else:
        cached_file = os.path.join(folder, img_name)

        if not os.path.exists(cached_file):
            self.save_images(url, img_name)

        return cached_file
