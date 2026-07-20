# Force IPv4 — broken IPv6 causes 30s timeouts on some machines
import urllib3.util.connection
urllib3.util.connection._has_ipv6 = lambda host: False

from .extension import WallpaperExtension, register_extension, get_extension_names, create_extension
from .settings import Settings
from .workers import SearchWorker, DownloadWorker, ThumbnailLoader
