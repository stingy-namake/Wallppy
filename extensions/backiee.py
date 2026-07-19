import os
import subprocess
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from core.extension import WallpaperExtension, register_extension
import logging

logger = logging.getLogger("wallppy.backiee")


CATEGORIES = [
    {"id": "abstract", "label": "Abstract"},
    {"id": "animals", "label": "Animals"},
    {"id": "anime", "label": "Anime"},
    {"id": "car", "label": "Car"},
    {"id": "celebration", "label": "Celebration"},
    {"id": "city", "label": "City"},
    {"id": "fantasy", "label": "Fantasy"},
    {"id": "flowers", "label": "Flowers"},
    {"id": "food", "label": "Food"},
    {"id": "funny", "label": "Funny"},
    {"id": "life", "label": "Life"},
    {"id": "military", "label": "Military"},
    {"id": "music", "label": "Music"},
    {"id": "nature", "label": "Nature"},
    {"id": "quotes", "label": "Quotes"},
    {"id": "space", "label": "Space"},
    {"id": "sports", "label": "Sports"},
    {"id": "technology", "label": "Technology"},
    {"id": "textures", "label": "Textures"},
    {"id": "video-games", "label": "Video Games"},
]

RESOLUTIONS = [
    {"id": "1000x563", "label": "1000x563 (HD)", "width": 1000, "height": 563},
    {"id": "3840x2160", "label": "3840x2160 (4K)", "width": 3840, "height": 2160},
]


_cached_resolutions = {}

