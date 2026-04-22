import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from core.extension import WallpaperExtension, register_extension


CATEGORIES = [
    {"id": "Video Game", "label": "Video Game"},
    {"id": "Anime", "label": "Anime"},
    {"id": "Movie", "label": "Movie"},
    {"id": "TV Series", "label": "TV Series"},
    {"id": "Abstract", "label": "Abstract"},
    {"id": "Animals", "label": "Animals"},
    {"id": "Celebrity", "label": "Celebrity"},
    {"id": "Comics", "label": "Comics"},
    {"id": "Digital Art", "label": "Digital Art"},
    {"id": "Fantasy", "label": "Fantasy"},
    {"id": "Nature", "label": "Nature"},
    {"id": "Scenery", "label": "Scenery"},
    {"id": "Sci-Fi", "label": "Sci-Fi"},
    {"id": "Space", "label": "Space"},
]

RESOLUTIONS = [
    {"id": "pc-4k", "label": "3840x2160 (4K PC)", "resolution": "3840x2160"},
    {"id": "pc-2k", "label": "2560x1440 (2K PC)", "resolution": "2560x1440"},
    {"id": "pc-hd", "label": "1920x1080 (HD PC)", "resolution": "1920x1080"},
    {"id": "phone-4k", "label": "2160x3840 (4K Phone)", "resolution": "2160x3840"},
    {"id": "phone-hd", "label": "1080x1920 (HD Phone)", "resolution": "1080x1920"},
]


class UHDWallpaperExtension(WallpaperExtension):
    """UHDPaper.com scraper implementation."""
    
    def __init__(self):
        super().__init__()
        self.name = "UHDPaper"
        self.base_url = "https://www.uhdpaper.com"
        self.search_url = f"{self.base_url}/search"
        self._last_total = 0
        
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Referer": "https://www.uhdpaper.com/",
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
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Referer": "https://www.uhdpaper.com/",
        }
    
    def _get_thumbnail_url_from_page(self, page_url: str) -> Optional[str]:
        try:
            response = self.session.get(page_url, headers=self._get_headers(), timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            img_tag = soup.find("img", {"class": "thumbnail"})
            if img_tag and img_tag.get("src"):
                return img_tag["src"]
            
            for img in soup.find_all("img"):
                src = img.get("src", "")
                if "img.uhdpaper.com/wallpaper/" in src and "@" in src:
                    return src
            
            return None
        except Exception:
            return None
    
    def search(self, query: str, page: int = 1, **kwargs) -> List[Dict[str, Any]]:
        start = (page - 1) * 50
        
        # Use categories filter if no query
        category = kwargs.get('categories', '')
        search_query = category if (category and not query) else (query if query else "*")
        
        params = {
            "q": search_query,
            "max-results": 24,
            "start": start,
            "by-date": "true",
        }
        
        try:
            response = self.session.get(
                self.search_url,
                params=params,
                headers=self._get_headers(),
                timeout=15
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            wp_boxes = soup.find_all("div", class_="wp_box")
            
            results = []
            
            for wp_box in wp_boxes:
                anchor = wp_box.find("a", href=lambda x: x and "/20" in x)
                if not anchor:
                    continue
                
                href = anchor.get("href")
                slug = href.rstrip("/").split("/")[-1]
                wallpaper_id = slug.replace(".html", "")
                
                snippet = wp_box.find("div", class_="snippet-title")
                title = wallpaper_id
                thumbnail = None
                resolution = "?"
                
                if snippet:
                    h2 = snippet.find("h2")
                    if h2:
                        title = h2.get_text(strip=True)
                    img = snippet.find("img")
                    if img:
                        thumbnail = img.get("src") or img.get("data-src")
                
                b_tags = wp_box.find_all("b")
                for b in b_tags:
                    text = b.get_text(strip=True)
                    if "4K" in text or "8K" in text:
                        resolution = text
                        break
                
                results.append({
                    "id": wallpaper_id,
                    "title": title,
                    "page_url": href,
                    "thumbnail_url": thumbnail or "",
                    "resolution": resolution,
                    "query": query,
                })
            
            self._last_total = len(results)
            
            return results
        except requests.exceptions.RequestException as e:
            print(f"UHDPaper error: {e}")
            return []
        except Exception as e:
            print(f"UHDPaper unexpected error: {e}")
            return []
    
    def get_total_pages(self, query: str, **kwargs) -> int:
        return 999
    
    def get_thumbnail_url(self, wallpaper_data: Dict[str, Any]) -> str:
        url = wallpaper_data.get("thumbnail_url", "")
        if url:
            url = url.replace("@5@n", "@5@n")
        return url
    
    def get_download_url(self, wallpaper_data: Dict[str, Any], resolution: str = None) -> str:
        # Use thumbnail URL directly - server returns a valid image
        # The -pc-4k suffix requires proper Referer header which workers don't have
        return wallpaper_data.get("thumbnail_url", "")
    
    def get_wallpaper_id(self, wallpaper_data: Dict[str, Any]) -> str:
        return str(wallpaper_data.get("id", ""))
    
    def get_file_extension(self, wallpaper_data: Dict[str, Any]) -> str:
        return "jpg"
    
    def get_resolution(self, wallpaper_data: Dict[str, Any]) -> str:
        res = wallpaper_data.get("resolution", "?")
        if "4K" in res:
            return "3840x2160"
        elif "8K" in res:
            return "7680x4320"
        return res
    
    def get_filters(self) -> Dict[str, Any]:
        return {
            "categories": {
                "type": "dropdown",
                "label": "Category",
                "options": [{"id": cat["id"], "label": cat["label"], "default": cat["id"] == "Anime"} for cat in CATEGORIES]
            },
            "resolution": {
                "type": "dropdown",
                "label": "Resolution",
                "options": [{"id": r["id"], "label": r["label"], "default": r["id"] == "pc-hd"} for r in RESOLUTIONS]
            },
        }


