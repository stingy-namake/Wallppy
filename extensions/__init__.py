from core.extension import register_extension
from .local import LocalExtension
from .all_sources import AllExtension
from .wallhaven import WallhavenExtension
from .fourkwallpapers import FourKWallpapersExtension
from .backiee import BackieeExtension
# from extensions.uhdpaper import UHDWallpaperExtension
# from .danbooru import DanbooruExtension

# WARNING: Do NOT REGISTER ANY EXTENSIONS 
# MORE THAN 1 TIME (INCLUDING ALL CODEBASE).
# IT WILL CRASH.

register_extension("Local", LocalExtension)
register_extension("All (Experimental)", AllExtension)
register_extension("Wallhaven", WallhavenExtension)
register_extension("4KWallpapers", FourKWallpapersExtension)
register_extension("Backiee", BackieeExtension)
# Off-ing Danbooru for now since it has a lot of NSFW content and is less relevant to the main use case
# register_extension("Danbooru", DanbooruExtension)
# register_extension("UHDPaper", UHDWallpaperExtension)
