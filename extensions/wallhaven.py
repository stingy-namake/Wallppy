import json
import hashlib
import time
import requests
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import List, Dict, Any
from core.extension import WallpaperExtension

DEBUG = True


def _dbg(msg):
    if DEBUG:
        print(f"[PERF][wallhaven] {msg}")


class WallhavenAPI:
    """Thin wallhaven.cc API v1 client with disk cache."""

    BASE = "https://wallhaven.cc/api/v1"
    CACHE_DIR = Path.home() / ".cache" / "wallppy" / "api"
    CACHE_TTL = 600  # 10 min

    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

        self.session = requests.Session()
        retry = Retry(total=3, backoff_factor=0.5,
                      status_forcelist=[429, 500, 502, 503, 504],
                      allowed_methods=["GET"])
        adapter = HTTPAdapter(pool_connections=5, pool_maxsize=10,
                              max_retries=retry)
        self.session.mount("https://", adapter)

    def _headers(self) -> Dict[str, str]:
        h = {"User-Agent": "wallppy/2.0 (https://github.com/stingy-namake/wallppy)"}
        if self.api_key:
            h["X-API-Key"] = self.api_key
        return h

    def _cache_key(self, params: Dict[str, Any]) -> str:
        return hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()

    def _read_cache(self, params: Dict[str, Any]) -> Dict[str, Any] | None:
        f = self.CACHE_DIR / f"{self._cache_key(params)}.json"
        if not f.exists():
            return None
        try:
            if time.time() - f.stat().st_mtime > self.CACHE_TTL:
                return None
            return json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            return None

    def _write_cache(self, params: Dict[str, Any], data: Dict[str, Any]):
        try:
            (self.CACHE_DIR / f"{self._cache_key(params)}.json").write_text(
                json.dumps(data))
        except OSError:
            pass

    def search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        t0 = time.perf_counter()
        cached = self._read_cache(params)
        if cached is not None:
            _dbg(f"API cache HIT in {(time.perf_counter()-t0)*1000:.0f}ms")
            return cached
        _dbg(f"API cache MISS, fetching from network...")
        # Use curl — requests is broken on some machines (IPv6/TLS issues)
        try:
            import subprocess
            url = f"{self.BASE}/search?" + "&".join(
                f"{k}={v}" for k, v in params.items() if v)
            result = subprocess.run(
                ["curl", "-sL", "--max-time", "15",
                 "-H", f"X-API-Key: {self.api_key}" if self.api_key else "true",
                 url],
                capture_output=True, text=True, timeout=20)
            if result.returncode != 0:
                raise Exception(f"curl failed: {result.stderr[:200]}")
            data = json.loads(result.stdout)
            self._write_cache(params, data)
            _dbg(f"API fetch OK in {(time.perf_counter()-t0)*1000:.0f}ms, "
                 f"{len(data.get('data', []))} results")
            return data
        except Exception as e:
            _dbg(f"API fetch FAILED in {(time.perf_counter()-t0)*1000:.0f}ms: {e}")
            return {}

    def clear_cache(self):
        import shutil
        if self.CACHE_DIR.exists():
            shutil.rmtree(self.CACHE_DIR, ignore_errors=True)
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)


