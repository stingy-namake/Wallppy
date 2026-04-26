from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Type


class WallpaperExtension(ABC):
    """Abstract base class for wallpaper sources."""
    
    def __init__(self):
        self.name = "Base Extension"
    
    @abstractmethod
    def search(self, query: str, page: int = 1, **kwargs) -> List[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def get_total_pages(self, query: str, **kwargs) -> int:
        pass
    
    @abstractmethod
    def get_thumbnail_url(self, wallpaper_data: Dict[str, Any]) -> str:
        pass
    
    @abstractmethod
    def get_download_url(self, wallpaper_data: Dict[str, Any]) -> str:
        pass
    
    @abstractmethod
    def get_wallpaper_id(self, wallpaper_data: Dict[str, Any]) -> str:
        pass
    
    @abstractmethod
    def get_file_extension(self, wallpaper_data: Dict[str, Any]) -> str:
        pass
    
    @abstractmethod
    def get_resolution(self, wallpaper_data: Dict[str, Any]) -> str:
        pass

    def get_available_resolutions(self, wallpaper_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []

    def get_download_urls_by_priority(self, wallpaper_data: Dict[str, Any]) -> List[str]:
        url = self.get_download_url(wallpaper_data)
        return [url] if url else []

    def get_filters(self) -> Dict[str, Any]:
        """
        Return a dictionary describing available filters for this extension.
        The UI will build filter widgets based on this description.
        
        Example return format:
        {
            "categories": {
                "type": "checkboxes",
                "label": "Categories",
                "options": [
                    {"id": "general", "label": "General", "default": True},
                    {"id": "anime", "label": "Anime", "default": True},
                    {"id": "people", "label": "People", "default": True}
                ]
            },
            "purity": {
                "type": "checkboxes",
                "label": "Content",
                "options": [
                    {"id": "sfw", "label": "SFW", "default": True},
                    {"id": "sketchy", "label": "Sketchy", "default": False},
                    {"id": "nsfw", "label": "NSFW", "default": False, "requires_auth": True}
                ]
            }
        }
        
        Returns empty dict if no filters are available.
        """
        return {}


# Registry
_EXTENSION_REGISTRY: Dict[str, Type[WallpaperExtension]] = {}

def register_extension(name: str, cls: Type[WallpaperExtension]):
    _EXTENSION_REGISTRY[name] = cls

def get_extension_names() -> List[str]:
    return list(_EXTENSION_REGISTRY.keys())

def create_extension(name: str, **kwargs) -> Optional[WallpaperExtension]:
    cls = _EXTENSION_REGISTRY.get(name)
    if cls:
        return cls(**kwargs)
    return None