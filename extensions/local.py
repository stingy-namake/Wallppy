import os
import math
import time
import json
import threading
from pathlib import Path
from typing import List, Dict, Any
from PIL import Image
from core.extension import WallpaperExtension


class LocalExtension(WallpaperExtension):
    """Browse downloaded wallpapers from local folder with caching."""

    def __init__(self):
        super().__init__()
        self.name = "Local"
        self._all_files = []
        self._filtered_files = []
        self._last_query = None
        self._last_folder = ""
        self._cache_timestamp = 0
        self._cache_ttl = 300  # 5 minutes

        # Persistent metadata cache
        self._cache_dir = Path.home() / ".cache" / "wallppy"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._metadata_cache_file = self._cache_dir / "local_metadata.json"
        self._metadata = {}  # path -> {"size": int, "mtime": float, "width": int, "height": int}
        self._load_metadata_cache()

        self._bg_thread = None
        self._stop_bg = False

    def _load_metadata_cache(self):
        try:
            if self._metadata_cache_file.exists():
                with open(self._metadata_cache_file, 'r') as f:
                    self._metadata = json.load(f)
        except Exception:
            self._metadata = {}

    def _save_metadata_cache(self):
        try:
            with open(self._metadata_cache_file, 'w') as f:
                json.dump(self._metadata, f)
        except Exception:
            pass

    def _get_image_files(self, folder: str) -> List[str]:
        extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
        files = []
        try:
            for root, _, filenames in os.walk(folder):
                for f in filenames:
                    if f.lower().endswith(extensions):
                        files.append(os.path.join(root, f))
        except Exception:
            pass
        return files

    def _get_resolution(self, path: str) -> tuple:
        """Return (width, height) for an image, using cache if valid."""
        try:
            stat = os.stat(path)
            mtime = stat.st_mtime
            size = stat.st_size
        except OSError:
            return (0, 0)

        # Check cache
        cached = self._metadata.get(path)
        if cached and cached.get("mtime") == mtime and cached.get("size") == size:
            w = cached.get("width", 0)
            h = cached.get("height", 0)
            if w and h:
                return (w, h)

        # Not cached or stale – compute and store
        try:
            with Image.open(path) as img:
                w, h = img.size
        except Exception:
            w, h = 0, 0

        self._metadata[path] = {
            "size": size,
            "mtime": mtime,
            "width": w,
            "height": h
        }
        return (w, h)

    def _update_metadata_background(self, files: List[str]):
        """Pre‑compute missing resolutions in a background thread."""
        for path in files:
            if self._stop_bg:
                break
            if path in self._metadata:
                continue
            self._get_resolution(path)
        self._save_metadata_cache()

    def search(self, query: str, page: int = 1, **kwargs) -> List[Dict[str, Any]]:
        folder = kwargs.get("download_folder", "./wallpapers")
        sort_by = kwargs.get("sort_by", "modified")

        now = time.time()
        cache_valid = (
            folder == self._last_folder and
            now - self._cache_timestamp < self._cache_ttl and
            self._all_files
        )

        if not cache_valid:
            self._all_files = self._get_image_files(folder)
            self._last_folder = folder
            self._cache_timestamp = now
            self._last_query = None

            # Stop previous background thread
            self._stop_bg = True
            if self._bg_thread and self._bg_thread.is_alive():
                self._bg_thread.join(timeout=0.5)

            # Start new background metadata updater
            self._stop_bg = False
            self._bg_thread = threading.Thread(
                target=self._update_metadata_background,
                args=(self._all_files,),
                daemon=True
            )
            self._bg_thread.start()

        # Filter by query
        if query != self._last_query:
            if query and query.strip():
                q = query.lower()
                self._filtered_files = [f for f in self._all_files if q in os.path.basename(f).lower()]
            else:
                self._filtered_files = list(self._all_files)
            self._last_query = query

        # Sort (using cached stats wherever possible)
        if sort_by == "name":
            self._filtered_files.sort(key=lambda f: os.path.basename(f).lower())
        elif sort_by == "size":
            def get_size(p):
                try:
                    return os.path.getsize(p)
                except OSError:
                    return 0
            self._filtered_files.sort(key=get_size, reverse=True)
        elif sort_by == "resolution":
            def get_pixels(p):
                cached = self._metadata.get(p, {})
                w = cached.get("width", 0)
                h = cached.get("height", 0)
                return w * h
            self._filtered_files.sort(key=get_pixels, reverse=True)
        else:  # modified
            def get_mtime(p):
                try:
                    return os.path.getmtime(p)
                except OSError:
                    return 0
            self._filtered_files.sort(key=get_mtime, reverse=True)

        limit = 24
        start = (page - 1) * limit
        end = start + limit
        page_files = self._filtered_files[start:end]

        # Build result list with actual resolution (fast, uses cache)
        results = []
        for f in page_files:
            cached = self._metadata.get(f, {})
            w = cached.get("width", 0)
            h = cached.get("height", 0)
            resolution_str = f"{w}x{h}" if w and h else "?x?"
            results.append({
                "path": f,
                "id": f,
                "resolution": resolution_str,
                "filename": os.path.basename(f),
            })
        return results

    def get_total_pages(self, query: str, **kwargs) -> int:
        limit = 24
        return math.ceil(len(self._filtered_files) / limit) if self._filtered_files else 1

    def get_thumbnail_url(self, wallpaper_data: Dict[str, Any]) -> str:
        return wallpaper_data.get("path", "")

    def get_download_url(self, wallpaper_data: Dict[str, Any]) -> str:
        return wallpaper_data.get("path", "")

    def get_wallpaper_id(self, wallpaper_data: Dict[str, Any]) -> str:
        return wallpaper_data.get("id", "")

    def get_file_extension(self, wallpaper_data: Dict[str, Any]) -> str:
        path = wallpaper_data.get("path", "")
        ext = os.path.splitext(path)[1].lstrip('.').lower()
        return ext if ext else "jpg"

    def get_resolution(self, wallpaper_data: Dict[str, Any]) -> str:
        return wallpaper_data.get("resolution", "?x?")

    def get_filters(self) -> Dict[str, Any]:
        return {
            "sort_by": {
                "type": "dropdown",
                "label": "Sort by",
                "options": [
                    {"id": "modified", "label": "Date Modified", "default": True},
                    {"id": "name", "label": "Name (A-Z)", "default": False},
                    {"id": "size", "label": "File Size", "default": False},
                    {"id": "resolution", "label": "Resolution", "default": False},
                ]
            }
        }

    def shutdown(self):
        """Cleanly stop background thread and save cache."""
        self._stop_bg = True
        if self._bg_thread and self._bg_thread.is_alive():
            self._bg_thread.join(timeout=1.0)
        self._save_metadata_cache()