class WallhavenExtension(WallpaperExtension):
    """Wallhaven.cc wallpaper source."""

    def __init__(self, api_key: str = None):
        super().__init__()
        self.name = "Wallhaven"
        self._api = WallhavenAPI(api_key)
        self._last_meta: Dict[str, Any] = {}

    @staticmethod
    def _bit_str(val: str, length: int = 3) -> str:
        if isinstance(val, str) and len(val) == length:
            return val
        return "1" * length

    def _build_params(self, query: str, page: int, **kw) -> Dict[str, Any]:
        p = {
            "q": query or "",
            "categories": self._bit_str(kw.get("categories", kw.get("category", "111"))),
            "purity": self._bit_str(kw.get("purity", "100")),
            "page": page,
            "per_page": 24,
            "sorting": kw.get("sorting", "date_added"),
            "order": "desc",
        }
        if p["sorting"] == "toplist":
            p["topRange"] = kw.get("top_range", "1M")
        if kw.get("resolution"):
            p["resolutions"] = kw["resolution"]
        if kw.get("ratio"):
            p["ratios"] = kw["ratio"]
        return p

    @staticmethod
    def _strip(w: Dict[str, Any]) -> Dict[str, Any]:
        """Minimal data needed for widget display + download."""
        return {
            "id": w.get("id", ""),
            "path": w.get("path", ""),
            "thumb_small": w.get("thumbs", {}).get("small", ""),
            "thumb_large": w.get("thumbs", {}).get("large", ""),
            "resolution": w.get("resolution", "?x?"),
            "file_type": w.get("file_type", "image/jpeg"),
        }

    # ── WallpaperExtension interface ──────────────────────────────

    def search(self, query: str, page: int = 1, **kw) -> List[Dict[str, Any]]:
        params = self._build_params(query, page, **kw)
        data = self._api.search(params)
        self._last_meta = data.get("meta", {})
        return [self._strip(w) for w in data.get("data", [])]

    def get_total_pages(self, query: str, **kw) -> int:
        return self._last_meta.get("last_page", 1)

    def get_thumbnail_url(self, wd: Dict[str, Any]) -> str:
        """Small thumbnail for widget grid — fast load, low memory."""
        return wd.get("thumb_small", "")

    def get_download_url(self, wd: Dict[str, Any]) -> str:
        """Full resolution image path."""
        path = wd.get("path", "")
        if path and not path.startswith("http"):
            path = f"https://wallhaven.cc{path}"
        return path

    def get_wallpaper_id(self, wd: Dict[str, Any]) -> str:
        return str(wd.get("id", ""))

    def get_file_extension(self, wd: Dict[str, Any]) -> str:
        ft = wd.get("file_type", "image/jpeg")
        if "png" in ft:
            return "png"
        return "jpg"

    def get_resolution(self, wd: Dict[str, Any]) -> str:
        return wd.get("resolution", "?x?")

    def get_filters(self) -> Dict[str, Any]:
        return {
            "categories": {
                "type": "checkboxes",
                "label": "Categories",
                "options": [
                    {"id": "general", "label": "General", "default": False},
                    {"id": "anime", "label": "Anime", "default": True},
                    {"id": "people", "label": "People", "default": False},
                ],
            },
            "purity": {
                "type": "checkboxes",
                "label": "Content",
                "options": [
                    {"id": "sfw", "label": "SFW", "default": True},
                    {"id": "sketchy", "label": "Sketchy", "default": False},
                    {"id": "nsfw", "label": "NSFW", "default": False,
                     "requires_api_key": True},
                ],
            },
            "sorting": {
                "type": "dropdown",
                "label": "Sort by",
                "options": [
                    {"id": "date_added", "label": "Date Added", "default": True},
                    {"id": "relevance", "label": "Relevance", "default": False},
                    {"id": "random", "label": "Random", "default": False},
                    {"id": "views", "label": "Views", "default": False},
                    {"id": "favorites", "label": "Favorites", "default": False},
                    {"id": "toplist", "label": "Toplist", "default": False},
                ],
            },
            "top_range": {
                "type": "dropdown",
                "label": "Toplist Period",
                "options": [
                    {"id": "1d", "label": "Last 24 Hours", "default": False},
                    {"id": "3d", "label": "Last 3 Days", "default": False},
                    {"id": "1w", "label": "Last Week", "default": False},
                    {"id": "1M", "label": "Last Month", "default": True},
                    {"id": "3M", "label": "Last 3 Months", "default": False},
                    {"id": "6M", "label": "Last 6 Months", "default": False},
                    {"id": "1y", "label": "Last Year", "default": False},
                ],
            },
            "resolution": {
                "type": "dropdown",
                "label": "Resolution",
                "options": [
                    {"id": "", "label": "Any", "default": True},
                    {"id": "1920x1080", "label": "1920x1080 (FHD)", "default": False},
                    {"id": "2560x1440", "label": "2560x1440 (QHD)", "default": False},
                    {"id": "3840x2160", "label": "3840x2160 (4K UHD)", "default": False},
                    {"id": "7680x4320", "label": "7680x4320 (8K UHD)", "default": False},
                    {"id": "1280x720", "label": "1280x720 (HD)", "default": False},
                    {"id": "3440x1440", "label": "3440x1440 (UltraWide)", "default": False},
                    {"id": "2560x1080", "label": "2560x1080 (UltraWide)", "default": False},
                ],
            },
            "ratio": {
                "type": "checkboxes",
                "label": "Aspect Ratio",
                "options": [
                    {"id": "16x9", "label": "16:9", "default": True},
                    {"id": "16x10", "label": "16:10", "default": False},
                    {"id": "21x9", "label": "21:9", "default": False},
                    {"id": "32x9", "label": "32:9", "default": False},
                    {"id": "4x3", "label": "4:3", "default": False},
                    {"id": "5x4", "label": "5:4", "default": False},
                    {"id": "9x16", "label": "9:16 (Mobile)", "default": False},
                    {"id": "1x1", "label": "1:1", "default": False},
                ],
            },
        }
