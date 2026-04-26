import os
import time
import traceback
import threading
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PyQt5.QtCore import QThread, pyqtSignal, QSize, Qt
from PyQt5.QtGui import QPixmap, QImageReader, QImage
from typing import List, Dict, Any
from .extension import WallpaperExtension

# Thread‑local storage for sessions
_thread_local = threading.local()

def get_session():
    """Return a thread‑local requests Session with connection pooling."""
    if not hasattr(_thread_local, "session"):
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Referer": "https://www.uhdpaper.com/",
        })
        retry = Retry(total=2, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(pool_connections=5, pool_maxsize=10, max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        _thread_local.session = session
    return _thread_local.session


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

        try:
            session = get_session()
            response = None
            for url in download_urls:
                try:
                    response = session.get(url, stream=True, timeout=30)
                    if response.status_code == 200:
                        break
                except Exception:
                    continue

            if not response or response.status_code != 200:
                self.finished.emit(False, "", "404", wall_id)
                return

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            last_emit = 0
            min_interval = 0.05

            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size:
                            now = time.time()
                            pct = int(downloaded * 100 / total_size)
                            if pct == 100 or now - last_emit > min_interval:
                                self.progress.emit(pct)
                                last_emit = now

            self.progress.emit(100)
            self.finished.emit(True, filepath, filename, wall_id)
        except Exception as e:
            self.finished.emit(False, "", str(e), wall_id)


class ThumbnailLoader(CrashAwareThread):
    loaded = pyqtSignal(QPixmap)
    _cache = {}
    _lock = __import__('threading').Lock()
    _semaphore = __import__('threading').Semaphore(8)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def _do_run(self):
        try:
            with ThumbnailLoader._lock:
                if self.url in ThumbnailLoader._cache:
                    cached = ThumbnailLoader._cache[self.url]
                    if not cached.isNull():
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
                self.loaded.emit(pixmap)
                return

            with ThumbnailLoader._semaphore:
                session = get_session()
                response = session.get(self.url, timeout=10, stream=True)
                if response.status_code == 200:
                    data = response.content
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
                    if not pixmap.isNull():
                        with ThumbnailLoader._lock:
                            ThumbnailLoader._cache[self.url] = pixmap
                    self.loaded.emit(pixmap)
                else:
                    self.loaded.emit(QPixmap())
        except:
            self.loaded.emit(QPixmap())