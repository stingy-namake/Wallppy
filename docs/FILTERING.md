# Wallppy Extensions & Filters System

## Overview

Two parts: extensions (data sources) + filters (UI controls for search params).

```
┌─────────────────────────────────────────────────────────────────────┐
│                      UI                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐   │
│  │ search box │───>│ get_filters│───>│ filter    │   │
│  │           │    │ returns   │    │ widgets   │   │
│  └─────────────┘    │ dict     │    │ built    │   │
│                    └─────────────┘    └─────────────┘   │
│                         │                 │            │
│                         v                 v            │
│                    ┌─────────────────────────┐           │
│                    │ Apply = kwargs sent  │           │
│                    │ to search()        │           │
│                    └─────────────────────────┘           │
└─────────────────────────────────────────────────────┘
                           │
                           v
┌─────────────────────────────────────────────────────┐
│                 EXTENSION                           │
│  ┌─────────────────────────────────────────────┐  │
│  │ search(query, page, **kwargs) -> []         │  │
│  │ get_total_pages(query) -> int              │  │
│  │ get_filters() -> {}                       │  │
│  └─────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

## Part 1: Extension System

### Base Class

Location: `core/extension.py` - `WallpaperExtension` ABC.

Every extension inherits from this. Must implement:

```python
class WallpaperExtension(ABC):
    def search(self, query: str, page: int = 1, **kwargs) -> List[Dict[str, Any]]:
        """Return list of wallpaper dicts. Each dict needs at least:
        - 'id': unique identifier (str)
        - 'slug': url-friendly name (str)
        - 'title': display name (str)
        - 'page_url': link to wallpaper page (str)
        - 'thumbnail_url': image preview URL (str)
        """
        pass
    
    def get_total_pages(self, query: str, **kwargs) -> int:
        """Total pages available. Infinite if unknown."""
        pass
    
    def get_thumbnail_url(self, wallpaper_data: Dict) -> str:
        pass
    
    def get_download_url(self, wallpaper_data: Dict, resolution: str = None) -> str:
        pass
    
    def get_wallpaper_id(self, wallpaper_data: Dict) -> str:
        pass
    
    def get_file_extension(self, wallpaper_data: Dict) -> str:
        pass
    
    def get_resolution(self, wallpaper_data: Dict) -> str:
        pass
    
    def get_filters(self) -> Dict[str, Any]:
        """Filter UI definition - see Part 2."""
        return {}
```

### Registry

Extensions register themselves at startup:

```python
# extensions/__init__.py
from core.extension import register_extension
from .fourkwallpapers import FourKWallpapersExtension
from .wallhaven import WallHavenExtension

register_extension("4KWallpapers", FourKWallpapersExtension)
register_extension("WallHaven", WallHavenExtension)
```

Creating extension by name:

```python
from core.extension import create_extension

ext = create_extension("4KWallpapers")  # returns instance
```

### Search Flow

```
UI.search_button -> results_page._start_search_worker()
    -> SearchWorker(page=1).start()
    -> SearchWorker._do_run():
        wallpapers = ext.search(query, page=1, **kwargs)
        total_pages = ext.get_total_pages(query, **kwargs)
        emit(wallpapers, page, total_pages)
    -> results_page.on_search_finished(wallpapers, page, total_pages)
    -> results_page.rebuild_grid()
```

### Pagination Flow

```
User scrolls -> load_next_page() called
    if current_page < total_pages:
        start SearchWorker(page + 1)
        on_search_finished extends wallpapers list
```

**Key point:** UI uses `total_pages` to decide if more pages exist. If `get_total_pages()` returns 999 -> infinite scroll possible.

### Pagination Bug Pattern

Site returns same results on every page. Detection requires tracking unique IDs:

```python
def search(self, query, page, **kwargs):
    # Reset on new search
    if page == 1 or query != self._last_query:
        self._seen_ids = set()
    
    results = self._fetch_results(query, page)
    
    # Find new IDs not seen before
    new_ids = {w['id'] for w in results if w['id'] not in self._seen_ids}
    
    # Duplicate page = exhausted
    if page > 1 and not new_ids:
        return []  # Stop pagination
    
    self._seen_ids.update(new_ids)
    return results
```

## Part 2: Filter System

### Filter Definition Format

Extension implements `get_filters()` returning dict:

```python
def get_filters(self) -> Dict[str, Any]:
    return {
        "filter_id": {
            "type": "checkboxes" | "dropdown" | "info",
            "label": "Display Name",
            "options": [
                {"id": "opt_id", "label": "Option Label", "default": True/False},
            ],
            # "info" type uses "text" instead of "options":
            "text": "Warning/help text here",
        },
    }
```

### Filter Types

#### checkboxes

Multi-select. Returns binary string:

```
options: [
    {"id": "cat1", "label": "Category 1", "default": True},
    {"id": "cat2", "label": "Category 2", "default": False},
]
UI returns: "10" (cat1 on, cat2 off)
```

Widget key format: `"categories.cat1"`

#### dropdown

Single select. Returns selected option ID:

```
options: [
    {"id": "anime", "label": "Anime", "default": True},
    {"id": "nature", "label": "Nature", "default": False},
]
UI returns: "anime" (selected ID)
```

Widget key: `"categories"` (direct, no suffix)

#### info

Read-only text display. For warnings, help text.

```python
"warning": {
    "type": "info",
    "label": "Note",
    "text": "Important information here",
}
```

### UI Filter Building

Location: `ui/results_page.py` - `FilterPanel` class.

```python
# Line ~107: Build filter widgets
filters = ext.get_filters()

