import threading
from typing import List, Dict, Any
from core.extension import WallpaperExtension, register_extension, get_extension_names, create_extension


class AllExtension(WallpaperExtension):
    """Aggregates results from all registered extensions."""
    
    def __init__(self):
        super().__init__()
        self.name = "All"
        self._extensions = []
    
    def search(self, query: str, page: int = 1, **kwargs) -> List[Dict[str, Any]]:
        results = []
        names = get_extension_names()
        
        for name in names:
            if name in ("All", "Local"):
                continue
            try:
                ext = create_extension(name)
                if ext:
                    wallpapers = ext.search(query, page, **kwargs)
                    for wp in wallpapers:
                        wp = wp.copy()
                        wp["_source"] = name
                        results.append(wp)
            except Exception:
                pass
        
        return results
    
    def get_total_pages(self, query: str, **kwargs) -> int:
        return 999
    
    def get_thumbnail_url(self, wallpaper_data: Dict[str, Any]) -> str:
        source = wallpaper_data.get("_source", "")
        if not source:
            return ""
        try:
            ext = create_extension(source)
            if ext:
                return ext.get_thumbnail_url(wallpaper_data)
        except Exception:
            pass
        return ""
    
    def get_download_url(self, wallpaper_data: Dict[str, Any], resolution: str = None) -> str:
        source = wallpaper_data.get("_source", "")
        if not source:
            return ""
        try:
            ext = create_extension(source)
            if ext:
                return ext.get_download_url(wallpaper_data, resolution)
        except Exception:
            pass
        return ""
    
    def get_wallpaper_id(self, wallpaper_data: Dict[str, Any]) -> str:
        source = wallpaper_data.get("_source", "")
        if not source:
            return str(wallpaper_data.get("id", ""))
        try:
            ext = create_extension(source)
            if ext:
                return f"{source}_{ext.get_wallpaper_id(wallpaper_data)}"
        except Exception:
            pass
        return str(wallpaper_data.get("id", ""))
    
    def get_file_extension(self, wallpaper_data: Dict[str, Any]) -> str:
        return wallpaper_data.get("file_extension", "jpg")
    
    def get_resolution(self, wallpaper_data: Dict[str, Any]) -> str:
        source = wallpaper_data.get("_source", "")
        if not source:
            return "?"
        try:
            ext = create_extension(source)
            if ext:
                return ext.get_resolution(wallpaper_data)
        except Exception:
            pass
        return "?"
    
    def get_filters(self) -> Dict[str, Any]:
        return {}
