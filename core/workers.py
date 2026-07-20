import os
import time
import traceback
import threading
import requests
from collections import OrderedDict
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PyQt5.QtCore import QThread, pyqtSignal, QSize, Qt
from PyQt5.QtGui import QPixmap, QImageReader, QImage
from typing import List, Dict, Any
from .extension import WallpaperExtension

DEBUG = True


def _dbg(msg):
    if DEBUG:
        print(f"[PERF][thumb] {msg}")


def _fetch_with_timeout(url: str, timeout: int = 10) -> bytes:
    """Fetch URL with hard total timeout (requests has no total timeout)."""
    result = [None]
    error = [None]

    def _do():
        try:
            session = get_session()
            r = session.get(url, timeout=timeout, stream=True)
            if r.status_code != 200:
                raise Exception(f"HTTP {r.status_code}")
            data = bytearray()
            for chunk in r.iter_content(chunk_size=8192):
                data.extend(chunk)
            result[0] = bytes(data)
        except Exception as e:
            error[0] = e

    t = threading.Thread(target=_do, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        raise TimeoutError(f"fetch timed out after {timeout}s")
    if error[0]:
        raise error[0]
    return result[0]

# Thread‑local storage for sessions
_thread_local = threading.local()

def get_session():
    """Return a thread‑local requests Session with connection pooling."""
    if not hasattr(_thread_local, "session"):
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        })
        retry = Retry(total=2, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(pool_connections=5, pool_maxsize=10, max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        _thread_local.session = session
    return _thread_local.session


def curl_fetch(url: str, timeout: int = 15) -> bytes:
    """Fetch using system curl — fast, no IPv6/TLS issues."""
    import subprocess
    import os
    curl_env = os.environ.copy()
    curl_env["LD_LIBRARY_PATH"] = "/usr/lib:/lib"
    result = subprocess.run(
        ["curl", "-sL", "--max-time", str(timeout),
         "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
         url],
        capture_output=True,
        env=curl_env
    )
    if result.returncode != 0:
        raise Exception(f"curl failed (rc={result.returncode}): {result.stderr[:200]}")
    return result.stdout


class CrashAwareThread(QThread):
    """QThread that logs uncaught exceptions to the crash log before re-raising."""

    def run(self):
        try:
            self._do_run()
        except Exception:
            import logging
            logger = logging.getLogger("wallppy.crash")
            logger.critical(
                f"Worker {self.__class__.__name__} crashed:\n{traceback.format_exc()}"
            )
            raise

    def _do_run(self):
        """Subclasses should override this instead of run()."""
        super().run()


class SearchWorker(CrashAwareThread):
    finished = pyqtSignal(list, int, int)  # wallpapers, page, total_pages
    error = pyqtSignal(str)

    def __init__(self, extension: WallpaperExtension, query: str, page: int = 1, **kwargs):
        super().__init__()
        self.extension = extension
        self.query = query
        self.page = page
        self.kwargs = kwargs

    def _do_run(self):
        try:
            wallpapers = self.extension.search(self.query, self.page, **self.kwargs)
            total_pages = self.extension.get_total_pages(self.query, **self.kwargs)
            self.finished.emit(wallpapers, self.page, total_pages)
        except Exception as e:
            self.error.emit(str(e))


class DownloadWorker(CrashAwareThread):
    finished = pyqtSignal(bool, str, str, str)  # success, filepath, filename, wall_id
    progress = pyqtSignal(int)

    def __init__(self, extension: WallpaperExtension, wallpaper_data: Dict[str, Any], download_folder: str):
        super().__init__()
        self.extension = extension
        self.data = wallpaper_data
        self.download_folder = download_folder

    def _do_run(self):
        wall_id = self.extension.get_wallpaper_id(self.data)
        download_urls = self.extension.get_download_urls_by_priority(self.data)
        if not download_urls:
            self.finished.emit(False, "", "No image URL", wall_id)
            return

        ext = self.extension.get_file_extension(self.data)
        filename = f"wallppy-{wall_id}.{ext}"
        filepath = os.path.join(self.download_folder, filename)

        os.makedirs(self.download_folder, exist_ok=True)

        if os.path.exists(filepath):
            self.finished.emit(True, filepath, filename, wall_id)
            return

        # Use curl — requests is broken on some machines
        import subprocess
        url = download_urls[0]
        try:
            self.progress.emit(0)
            result = subprocess.run(
                ["curl", "-sL", "--max-time", "60",
                 "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                 "-o", filepath,
                 "-w", "%{http_code}",
                 url],
                capture_output=True, text=True, timeout=70)
            http_code = result.stdout.strip()
            if http_code == "200" and os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                self.progress.emit(100)
                self.finished.emit(True, filepath, filename, wall_id)
            else:
                if os.path.exists(filepath):
                    os.remove(filepath)
                self.finished.emit(False, "", f"HTTP {http_code}", wall_id)
        except Exception as e:
            if os.path.exists(filepath):
                os.remove(filepath)
            self.finished.emit(False, "", str(e), wall_id)


class ThumbnailLoader(CrashAwareThread):
    loaded = pyqtSignal(QPixmap)
    _cache = OrderedDict()
    _cache_max = 200
    _lock = __import__('threading').Lock()
    _semaphore = __import__('threading').Semaphore(8)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def _do_run(self):
        t0 = time.perf_counter()
        short_url = self.url.split("/")[-1] if "/" in self.url else self.url[:30]
        try:
            with ThumbnailLoader._lock:
                if self.url in ThumbnailLoader._cache:
                    ThumbnailLoader._cache.move_to_end(self.url)
                    cached = ThumbnailLoader._cache[self.url]
                    if not cached.isNull():
                        _dbg(f"cache HIT {short_url} in {(time.perf_counter()-t0)*1000:.0f}ms")
                        self.loaded.emit(cached)
                        return

            if os.path.exists(self.url):
                reader = QImageReader(self.url)
                reader.setAutoDetectImageFormat(True)
                if reader.supportsAnimation():
                    reader.setScaledSize(QSize(256, 256))
                else:
                    reader.setScaledSize(QSize(256, 256))
                pixmap = QPixmap.fromImage(reader.read())
                with ThumbnailLoader._lock:
                    ThumbnailLoader._cache[self.url] = pixmap
                    if len(ThumbnailLoader._cache) > ThumbnailLoader._cache_max:
                        ThumbnailLoader._cache.popitem(last=False)
                _dbg(f"local file {short_url} in {(time.perf_counter()-t0)*1000:.0f}ms")
                self.loaded.emit(pixmap)
                return

            with ThumbnailLoader._semaphore:
                t_net = time.perf_counter()
                data = None
                # Try curl first — fast, no IPv6/TLS issues
                try:
                    t_curl = time.perf_counter()
                    data = curl_fetch(self.url, timeout=8)
                    curl_ms = (time.perf_counter() - t_curl) * 1000
                    _dbg(f"  curl OK {curl_ms:.0f}ms, {len(data)} bytes")
                except Exception as e:
                    curl_ms = (time.perf_counter() - t_curl) * 1000
                    _dbg(f"  curl FAIL {curl_ms:.0f}ms: {type(e).__name__}: {e}")
                # Fallback to requests (slow on some machines)
                if data is None:
                    try:
                        t_req = time.perf_counter()
                        data = _fetch_with_timeout(self.url, timeout=8)
                        req_ms = (time.perf_counter() - t_req) * 1000
                        _dbg(f"  requests OK {req_ms:.0f}ms, {len(data)} bytes")
                    except Exception as e:
                        req_ms = (time.perf_counter() - t_req) * 1000
                        _dbg(f"  requests FAIL {req_ms:.0f}ms: {type(e).__name__}: {e}")
                        data = b""
                net_ms = (time.perf_counter() - t_net) * 1000
                
                t_img = time.perf_counter()
                if len(data) > 500_000:
                    img = QImage()
                    img.loadFromData(data)
                    if not img.isNull():
                        scaled = img.scaled(QSize(256, 256), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        pixmap = QPixmap.fromImage(scaled)
                    else:
                        pixmap = QPixmap()
                        pixmap.loadFromData(data)
                else:
                    pixmap = QPixmap()
                    pixmap.loadFromData(data)
                img_ms = (time.perf_counter() - t_img) * 1000
                
                if not pixmap.isNull():
                    with ThumbnailLoader._lock:
                        ThumbnailLoader._cache[self.url] = pixmap
                        if len(ThumbnailLoader._cache) > ThumbnailLoader._cache_max:
                            ThumbnailLoader._cache.popitem(last=False)
                total_ms = (time.perf_counter() - t0) * 1000
                _dbg(f"net {net_ms:.0f}ms + img {img_ms:.0f}ms = {total_ms:.0f}ms "
                     f"({len(data)} bytes) {short_url}")
                self.loaded.emit(pixmap)
        except:
            _dbg(f"FAILED {short_url} in {(time.perf_counter()-t0)*1000:.0f}ms")
            self.loaded.emit(QPixmap())