for filter_id, filter_def in filters.items():
    filter_type = filter_def.get("type")
    label = filter_def.get("label", filter_id)
    options = filter_def.get("options", [])
    
    if filter_type == "checkboxes":
        # Build checkbox group
        for opt in options:
            cb = QCheckBox(opt["label"])
            self.widgets[f"{filter_id}.{opt['id']}"] = cb
    
    elif filter_type == "dropdown":
        combo = QComboBox()
        for opt in options:
            combo.addItem(opt["label"], opt["id"])
        self.widgets[filter_id] = combo
    
    elif filter_type == "info":
        info_label = QLabel(filter_def.get("text", ""))
```

### Filter Value Extraction

When user clicks Apply:

```python
def get_filter_values(self) -> dict:
    filters = self.extension.get_filters()
    values = {}
    
    for filter_id, filter_def in filters.items():
        filter_type = filter_def.get("type")
        
        if filter_type == "checkboxes":
            val = ""
            for opt in filter_def["options"]:
                cb = self.widgets.get(f"{filter_id}.{opt['id']}")
                val += "1" if (cb and cb.isChecked()) else "0"
            values[filter_id] = val
        
        elif filter_type == "dropdown":
            combo = self.widgets.get(filter_id)
            values[filter_id] = combo.currentData() if combo else ""
        
        # "info" type: no value
    
    return values
```

### Filter Flow to Search

```
Apply button clicked
    -> emit apply_clicked(values)
    -> SearchWorker extension.search(query, page, **values)
    -> kwargs passed as **kwargs
```

Extension reads kwargs:

```python
def search(self, query: str, page: int = 1, **kwargs):
    category = kwargs.get('categories', '')  # from dropdown
    cat_flags = kwargs.get('purity', '111')  # from checkboxes
    
    # Use in API calls, URL building, etc.
```

## Part 3: Debugging

### Filter Not Showing

Check:
1. Extension has `get_filters()` returning non-empty dict
2. Filter type in ("checkboxes", "dropdown", "info")
3. "options" present for checkboxes/dropdown
4. "text" present for info

Debug:
```python
from core.extension import create_extension
ext = create_extension("4KWallpapers")
print(ext.get_filters())
```

### Filter Not Applied

Check:
1. Add print in `get_filter_values()`: confirm values change on Apply
2. Check SearchWorker receives kwargs: add print in extension.search()
3. Check `apply_clicked` signal connects properly

### Infinite Scroll / Repeating Results

Site returns same data on every page. Fix:
1. Track unique IDs in instance variables
2. Return empty when no new IDs found
3. Set `_total_pages` to stop UI

Debug:
```python
# In extension.search():
print(f"Page {page}: {len(results)} results")
print(f"New IDs: {new_ids}")

# Check page 1 vs page 2 response content
import requests
r1 = requests.get(url + "?page=1")
r2 = requests.get(url + "?page=2")
print(r1.text == r2.text)  # True = bug
```

### Extension Not Loading

Check:
1. In `extensions/__init__.py`: register_extension called?
2. In `core/extension.py`: name matches create_extension call?
3. Import works: `python -c "from extensions.fourkwallpapers import FourKWallpapersExtension"`

## Part 4: Adding New Filter Type

Two files to modify:

1. **Extension** (`extensions/xxx.py`):
```python
def get_filters(self) -> Dict[str, Any]:
    return {
        "myfilter": {
            "type": "newtype",
            "label": "My Filter",
            # ... type-specific fields
        },
    }
```

2. **UI** (`ui/results_page.py`):
In `FilterPanel.__init__()`, add handler:

```python
elif filter_type == "newtype":
    # Build widget based on filter_def
    # Store in self.widgets with key = filter_id
```

In `get_filter_values()`, add extraction:

```python
elif filter_type == "newtype":
    values[filter_id] = # extract value from widget
```

## Quick Reference

| File | Purpose |
|------|--------|
| `core/extension.py` | Base class ABC |
| `extensions/__init__.py` | Registry + imports |
| `extensions/*.py` | Concrete implementations |
| `ui/results_page.py` | FilterPanel class |
| `core/workers.py` | SearchWorker runs search |

### Common Patterns

**Dropdown filter (single select):**
```python
"categories": {
    "type": "dropdown",
    "label": "Category",
    "options": [{"id": "anime", "label": "Anime", "default": True}]
}
```

**Checkbox filter (multi select):**
```python
"purity": {
    "type": "checkboxes", 
    "label": "Content",
    "options": [
        {"id": "sfw", "label": "SFW", "default": True},
        {"id": "nsfw", "label": "NSFW", "default": False}
    ]
}
```

**Info/helper text:**
```python
"warning": {
    "type": "info",
    "label": "Note",
    "text": "Important info here"
}
```