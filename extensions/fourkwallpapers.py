import requests
import re
import math
import time
import hashlib
import threading
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Tuple, Optional
from bs4 import BeautifulSoup
from core.extension import WallpaperExtension


class FourKWallpapersExtension(WallpaperExtension):
    """High-performance extension for 4kwallpapers.com."""

    def __init__(self):
        super().__init__()
        self.name = "4kwallpapers"
        self.base_url = "https://4kwallpapers.com"

        self._cache_dir = Path.home() / ".cache" / "wallppy" / "4kwallpapers"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_file = self._cache_dir / "wallpapers.json"

        self._cached_results = []
        self._gallery_queue = []
        self._category_queue = []
        self._detail_queue = []
        self._scraped_galleries = set()
        self._scraped_categories = set()
        self._scraped_wallpaper_ids = set()
        self._detail_cache = {}

        self._last_query = ""
        self._lock = threading.RLock()
        self._background_thread = None
        self._stop_background = False
        self._executor = None

        self._load_cache()

    # ----------------------------------------------------------------------
    # Cache
    # ----------------------------------------------------------------------
    def _load_cache(self):
        try:
            if self._cache_file.exists():
                with open(self._cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                with self._lock:
                    self._cached_results = data.get('wallpapers', [])
                    self._scraped_wallpaper_ids = set(data.get('ids', []))
                    self._detail_cache = {wp['id']: wp for wp in self._cached_results}
                print(f"[4kwallpapers] Loaded {len(self._cached_results)} from cache.")
        except Exception as e:
            print(f"[4kwallpapers] Cache load error: {e}")

    def _save_cache(self):
        try:
            with self._lock:
                data = {'wallpapers': self._cached_results, 'ids': list(self._scraped_wallpaper_ids)}
            with open(self._cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[4kwallpapers] Cache save error: {e}")

    # ----------------------------------------------------------------------
    # Background fetching
    # ----------------------------------------------------------------------
    def _start_background_fetcher(self):
        if self._background_thread and self._background_thread.is_alive():
            return
        self._stop_background = False
        self._background_thread = threading.Thread(target=self._background_worker, daemon=True)
        self._background_thread.start()
        self._executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="4kwp")

    def _background_worker(self):
        while not self._stop_background:
            # Process listing pages
            url = None
            task_type = None
            with self._lock:
                if self._gallery_queue:
                    url = self._gallery_queue.pop(0)
                    task_type = 'gallery'
                elif self._category_queue:
                    url = self._category_queue.pop(0)
                    task_type = 'category'

            if url:
                print(f"[4kwallpapers] Scraping listing: {url}")
                items = self._scrape_listing_page(url)
                with self._lock:
                    if task_type == 'gallery':
                        self._scraped_galleries.add(url)
                    else:
                        self._scraped_categories.add(url)
                print(f"[4kwallpapers] Queued {len(items)} detail pages")
                continue  # no sleep

            # Process detail pages in larger batches
            batch = []
            with self._lock:
                while self._detail_queue and len(batch) < 20:
                    batch.append(self._detail_queue.pop(0))

            if batch:
                self._process_detail_batch(batch)
                continue

            time.sleep(0.1)  # short sleep when idle

    def _process_detail_batch(self, urls: List[str]):
        futures = [self._executor.submit(self._fetch_detail_page, url) for url in urls]
        new_wallpapers = []
        for future in as_completed(futures):
            try:
                wp = future.result(timeout=15)
                if wp:
                    new_wallpapers.append(wp)
            except Exception as e:
                pass  # ignore individual errors

        if new_wallpapers:
            with self._lock:
                for wp in new_wallpapers:
                    if wp['id'] not in self._scraped_wallpaper_ids:
                        self._scraped_wallpaper_ids.add(wp['id'])
                        self._cached_results.append(wp)
                        self._detail_cache[wp['id']] = wp
            # Save cache every ~100 wallpapers
            if len(self._cached_results) % 100 < len(new_wallpapers):
                self._save_cache()
            print(f"[4kwallpapers] Added {len(new_wallpapers)} wallpapers, total {len(self._cached_results)}")

    def _fetch_detail_page(self, url: str) -> Optional[Dict[str, Any]]:
        wall_id = self._extract_id_from_url(url)
        with self._lock:
            if wall_id in self._detail_cache:
                return None
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, timeout=10, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            download_link = soup.find('a', href=re.compile(r'/images/wallpapers/.*\.(jpe?g|png)$', re.I))
            if not download_link:
                download_link = soup.find('a', href=re.compile(r'\.(jpe?g|png)$', re.I))
            if not download_link:
                return None
            download_url = download_link.get('href')
            if download_url.startswith('/'):
                download_url = self.base_url + download_url

            title_tag = soup.find('h1') or soup.find('title')
            title = title_tag.get_text(strip=True) if title_tag else "Untitled"
            title = re.sub(r'\s*\(?\d+x\d+\)?\s*$', '', title).strip()

            resolution = "Unknown"
            res_match = re.search(r'-(\d+x\d+)-', download_url)
            if res_match:
                resolution = res_match.group(1)

            thumb_url = download_url
            meta_thumb = soup.find('meta', property='og:image')
            if meta_thumb and meta_thumb.get('content'):
                thumb_url = meta_thumb.get('content')
                if thumb_url.startswith('/'):
                    thumb_url = self.base_url + thumb_url

            if not wall_id:
                wall_id = hashlib.md5(url.encode()).hexdigest()[:8]

            return {
                "id": wall_id, "title": title, "url": url,
                "thumb": thumb_url, "direct_download": download_url, "resolution": resolution,
            }
        except Exception:
            return None

    def _extract_id_from_url(self, url: str) -> Optional[str]:
        match = re.search(r'-(\d+)\.html$', url)
        return match.group(1) if match else None

    # ----------------------------------------------------------------------
    # Listing scraping
    # ----------------------------------------------------------------------
    def _scrape_listing_page(self, url: str) -> List[str]:
        detail_urls = []
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, timeout=15, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            items = soup.find_all('p', class_='wallpapers__item')
            for item in items:
                a_tag = item.find('a', class_='wallpapers__canvas_image')
                if not a_tag:
                    a_tag = item.find('a', href=re.compile(r'\.html$'))
                if not a_tag:
                    continue
                href = a_tag.get('href')
                if href.startswith('/'):
                    href = self.base_url + href
                wall_id = self._extract_id_from_url(href)
                with self._lock:
                    if wall_id and wall_id in self._scraped_wallpaper_ids:
                        continue
                detail_urls.append(href)

            # Pagination
            if '/page/' not in url and '?page=' not in url:
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if '?page=' in href and href.startswith('/'):
                        next_url = self.base_url + href
                        with self._lock:
                            if next_url not in self._scraped_categories and next_url not in self._category_queue:
                                self._category_queue.append(next_url)
        except Exception as e:
            print(f"[4kwallpapers] Listing error {url}: {e}")

        with self._lock:
            for detail_url in detail_urls:
                self._detail_queue.append(detail_url)
        return detail_urls

    # ----------------------------------------------------------------------
    # Discovery
    # ----------------------------------------------------------------------
    def _fetch_gallery_list(self) -> List[str]:
        gallery_urls = []
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            response = requests.get(self.base_url, timeout=15, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.startswith('/') and href.endswith('/') and 'wallpaper' in href.lower():
                    if any(skip in href for skip in ['/cdn-cgi/', '/search/', '/tag/', '/recent/', '/popular/', '/page/']):
                        continue
                    full_url = self.base_url + href
                    if full_url not in gallery_urls:
                        gallery_urls.append(full_url)

            category_links = []
            for a in soup.select('.section-dropdown a[href]'):
                href = a.get('href')
                if href and href.startswith('/'):
                    full_url = self.base_url + href
                    if full_url not in category_links:
                        category_links.append(full_url)

            with self._lock:
                for cat_url in category_links:
                    if cat_url not in self._scraped_categories:
                        self._category_queue.append(cat_url)
            print(f"[4kwallpapers] Discovered {len(gallery_urls)} galleries, {len(category_links)} categories")
        except Exception as e:
            print(f"[4kwallpapers] Discovery error: {e}")
        return gallery_urls

    def _fetch_initial_wallpapers_sync(self):
        if self._cached_results:
            return
        print("[4kwallpapers] Fast initial fetch...")
        gallery_urls = self._fetch_gallery_list()
        with self._lock:
            self._gallery_queue = gallery_urls
            self._scraped_galleries = set()

        # Scrape first gallery and fetch up to 5 detail pages
        if gallery_urls:
            detail_urls = self._scrape_listing_page(gallery_urls[0])
            for url in detail_urls[:5]:
                wp = self._fetch_detail_page(url)
                if wp:
                    with self._lock:
                        if wp['id'] not in self._scraped_wallpaper_ids:
                            self._scraped_wallpaper_ids.add(wp['id'])
                            self._cached_results.append(wp)
                            self._detail_cache[wp['id']] = wp
        print(f"[4kwallpapers] Initial sync loaded {len(self._cached_results)} wallpapers")

    def _ensure_initial_data(self, query: str):
        with self._lock:
            if self._cached_results:
                return
        self._fetch_initial_wallpapers_sync()
        self._start_background_fetcher()

    def _ensure_page_available(self, page: int, limit: int = 24):
        needed = page * limit
        with self._lock:
            current = len(self._cached_results)
        if current >= needed:
            return
        waited = 0
        while current < needed and waited < 2:
            time.sleep(0.1)
            waited += 0.1
            with self._lock:
                current = len(self._cached_results)

    # ----------------------------------------------------------------------
    # Core methods
    # ----------------------------------------------------------------------
    def search(self, query: str, page: int = 1, **kwargs) -> List[Dict[str, Any]]:
        self._ensure_initial_data(query)
        self._ensure_page_available(page)

        with self._lock:
            if query:
                filtered = [wp for wp in self._cached_results if query.lower() in wp.get('title', '').lower()]
            else:
                filtered = self._cached_results.copy()

        filtered = self._apply_filters(filtered, **kwargs)
        limit = 24
        start = (page - 1) * limit
        end = start + limit
        return filtered[start:end]

    def get_total_pages(self, query: str, **kwargs) -> int:
        with self._lock:
            if query:
                filtered = [wp for wp in self._cached_results if query.lower() in wp.get('title', '').lower()]
            else:
                filtered = self._cached_results.copy()
        filtered = self._apply_filters(filtered, **kwargs)
        limit = 24
        actual_pages = math.ceil(len(filtered) / limit) if filtered else 1

        with self._lock:
            still_fetching = bool(self._gallery_queue or self._category_queue or self._detail_queue)
        return max(actual_pages, 50) if still_fetching else actual_pages

    # ----------------------------------------------------------------------
    # Filtering
    # ----------------------------------------------------------------------
    def _apply_filters(self, wallpapers, **kwargs):
        filtered = wallpapers.copy()
        resolution_filter = kwargs.get('resolution', '')
        if resolution_filter:
            filtered = [wp for wp in filtered if self._matches_resolution(wp, resolution_filter)]
        ratio_filter = kwargs.get('ratio', '')
        if ratio_filter:
            filtered = [wp for wp in filtered if self._matches_aspect_ratio(wp, ratio_filter)]
        sort_by = kwargs.get('sort_by', 'recent')
        if sort_by == 'resolution':
            filtered.sort(key=lambda wp: self._get_pixel_count(wp), reverse=True)
        elif sort_by == 'aspect_ratio':
            filtered.sort(key=lambda wp: (self._get_aspect_ratio_string(wp), self._get_pixel_count(wp)), reverse=True)
        elif sort_by == 'title':
            filtered.sort(key=lambda wp: wp.get('title', '').lower())
        return filtered

    def _get_resolution_tuple(self, wp):
        res_str = wp.get('resolution', 'Unknown')
        if res_str == 'Unknown':
            return (0, 0)
        match = re.search(r'(\d+)\s*[xX×]\s*(\d+)', res_str)
        if match:
            return (int(match.group(1)), int(match.group(2)))
        url = wp.get('direct_download', '')
        match = re.search(r'-(\d+)x(\d+)-', url)
        if match:
            return (int(match.group(1)), int(match.group(2)))
        return (0, 0)

    def _get_pixel_count(self, wp):
        w, h = self._get_resolution_tuple(wp)
        return w * h

    def _get_aspect_ratio_float(self, wp):
        w, h = self._get_resolution_tuple(wp)
        return w / h if h != 0 else 0.0

    def _get_aspect_ratio_string(self, wp):
        ratio = self._get_aspect_ratio_float(wp)
        if ratio == 0:
            return 'Unknown'
        common = {16/9: '16:9', 16/10: '16:10', 21/9: '21:9', 4/3: '4:3', 5/4: '5:4', 1/1: '1:1', 9/16: '9:16'}
        for val, label in common.items():
            if abs(ratio - val) < 0.02:
                return label
        return f"{ratio:.2f}"

    def _matches_resolution(self, wp, filter_val):
        w, h = self._get_resolution_tuple(wp)
        pixels = w * h
        if filter_val == '4k': return w >= 3840 or h >= 2160
        if filter_val == '1440p': return (w >= 2560 or h >= 1440) and pixels < 3840*2160
        if filter_val == '1080p': return (w >= 1920 or h >= 1080) and pixels < 2560*1440
        if filter_val == '720p': return (w >= 1280 or h >= 720) and pixels < 1920*1080
        if filter_val == 'ultrawide': return w / h >= 2.0 if h > 0 else False
        return True

    def _matches_aspect_ratio(self, wp, filter_val):
        actual = self._get_aspect_ratio_float(wp)
        target_map = {'16:9': 16/9, '16:10': 16/10, '21:9': 21/9, '32:9': 32/9, '4:3': 4/3, '5:4': 5/4, '1:1': 1, '9:16': 9/16}
        target = target_map.get(filter_val)
        return abs(actual - target) < 0.05 if target else False

    # ----------------------------------------------------------------------
    # Required methods
    # ----------------------------------------------------------------------
    def get_thumbnail_url(self, wp): return wp.get('thumb', '')
    def get_download_url(self, wp): return wp.get('direct_download', wp.get('url', ''))
    def get_wallpaper_id(self, wp): return str(wp.get('id', ''))
    def get_file_extension(self, wp): return 'png' if 'png' in wp.get('direct_download', '').lower() else 'jpg'
    def get_resolution(self, wp): return wp.get('resolution', 'Unknown')

    def get_filters(self):
        return {
            "sort_by": {
                "type": "dropdown", "label": "Sort by",
                "options": [
                    {"id": "recent", "label": "Recent", "default": True},
                    {"id": "resolution", "label": "Resolution (High to Low)", "default": False},
                    {"id": "aspect_ratio", "label": "Aspect Ratio", "default": False},
                    {"id": "title", "label": "Title (A-Z)", "default": False},
                ]
            },
            "resolution": {
                "type": "dropdown", "label": "Resolution",
                "options": [
                    {"id": "", "label": "Any", "default": True},
                    {"id": "4k", "label": "4K & Above", "default": False},
                    {"id": "1440p", "label": "1440p (QHD)", "default": False},
                    {"id": "1080p", "label": "1080p (Full HD)", "default": False},
                    {"id": "720p", "label": "720p (HD)", "default": False},
                    {"id": "ultrawide", "label": "Ultrawide (21:9+)", "default": False},
                ]
            },
            "ratio": {
                "type": "dropdown", "label": "Aspect Ratio",
                "options": [
                    {"id": "", "label": "Any", "default": True},
                    {"id": "16:9", "label": "16:9 (Widescreen)", "default": False},
                    {"id": "16:10", "label": "16:10", "default": False},
                    {"id": "21:9", "label": "21:9 (Ultrawide)", "default": False},
                    {"id": "32:9", "label": "32:9 (Super Ultrawide)", "default": False},
                    {"id": "4:3", "label": "4:3 (Standard)", "default": False},
                    {"id": "5:4", "label": "5:4", "default": False},
                    {"id": "1:1", "label": "1:1 (Square)", "default": False},
                    {"id": "9:16", "label": "9:16 (Portrait)", "default": False},
                ]
            }
        }

    def __del__(self):
        self._stop_background = True
        if self._executor:
            self._executor.shutdown(wait=False)
        self._save_cache()
    
    # In fourkwallpapers.py
    def shutdown(self):
        self._stop_background = True
        if self._executor:
            self._executor.shutdown(wait=False)
        self._save_cache()