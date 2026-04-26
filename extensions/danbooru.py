import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import List, Dict, Any
from core.extension import WallpaperExtension


class DanbooruExtension(WallpaperExtension):
    """Danbooru API implementation with connection pooling."""
    
    def __init__(self, username: str = None, api_key: str = None):
        super().__init__()
        self.name = "Danbooru"
        self.base_url = "https://danbooru.donmai.us"
        self.username = username
        self.api_key = api_key
        self._last_response = None
        
        # Setup connection pooling
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(
            pool_connections=3,
            pool_maxsize=5,
            max_retries=retry_strategy
        )
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
    
    def _auth_params(self) -> Dict[str, str]:
        if self.username and self.api_key:
            return {"login": self.username, "api_key": self.api_key}
        return {}
    
    def search(self, query: str, page: int = 1, **kwargs) -> List[Dict[str, Any]]:
        tags = query.strip().split() if query else ["order:rank"]
        if query:
            safe_query = query.strip().replace(' ', '_')
            tags.append(safe_query)
        
        rating = kwargs.get("rating")
        if rating:
            tags.append(f"rating:{rating}")
        
        limit = 24
        params = {
            "limit": limit,
            "page": page,
            "tags": " ".join(tags),
            **self._auth_params()
        }
        
        headers = {
            "User-Agent": "wallppy/1.0"
        }
        
        url = f"{self.base_url}/posts.json"
        try:
            response = self.session.get(url, params=params, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and not data.get("success", True):
                raise Exception(data.get("message", "Unknown API error"))
            return data if isinstance(data, list) else []
        except Exception:
            return []
    
    def get_total_pages(self, query: str, **kwargs) -> int:
        return 999
    
    def get_thumbnail_url(self, wallpaper_data: Dict[str, Any]) -> str:
        return wallpaper_data.get("preview_file_url") or wallpaper_data.get("large_file_url", "")
    
    def get_download_url(self, wallpaper_data: Dict[str, Any]) -> str:
        return wallpaper_data.get("file_url") or wallpaper_data.get("large_file_url", "")
    
    def get_wallpaper_id(self, wallpaper_data: Dict[str, Any]) -> str:
        return str(wallpaper_data.get("id", ""))
    
    def get_file_extension(self, wallpaper_data: Dict[str, Any]) -> str:
        return wallpaper_data.get("file_ext", "jpg").lstrip('.')
    
    def get_resolution(self, wallpaper_data: Dict[str, Any]) -> str:
        w = wallpaper_data.get("image_width", 0)
        h = wallpaper_data.get("image_height", 0)
        return f"{w}x{h}" if w and h else "?x?"
    
    def get_filters(self) -> Dict[str, Any]:
        return {
            "rating": {
                "type": "dropdown",
                "label": "Rating",
                "options": [
                    {"id": "g", "label": "General (SFW)", "default": True},
                    {"id": "s", "label": "Sensitive (Sketchy)", "default": False},
                    {"id": "q", "label": "Questionable", "default": False},
                    {"id": "e", "label": "Explicit (NSFW)", "default": False}
                ]
            }
        }