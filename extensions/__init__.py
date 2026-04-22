from extensions.all_sources import AllExtension
from extensions.backiee import BackieeExtension
from extensions.uhdpaper import UHDWallpaperExtension
from .wallhaven import WallhavenExtension
# from .danbooru import DanbooruExtension

# WARNING: Do NOT REGISTER ANY EXTENSIONS 
# MORE THAN 1 TIME (INCLUDING ALL CODEBASE).
# IT WILL CRASH.

from .local import LocalExtension
from .fourkwallpapers import FourKWallpapersExtension
from core.extension import register_extension

register_extension("4KWallpapers", FourKWallpapersExtension)
register_extension("Wallhaven", WallhavenExtension)
# Off-ing Danbooru for now since it has a lot of NSFW content and is less relevant to the main use case
# register_extension("Danbooru", DanbooruExtension)
register_extension("Local", LocalExtension)
register_extension("UHDPaper", UHDWallpaperExtension)
register_extension("Backiee", BackieeExtension)
register_extension("All", AllExtension)