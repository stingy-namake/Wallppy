import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import List, Dict, Any
from core.extension import WallpaperExtension


class WallhavenExtension(WallpaperExtension):
    """Wallhaven.cc API implementation with connection pooling."""
    
    def __init__(self, api_key: str = None):
        super().__init__()
        self.name = "Wallhaven"
        self.api_url = "https://wallhaven.cc/api/v1/search"
        self.api_key = api_key
        self._last_meta = {}
        
        # Setup connection pooling with retries
        self.session = requests.Session()
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
    
    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "User-Agent": "wallppy/1.0 (https://github.com/stingy-namake/wallppy)"
        }
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers
    
    def _build_category_string(self, categories_dict: str) -> str:
        """Build category string for Wallhaven API."""
        if isinstance(categories_dict, str) and len(categories_dict) == 3:
            return categories_dict
        return "111"
    
    def _build_purity_string(self, purity_dict: str) -> str:
        """Build purity string for Wallhaven API."""
        if isinstance(purity_dict, str) and len(purity_dict) == 3:
            return purity_dict
        return "100"
    
    def _strip_wallpaper_data(self, wallpaper: Dict[str, Any]) -> Dict[str, Any]:
        """Remove unnecessary data to save memory."""
        return {
            "id": wallpaper.get("id", ""),
            "path": wallpaper.get("path", ""),
            "thumbs": {
                "large": wallpaper.get("thumbs", {}).get("large", "")
            },
            "resolution": wallpaper.get("resolution", "?x?"),
            "file_type": wallpaper.get("file_type", "image/jpeg"),
        }
    
    def search(self, query: str, page: int = 1, **kwargs) -> List[Dict[str, Any]]:
        # Handle categories
        category_val = kwargs.get("categories", kwargs.get("category", "111"))
        category = self._build_category_string(category_val)
        
        # Handle purity
        purity_val = kwargs.get("purity", "100")
        purity = self._build_purity_string(purity_val)
        
        # Build API parameters
        params = {
            "q": query if query else "",
            "categories": category,
            "purity": purity,
            "page": page,
            "per_page": 24,
        }
        
        # Add sorting parameters
        sorting = kwargs.get("sorting", "date_added")
        params["sorting"] = sorting
        params["order"] = "desc"
        
        if sorting == "toplist":
            top_range = kwargs.get("top_range", "1M")
            params["topRange"] = top_range
        
        # Add resolution filter
        resolution = kwargs.get("resolution", "")
        if resolution:
            params["resolutions"] = resolution
        
        # Add aspect ratio filter
        ratio = kwargs.get("ratio", "")
        if ratio:
            params["ratios"] = ratio
                
        try:
            response = self.session.get(
                self.api_url,
                params=params,
                headers=self._get_headers(),
                timeout=15
            )
            response.raise_for_status()
            data = response.json()
            self._last_meta = data.get("meta", {})
            
            # Strip unnecessary data to save memory
            raw_data = data.get("data", [])
            stripped_data = [self._strip_wallpaper_data(wp) for wp in raw_data]
            
            return stripped_data
        except requests.exceptions.RequestException as e:
            print(f"Wallhaven error: {e}")
            return []
        except Exception as e:
            print(f"Wallhaven unexpected error: {e}")
            return []
    
    def get_total_pages(self, query: str, **kwargs) -> int:
        return self._last_meta.get("last_page", 1)
    
    def get_thumbnail_url(self, wallpaper_data: Dict[str, Any]) -> str:
        return wallpaper_data.get("thumbs", {}).get("large", "")
    
    def get_download_url(self, wallpaper_data: Dict[str, Any]) -> str:
        return wallpaper_data.get("path", "")
    
    def get_wallpaper_id(self, wallpaper_data: Dict[str, Any]) -> str:
        return str(wallpaper_data.get("id", ""))
    
    def get_file_extension(self, wallpaper_data: Dict[str, Any]) -> str:
        file_type = wallpaper_data.get("file_type", "image/jpeg")
        if "jpeg" in file_type or "jpg" in file_type:
            return "jpg"
        elif "png" in file_type:
            return "png"
        return "jpg"
    
    def get_resolution(self, wallpaper_data: Dict[str, Any]) -> str:
        return wallpaper_data.get("resolution", "?x?")
    
    def get_filters(self) -> Dict[str, Any]:
        return {
            "categories": {
                "type": "checkboxes",
                "label": "Categories",
                "options": [
                    {"id": "general", "label": "General", "default": False},
                    {"id": "anime", "label": "Anime", "default": True},
                    {"id": "people", "label": "People", "default": False}
                ]
            },
            "purity": {
                "type": "checkboxes",
                "label": "Content",
                "options": [
                    {"id": "sfw", "label": "SFW", "default": True},
                    {"id": "sketchy", "label": "Sketchy", "default": False},
                    {"id": "nsfw", "label": "NSFW", "default": False, "requires_api_key": True}
                ]
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
                    {"id": "toplist", "label": "Toplist", "default": False}
                ]
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
                    {"id": "1y", "label": "Last Year", "default": False}
                ]
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
                    {"id": "2560x1080", "label": "2560x1080 (UltraWide)", "default": False}
                ]
            },
            "ratio": {
                "type": "checkboxes",
                "label": "Aspect Ratio",
                "options": [
                    {"id": "16x9", "label": "16:9", "default": False},
                    {"id": "16x10", "label": "16:10", "default": False},
                    {"id": "21x9", "label": "21:9", "default": False},
                    {"id": "32x9", "label": "32:9", "default": False},
                    {"id": "4x3", "label": "4:3", "default": False},
                    {"id": "5x4", "label": "5:4", "default": False},
                    {"id": "9x16", "label": "9:16 (Mobile)", "default": False},
                    {"id": "1x1", "label": "1:1", "default": False}
                ]
            }
        }