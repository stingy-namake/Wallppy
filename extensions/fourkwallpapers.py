import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
import urllib.parse
from core.extension import WallpaperExtension, register_extension


CATEGORIES = [
    {"id": "abstract", "label": "Abstract"},
    {"id": "animals", "label": "Animals"},
    {"id": "anime", "label": "Anime"},
    {"id": "architecture", "label": "Architecture"},
    {"id": "bikes", "label": "Bikes"},
    {"id": "black-dark", "label": "Black/Dark"},
    {"id": "cars", "label": "Cars"},
    {"id": "celebrations", "label": "Celebrations"},
    {"id": "cute", "label": "Cute"},
    {"id": "fantasy", "label": "Fantasy"},
    {"id": "flowers", "label": "Flowers"},
    {"id": "food", "label": "Food"},
    {"id": "games", "label": "Games"},
    {"id": "gradients", "label": "Gradients"},
    {"id": "graphics-cgi", "label": "CGI"},
    {"id": "lifestyle", "label": "Lifestyle"},
    {"id": "love", "label": "Love"},
    {"id": "military", "label": "Military"},
    {"id": "minimal", "label": "Minimal"},
    {"id": "movies", "label": "Movies"},
    {"id": "music", "label": "Music"},
    {"id": "nature", "label": "Nature"},
    {"id": "people", "label": "People"},
    {"id": "photography", "label": "Photography"},
    {"id": "quotes", "label": "Quotes"},
    {"id": "sci-fi", "label": "Sci-Fi"},
    {"id": "space", "label": "Space"},
    {"id": "sports", "label": "Sports"},
    {"id": "technology", "label": "Technology"},
    {"id": "world", "label": "World"},
]

RESOLUTIONS = [
    {"id": "3840x2160", "label": "3840x2160 (4K)", "width": 3840, "height": 2160},
    {"id": "5120x2880", "label": "5120x2880 (5K)", "width": 5120, "height": 2880},
    {"id": "2560x1440", "label": "2560x1440 (2K)", "width": 2560, "height": 1440},
    {"id": "1920x1080", "label": "1920x1080 (Full HD)", "width": 1920, "height": 1080},
    {"id": "3440x1440", "label": "3440x1440 (UltraWide)", "width": 3440, "height": 1440},
    {"id": "1080x1920", "label": "1080x1920 (Mobile)", "width": 1080, "height": 1920},
]