class BackieeExtension(WallpaperExtension):
    """backiee.com scraper implementation."""
    
    def __init__(self):
        super().__init__()
        self.name = "Backiee"
        self.base_url = "https://backiee.com"
        self._last_total = 0
        self._total_pages = 0
        self._seen_ids = set()
        self._max_page_with_results = 0
        
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://backiee.com/",
        })
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(
            pool_connections=5,
            pool_maxsize=10,
            max_retries=retry_strategy
        )
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
    
    def _get_download_url_from_page(self, page_url: str, wall_id: str) -> str:
        img_id = str(int(wall_id) + 100000)
        
        # Try requests first, fall back to curl for cloudflare-blocked binary
        try:
            from core.workers import get_session
            session = get_session()
            response = session.get(page_url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            download_btn = soup.find('button', {'data-download-btn': True})
            if download_btn:
                file_url = download_btn.get('data-file-url', '')
                if file_url:
                    return file_url
            return f"{self.base_url}/static/wallpapers/3840x2160/{img_id}.jpg"
        except Exception as e:
            logger.warning(f"Backiee get_download_url_from_page requests failed, trying curl: {e}")
            try:
                curl_env = os.environ.copy()
                curl_env["LD_LIBRARY_PATH"] = "/usr/lib:/lib"
                result = subprocess.run(
                    ["curl", "-sL", "--max-time", "15",
                     "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                     "-H", "Referer: https://backiee.com/",
                     page_url],
                    capture_output=True, text=True,
                    env=curl_env
                )
                soup = BeautifulSoup(result.stdout, "html.parser")
                download_btn = soup.find('button', {'data-download-btn': True})
                if download_btn:
                    file_url = download_btn.get('data-file-url', '')
                    if file_url:
                        return file_url
            except Exception as e2:
                logger.error(f"Backiee curl fallback also failed: {e2}")
            
            return f"{self.base_url}/static/wallpapers/3840x2160/{img_id}.jpg"
    
    def _build_url(self, query: str, page: int) -> str:
        if query:
            query_lower = query.lower().strip()
            if not query_lower:
                return f"{self.base_url}/latest?page={page}"
            for cat in CATEGORIES:
                if cat["id"].lower() == query_lower:
                    return f"{self.base_url}/categories/{cat['id']}/?page={page}"
            return f"{self.base_url}/search/{query_lower}?page={page}"
        return f"{self.base_url}/latest?page={page}"
    
    def search(self, query: str, page: int = 1, **kwargs) -> List[Dict[str, Any]]:
        category = kwargs.get('categories', '')
        if category and not query:
            query = category
        
        url = self._build_url(query, page)
        
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            page_html = response.text
        except Exception as e:
            # Use curl as fallback - binary's bundled OpenSSL is too old for backiee's Cloudflare
            # but system curl links to system SSL which works. Force LD to find system libs.
            logger.warning(f"Backiee requests failed, falling back to curl: {e}")
            try:
                curl_env = os.environ.copy()
                # Prefer system SSL over bundled one
                curl_env["LD_LIBRARY_PATH"] = "/usr/lib:/lib"
                result = subprocess.run(
                    ["curl", "-sL", "--max-time", "15", 
                     "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                     "-H", "Referer: https://backiee.com/",
                     url],
                    capture_output=True, text=True,
                    env=curl_env
                )
                page_html = result.stdout
            except Exception as e2:
                logger.error(f"Backiee curl fallback also failed: {e2}")
                return []
        
        try:
            soup = BeautifulSoup(page_html, "html.parser")
            
            wallpapers = []
            seen_ids = set()
            
            links = soup.find_all('a', href=lambda x: x and '/wallpaper/' in str(x))
            
            for link in links:
                href = link.get('href', '')
                parts = href.rstrip('/').split('/')
                if not parts[-1].isdigit():
                    continue
                wall_id = parts[-1]
                
                if wall_id in seen_ids:
                    continue
                seen_ids.add(wall_id)
                
                slug = href.replace(self.base_url, '').strip('/')
                
                # Image ID = page ID + 100000
                img_id = str(int(wall_id) + 100000)
                
                wallpapers.append({
                    "id": wall_id,
                    "img_id": img_id,
                    "slug": slug,
                    "title": slug.replace('-', ' ').replace('/', ' ').title(),
                    "page_url": href,
                    "thumbnail_url": f"{self.base_url}/static/wallpapers/456x257/{img_id}.jpg",
                    "resolution": "3840x2160",
                    "query": query,
                })
            
            self._last_total = len(wallpapers)
            
            if len(wallpapers) > 24:
                wallpapers = wallpapers[:24]
            
            return wallpapers
        except Exception as e:
            logger.error(f"Backiee search failed for '{query}': {e}")
            return []
    
    def get_total_pages(self, query: str, **kwargs) -> int:
        if self._last_total >= 10:
            return 999
        return self._last_total if self._last_total > 0 else 1
    
    def get_thumbnail_url(self, wallpaper_data: Dict[str, Any]) -> str:
        return wallpaper_data.get("thumbnail_url", "")
    
    def get_download_url(self, wallpaper_data: Dict[str, Any], resolution: str = None) -> str:
        urls = self.get_download_urls_by_priority(wallpaper_data)
        return urls[0] if urls else ""
    
    def get_download_urls_by_priority(self, wallpaper_data: Dict[str, Any]) -> List[str]:
        img_id = wallpaper_data.get("img_id", wallpaper_data.get("id", ""))
        return [
            f"{self.base_url}/static/wallpapers/{r['id']}/{img_id}.jpg"
            for r in RESOLUTIONS
        ]
    
    def get_wallpaper_id(self, wallpaper_data: Dict[str, Any]) -> str:
        return str(wallpaper_data.get("id", ""))
    
    def get_file_extension(self, wallpaper_data: Dict[str, Any]) -> str:
        return "jpg"
    
    def get_resolution(self, wallpaper_data: Dict[str, Any]) -> str:
        return wallpaper_data.get("resolution", "?") or "?"
    
    def get_available_resolutions(self, wallpaper_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []
    
    def get_filters(self) -> Dict[str, Any]:
        return {
            "categories": {
                "type": "dropdown",
                "label": "Category",
                "options": [{"id": cat["id"], "label": cat["label"], "default": cat["id"] == "anime"} for cat in CATEGORIES]
            },
        }
    
    def get_download_url_for_set(self, wallpaper_data: Dict[str, Any]) -> str:
        page_url = wallpaper_data.get("page_url", "")
        wall_id = wallpaper_data.get("id", "")
        
        if page_url and wall_id:
            try:
                return self._get_download_url_from_page(page_url, wall_id)
            except Exception:
                pass
        
        img_id = wallpaper_data.get("img_id", wallpaper_data.get("id", ""))
        return f"{self.base_url}/static/wallpapers/3840x2160/{img_id}.jpg"