from typing import List, Dict, Any
from core.extension import WallpaperExtension, get_extension_names, create_extension


class AllExtension(WallpaperExtension):
    """Aggregates results from all registered extensions."""

    def __init__(self):
        super().__init__()
        self.name = "All"
        self._source_cache = {}

    def _get_source_ext(self, source: str):
        if source not in self._source_cache:
            self._source_cache[source] = create_extension(source)
        return self._source_cache[source]

    def search(self, query: str, page: int = 1, **kwargs) -> List[Dict[str, Any]]:
        results = []
        selected_sources = kwargs.get("sources", [])
        if isinstance(selected_sources, str) and selected_sources:
            selected_sources = selected_sources.split(",")
        elif not selected_sources:
            selected_sources = []

        selected_set = set(selected_sources) if selected_sources else None

        names = get_extension_names()
        skip = {"All", "All (Experimental)", "Local"}

        for name in names:
            if name in skip:
                continue
            if selected_set and name not in selected_set:
                continue
            try:
                ext = create_extension(name)
                if not ext:
                    continue
                wallpapers = ext.search(query, page, **kwargs)
                for wp in wallpapers:
                    wp = wp.copy()
                    wp["_source"] = name
                    results.append(wp)
            except Exception as e:
                print(f"All: error from {name}: {e}")

        return results

    def get_total_pages(self, query: str, **kwargs) -> int:
        return 999

    def get_thumbnail_url(self, wallpaper_data: Dict[str, Any]) -> str:
        return self._get_source_method(wallpaper_data, "get_thumbnail_url")

    def get_download_url(
        self, wallpaper_data: Dict[str, Any], resolution: str = None
    ) -> str:
        return (
            self._get_source_method(wallpaper_data, "get_download_url", resolution)
            or ""
        )

    def get_download_urls_by_priority(
        self, wallpaper_data: Dict[str, Any]
    ) -> List[str]:
        method = self._get_source_method(
            wallpaper_data, "get_download_urls_by_priority"
        )
        return method(wallpaper_data) if callable(method) else []

    def get_wallpaper_id(self, wallpaper_data: Dict[str, Any]) -> str:
        source = wallpaper_data.get("_source", "")
        return (
            f"{source}_{wallpaper_data.get('id', '')}"
            if source
            else wallpaper_data.get("id", "")
        )

    def get_file_extension(self, wallpaper_data: Dict[str, Any]) -> str:
        return wallpaper_data.get("file_extension", "jpg")

    def get_resolution(self, wallpaper_data: Dict[str, Any]) -> str:
        return self._get_source_method(wallpaper_data, "get_resolution")

    def get_filters(self) -> Dict[str, Any]:
        names = get_extension_names()
        sources = [n for n in names if n not in ("All", "All (Experimental)", "Local")]
        return {
            "sources": {
                "type": "checkboxes",
                "label": "Sources",
                "options": [{"id": s, "label": s, "default": True} for s in sources],
            }
        }

    def get_download_url_for_set(self, wallpaper_data: Dict[str, Any]) -> str:
        result = self._get_source_method(wallpaper_data, "get_download_url_for_set")
        return (
            result or self._get_source_method(wallpaper_data, "get_download_url") or ""
        )

    def _get_source_method(
        self, wallpaper_data: Dict[str, Any], method_name: str, *args
    ):
        source = wallpaper_data.get("_source", "")
        if not source:
            return None
        try:
            ext = self._get_source_ext(source)
            if not ext:
                return None
            if hasattr(ext, method_name):
                method = getattr(ext, method_name)
                if callable(method):
                    return (
                        method(wallpaper_data, *args)
                        if args
                        else method(wallpaper_data)
                    )
        except Exception:
            pass
        return None