class FourKWallpapersExtension(WallpaperExtension):
    """4kwallpapers.com scraper implementation."""
    
    def __init__(self):
        super().__init__()
        self.name = "4kwallpapers"
        self.base_url = "https://4kwallpapers.com"
        self._last_total = 0
        self._total_pages = 0
        self._last_query = ""
        self._seen_ids = set()
        self._max_page_with_results = 0
        
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
        return {
            "User-Agent": "wallppy/1.0 (https://github.com/stingy-namake/wallppy)"
        }
    
    def _build_url(self, query: str, page: int) -> str:
        if query:
            query_lower = query.lower().strip()
            if not query_lower:
                return f"{self.base_url}/?page={page}"
            for cat in CATEGORIES:
                if cat["id"].lower() == query_lower or cat["label"].lower() == query_lower:
                    return f"{self.base_url}/{cat['id']}/?page={page}"
            encoded = urllib.parse.quote(query)
            return f"{self.base_url}/search/{encoded}?page={page}"
        return f"{self.base_url}/?page={page}"
    
    def search(self, query: str, page: int = 1, **kwargs) -> List[Dict[str, Any]]:
        category = kwargs.get('categories', '')
        if category and not query:
            query = category
        
        # Reset pagination tracking on new search
        if page == 1 or query != self._last_query:
            self._total_pages = 0
            self._last_query = query
            self._seen_ids = set()
            self._max_page_with_results = 0
        
        url = self._build_url(query, page)
        
        try:
            response = self.session.get(
                url,
                headers=self._get_headers(),
                timeout=15
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            wallpapers = []
            seen_ids = set()
            
            items = soup.find_all('p', class_='wallpapers__item')
            if not items:
                items = soup.find_all('div', class_='wallpapers__item')
            
            for item in items:
                wallpaper = self._extract_wallpaper_data(item, query)
                if wallpaper and wallpaper.get('id') not in seen_ids:
                    wallpapers.append(wallpaper)
            
            if wallpapers:
                self._max_page_with_results = page
            
            # Track new unique IDs in this page
            new_ids_this_page = set()
            for w in wallpapers:
                wid = w.get('id')
                if wid and wid not in self._seen_ids:
                    new_ids_this_page.add(wid)
            
            # Check if we've reached the end: same results on consecutive pages
            # indicates site has no more unique results
            if page > 1 and len(new_ids_this_page) == 0 and len(wallpapers) > 0:
                # No new IDs this page, all are duplicates - exhausted
                self._total_pages = self._max_page_with_results
                return []
            
            # Update seen IDs
            for wid in new_ids_this_page:
                self._seen_ids.add(wid)
            
            self._last_total = len(wallpapers)
            
            # Detect pagination: check if pagination links exist on page
            pagination = soup.find_all('a', class_='wallpapers__pagination')
            if not pagination:
                pagination = soup.find_all('div', class_='pagination')
            if not pagination:
                pagination = soup.find_all('nav', class_='pagination')
            
            # Get actual total pages from pagination if available
            if pagination:
                page_numbers = []
                for p in pagination:
                    for a in p.find_all('a'):
                        text = a.get_text(strip=True)
                        if text.isdigit():
                            page_numbers.append(int(text))
                if page_numbers:
                    self._total_pages = max(page_numbers)
            
            # If no results, we've reached the end
            if len(wallpapers) == 0:
                return []
            
            if len(wallpapers) > 24:
                wallpapers = wallpapers[:24]
            
            return wallpapers
        except requests.exceptions.RequestException:
            return []
        except Exception:
            return []
    
    def _extract_wallpaper_data(self, item, query: str) -> Optional[Dict[str, Any]]:
        link = item.find('a', href=lambda x: x and '.html' in x and '/images/' not in x)
        
        if not link:
            return None
        
        href = link.get('href', '')
        if not href:
            return None
        
        if '/images/wallpapers/' in href:
            return None
        
        if not href.startswith('http'):
            href = self.base_url + href
        
        slug = href.rstrip('/').split('/')[-1].replace('.html', '')
        
        wallpaper_id = None
        for part in reversed(slug.split('-')):
            if part.isdigit():
                wallpaper_id = part
                break
        if not wallpaper_id:
            wallpaper_id = slug
        
        thumbnail = None
        parent = item
        img = parent.find('img', src=True)
        if not img:
            grandparent = parent.parent
            if grandparent:
                img = grandparent.find('img', src=True)
        if not img:
            for c in parent.children:
                if hasattr(c, 'find'):
                    img = c.find('img', src=True)
                    if img:
                        break
        if img:
            thumbnail = img.get('src') or img.get('data-src') or img.get('data-lazy')
            if thumbnail and not thumbnail.startswith('http'):
                thumbnail = self.base_url + thumbnail
        
        title = slug.replace('-', ' ').title()
        
        return {
            "id": wallpaper_id,
            "slug": slug,
            "title": title,
            "page_url": href,
            "thumbnail_url": thumbnail or "",
            "resolution": "?",
            "query": query,
        }
    
    def get_total_pages(self, query: str, **kwargs) -> int:
        if self._total_pages > 0:
            return self._total_pages
        # Fallback: use reasonable default, will stop on empty results
        return 999
    
    def get_thumbnail_url(self, wallpaper_data: Dict[str, Any]) -> str:
        url = wallpaper_data.get("thumbnail_url", "")
        return url
    
    def get_download_url(self, wallpaper_data: Dict[str, Any], resolution: str = None) -> str:
        wallpaper_id = wallpaper_data.get("id", "")
        slug = wallpaper_data.get("slug", wallpaper_id)
        
        res_id = resolution if resolution else "3840x2160"
        
        if wallpaper_id.isdigit():
            return f"{self.base_url}/images/wallpapers/{slug}-{res_id}-{wallpaper_id}.jpg"
        
        return f"{self.base_url}/images/wallpapers/{slug}-{res_id}.jpg"
    
    def get_wallpaper_id(self, wallpaper_data: Dict[str, Any]) -> str:
        return str(wallpaper_data.get("id", ""))
    
    def get_file_extension(self, wallpaper_data: Dict[str, Any]) -> str:
        url = wallpaper_data.get("thumbnail_url", "")
        if url.endswith('.png'):
            return "png"
        return "jpg"
    
    def get_resolution(self, wallpaper_data: Dict[str, Any]) -> str:
        return "3840x2160"

    def get_available_resolutions(self, wallpaper_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        return RESOLUTIONS
    
    def get_filters(self) -> Dict[str, Any]:
        return {
            "warning": {
                "type": "info",
                "label": "Note",
                "text": "4kwallpapers.com returns the same results on all pages, so only 1 page of results is possible. To browse more, use the search box (categories won't work with searches)."
            },
            "categories": {
                "type": "dropdown",
                "label": "Category",
                "options": [{"id": cat["id"], "label": cat["label"], "default": cat["id"] == "anime"} for cat in CATEGORIES]
            },
            "resolution": {
                "type": "dropdown",
                "label": "Resolution",
                "options": [{"id": r["id"], "label": r["label"], "default": r["id"] == "3840x2160"} for r in RESOLUTIONS]
            },
        }