# Wallppy Technical Documentation

This document provides comprehensive technical documentation for Wallppy, enabling a developer to understand, modify, and extend the codebase.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Application Lifecycle](#application-lifecycle)
3. [Core Modules](#core-modules)
4. [UI System](#ui-system)
5. [Extension System](#extension-system)
6. [Background Workers](#background-workers)
7. [Configuration & Persistence](#configuration--persistence)
8. [Platform-Specific Handling](#platform-specific-handling)
9. [Extending Wallppy](#extending-wallppy)
10. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

### Project Structure

```
Wallppy/
├── main.py                    # Entry point, environment setup
├── core/
│   ├── extension.py         # Abstract base class for sources
│   ├── wallpaper_manager.py # Cross-platform wallpaper setting
│   ├── settings.py          # Persistent configuration
│   ├── crash_handler.py     # Global exception handling
│   └── workers.py          # Background threads
├── ui/
│   ├── main_window.py       # Main application window
│   ├── landing_page.py    # Search/explore interface
│   ├── results_page.py    # Gallery view with filtering
│   └── wallpaper_widget.py # Thumbnail card component
├── extensions/
│   ├── __init__.py        # Extension registry
│   ├── wallhaven.py      # Wallhaven.cc API
│   ├── local.py         # Local folder browsing
│   ├── all_sources.py   # Multi-source aggregation
│   ├── fourkwallpapers.py # 4kwallpapers.com scraper
│   └── backiee.py      # backiee.com scraper
└── docs/
    └── (this file)
```

### Design Principles

1. **Plugin Architecture**: Each wallpaper source is an independent extension registered via `WallpaperExtension` base class
2. **Thread Safety**: All network/distinct operations run in background QThread workers to keep UI responsive
3. **Cross-Platform**: WallpaperManager tries multiple desktop environments in order of likelihood
4. **Graceful Degradation**: Fallback mechanisms for network failures, missing APIs, platform incompatibilities

---

## Application Lifecycle

### Startup Sequence (main.py)

```
1. is_gnome_wayland()     # Detect GNOME on Wayland
2. debug_ssl()              # Write SSL debug info (optional)
3. PyInstaller fixes      # System certs, OPENSSL_FIPS
4. Qt platform fix      # QT_QPA_PLATFORM=xcb on GNOME Wayland
5. Import Qt           # After platform variable set
6. CrashHandler.install() # Install before QApplication
7. QApplication()    # Create Qt app
8. Settings.load()    # Load config
9. MainWindow.show() # Create and show window
10. app.exec_()       # Event loop
```

### Why GNOME Wayland Needs XCB (lines 72-77 in main.py)

GNOME on Wayland has known issues with Qt's Wayland platform plugin:
- Qt's Wayland integration with GNOME's compositor (mutter) causes crashes
- X11 fallback via xcb works reliably

Detection uses multiple methods:
1. `XDG_SESSION_TYPE=wayland` + `XDG_CURRENT_DESKTOP=GNOME`
2. `loginctl show-session self -p Type`
3. `WAYLAND_DISPLAY` + `DESKTOP_SESSION` containing "gnome"

### SSL Certificate Handling (lines 61-69 in main.py)

PyInstaller bundles stale CA certificates. At runtime:
- Check if frozen (PyInstaller) mode
- Override `REQUESTS_CA_BUNDLE` and `SSL_CERT_FILE` to system certs
- Set `OPENSSL_FIPS=1` for correct TLS fingerprinting

This prevents SSL certificate validation errors on older systems.

---

## Core Modules

### WallpaperExtension (core/extension.py)

Abstract base class defining the wallpaper source interface. All extensions must implement:

```python
class WallpaperExtension(ABC):
    @abstractmethod
    def search(self, query: str, page: int = 1, **kwargs) -> List[Dict[str, Any]]:
        """Execute search query, return wallpaper data list."""
        pass

    @abstractmethod
    def get_total_pages(self, query: str, **kwargs) -> int:
        """Return total available pages."""
        pass

    # Accessor methods
    def get_thumbnail_url(self, wallpaper_data) -> str: ...
    def get_download_url(self, wallpaper_data) -> str: ...
    def get_wallpaper_id(self, wallpaper_data) -> str: ...
    def get_file_extension(self, wallpaper_data) -> str: ...
    def get_resolution(self, wallpaper_data) -> str: ...

    # Optional filters
    def get_filters(self) -> Dict[str, Any]:
        """Return filter definitions for UI."""
        return {}
```

### Registry Pattern (core/extension.py:79-91)

Extensions register themselves at import time:

```python
_EXTENSION_REGISTRY: Dict[str, Type[WallpaperExtension]] = {}

def register_extension(name: str, cls: Type[WallpaperExtension]):
    _EXTENSION_REGISTRY[name] = cls

def create_extension(name: str, **kwargs) -> Optional[WallpaperExtension]:
    cls = _EXTENSION_REGISTRY.get(name)
    return cls(**kwargs) if cls else None
```

Registration happens in `extensions/__init__.py` when imported from `main.py` line 85:
```python
import extensions  # registers extensions
```

### WallpaperManager (core/wallpaper_manager.py)

Cross-platform wallpaper setter with multiple fallback methods:

```
set_wallpaper(image_path)
    ├── Windows: ctypes.SystemParametersInfoW
    ├── macOS: osascript
    └── Linux: (tried in order)
        ├── COSMIC (System76) - write RON config
        ├── GNOME (dconf/gsettings/keyfile/gconftool-2)
        ├── KDE Plasma: plasma-apply-wallpaperimage
        ├── Sway: swaymsg
        ├── Hyprland: hyprctl hyprpaper
        ├── feh (X11 fallback)
        └── nitrogen (X11 fallback)
```

#### Why Multiple GNOME Methods (lines 113-218)

GNOME has changed wallpaper APIs over versions:
1. **dconf write**: Modern g Settings dconf backend
2. **gsettings with keyfile**: Works when dconf unavailable
3. **dbus-launch + gsettings**: Session bus fallback
4. **gconftool-2**: Older GNOME 2.x/3.x
5. **xfconf-query**: XFCE compatibility

The `_clean_env()` method (lines 44-52) removes `LD_LIBRARY_PATH` which PyInstaller pollutes with its temp directory—causing system libraries for gsettings/dconf.

#### COSMIC Desktop (lines 226-260)

System76's COSMIC desktop uses RON configuration:
- Config path: `~/.config/cosmic/com.system76.CosmicBackground/v1/all`
- Daemon watches with inotify, auto-reloads on change

Must check COSMIC before GNOME because COSMIC ignores GNOME variables.

#### Windows Caching (lines 23-31)

Windows locks wallpaper files. Manager caches to `~/.cache/wallppy/` to avoid locks:
```python
def get_cached_path(cls, source_path):
    stat = os.stat(source_path)
    cache_key = hashlib.md5(f"{source_path}:{stat.st_mtime}").hexdigest()
    return cls._cache_dir / f"{cache_key}.jpg"
```

### Settings (core/settings.py)

JSON-based persistent configuration:

```python
class Settings:
    config_path = ~/.config/wallppy/settings.json
    
    # Default values
    download_folder = "./wallpapers"
    categories = {"general": True, "anime": True, "people": True}
    purity = {"sfw": True, "sketchy": False}
    extension_name = "Wallhaven"
```

Saved on any change via `save()` method.

### CrashHandler (core/crash_handler.py)

Global exception catcher that logs to `~/.config/wallppy/crash.log`:

```python
class CrashHandler:
    def install(self):
        sys.excepthook = self._handle_exception      # Uncaught exceptions
        sys.unraisablehook = self._handle_unraisable  # __del__ failures
        threading.excepthook = self._handle_thread_exception
        qInstallMessageHandler(self._qt_message_handler)  # Qt warnings
```

Shows crash dialog on next startup if previous session crashed:
- Checks for `.clean_shutdown` marker
- Clears log after 5 consecutive clean sessions

---

## UI System

### MainWindow (ui/main_window.py)

Main application frame with dark theme:

```python
class MainWindow(QMainWindow):
    # Color palette - Modern Dark with Neon Accents
    COLOR_BG_PRIMARY = "#050508"
    COLOR_ACCENT_PRIMARY = "#00d4ff"
    COLOR_ACCENT_SECONDARY = "#7b61ff"
```

#### Navigation (FadeStackedWidget)

Custom QStackedWidget with cross-fade animation between pages:
```python
class FadeStackedWidget(QStackedWidget):
    def setCurrentIndex(self, index):
        # Fade current widget out (0.2s)
        # Switch
        # Fade next widget in (0.25s)
```

### LandingPage (ui/landing_page.py)

Entry point with:
- Logo with drop shadow
- Source selector dropdown
- Search input with animated button
- Download folder selector
- "explore content" link

Uses `AnimatedButton`, `AnimatedComboBox` with hover scale effect (QGraphicsEffect).

### ResultsPage (ui/results_page.py)

Gallery view with:
- Search bar with filtering toggle
- AnimatedFilterPanel (collapsible)
- Grid layout (auto-calculated columns)
- Infinite scroll pagination
- Scroll-to-top button
- Download queue management
- Image overlay for full preview

#### Filter System

Filters defined per-extension in `get_filters()`:
```python
{
    "filter_id": {
        "type": "checkboxes|dropdown|info",
        "label": "Display Label",
        "options": [
            {"id": "opt_id", "label": "Display", "default": False}
        ]
    }
}
```

Panel builds UI from these definitions, emits `apply_clicked` with compiled values.

#### Image Overlay

Full-resolution preview with:
- Loading spinner during fetch
- Cancel on ESC
- Scale to fit window, maintain aspect ratio
- Click anywhere to close

### WallpaperWidget (ui/wallpaper_widget.py)

Individual thumbnail card:

```
┌─────────────────────────────┐
│  ┌─────────────────────┐  │
│  │    Thumbnail      │  │
│  │   (Shimmer)     │  │
│  └─────────────────────┘  │
│ ★ ✓ 1920x1080  [⤢][🖵][✕] │
└─────────────────────────────┘
```

Features:
- **ShimmerLabel**: Animated loading placeholder while thumbnail loads
- **HoverScaleEffect**: Zoom + glow on hover
- **AnimatedToolButton**: Buttons with press feedback
- **Indicator buttons**:
  - ★ (star): Currently active wallpaper
  - ✓ (checkmark): Downloaded
  - ⤢ (expand): Preview full image
  - 🖵 (monitor): Set as wallpaper
  - ✕ (trash): Delete downloaded file

---

## Extension System

### WallhavenExtension (extensions/wallhaven.py)

API v1 from wallhaven.cc:

```python
api_url = "https://wallhaven.cc/api/v1/search"
params = {
    "q": query,
    "categories": "111",   # general/anime/people
    "purity": "100",      # sfw/sketchy/nsfw
    "page": page,
    "per_page": 24,
    "sorting": "date_added",
}
```

- Returns 24 results per page
- Uses categories/purity filters mapped to 3-character strings
- Session with connection pooling and retries

### LocalExtension (extensions/local.py)

Browse local wallpapers:

```
search(query, page, download_folder, sort_by)
    │
    ├─ Get all image files (*.jpg, *.png, *.gif, *.bmp, *.webp)
    ├─ Filter by query (filename contains)
    ├─ Sort by: modified/name/size/resolution
    └─ Return paginated results
```

Uses metadata caching:
- Stores in `~/.cache/wallppy/local_metadata.json`
- Pre-computes resolutions in background thread
- 5-minute TTL before rescanning folder

### AllExtension (extensions/all_sources.py)

Aggregates multiple sources:

```
search(query, page, sources, **filters)
    │
    ├─ For each enabled source:
    │   └─ Create extension, search, tag with source
    └─ Return merged results
```

Creates dynamic filters combining all source filters.

### FourKWallpapersExtension (extensions/fourkwallpapers.py)

Web scraper for 4kwallpapers.com:

- Parses HTML with BeautifulSoup
- Builds thumbnail/download URLs from page data
- Deduplicates across pages using ID tracking

### BackieeExtension (extensions/backiee.py)

Scraper for backiee.com:

- Uses curl fallback when requests blocked by Cloudflare
- Builds direct image URLs from ID patterns

---

## Background Workers

### Thread Architecture (core/workers.py)

All workers inherit from `CrashAwareThread` which logs exceptions before raising:

```python
class CrashAwareThread(QThread):
    def run(self):
        try:
            self._do_run()
        except Exception:
            logger.critical(f"Worker crashed:\n{traceback.format_exc()}")
            raise

    def _do_run(self):
        """Override instead of run()."""
```

### SearchWorker

```python
class SearchWorker(CrashAwareThread):
    finished = pyqtSignal(list, int, int)  # results, page, total
    error = pyqtSignal(str)

    def _do_run(self):
        wallpapers = extension.search(query, page, **kwargs)
        total_pages = extension.get_total_pages(query, **kwargs)
        self.finished.emit(wallpapers, page, total_pages)
```

### DownloadWorker

```python
class DownloadWorker(CrashAwareThread):
    finished = pyqtSignal(bool, str, str, str)  # success, path, filename, id
    progress = pyqtSignal(int)

    def _do_run(self):
        # 1. Use URL from extension (with fallback URLs)
        # 2. Download with requests (stream, chunked)
        # 3. Fallback to curl if blocked
        # 4. Emit progress, save to download_folder
```

### ThumbnailLoader

```python
class ThumbnailLoader(CrashAwareThread):
    loaded = pyqtSignal(QPixmap)
    _cache = {}           # Shared in-memory cache
    _lock = Lock()       # Thread-safe access
    _semaphore = Semaphore(8)  # Limit concurrent loads

    def _do_run(self):
        # 1. Check cache with lock
        # 2. If local file: QImageReader
        # 3. Else: requests (semaphore limited)
        # 4. Fallback to curl for blocked URLs
        # 5. Scale to 256x256, cache, emit
```

### get_session() (core/workers.py:16-29)

Thread-local requests session with:
- Connection pooling (5 connections, 10 max)
- Retry strategy (2 retries, backoff for 429/5xx)
- User-Agent and Accept headers

---

## Configuration & Persistence

### Settings File

`~/.config/wallppy/settings.json`:

```json
{
  "download_folder": "/home/user/wallpapers",
  "extension": "Wallhaven",
  "categories": {"general": true, "anime": true, "people": true},
  "purity": {"sfw": true, "sketchy": false}
}
```

### Cache Files

| File | Purpose |
|------|---------|
| `~/.cache/wallppy/*.jpg` | Windows wallpaper cache |
| `~/.cache/wallppy/local_metadata.json` | Local extension resolutions |
| `~/.config/wallppy/crash.log` | Crash/exception log |
| `~/.config/wallppy/.clean_shutdown` | Startup marker |

### Log Rotation

CrashHandler clears log after 5 consecutive clean sessions (lines 133-138 in crash_handler.py):

```python
if new_count >= 5:
    self._clear_log()
    new_count = 0
```

---

## Platform-Specific Handling

### Linux Desktop Detection

Multiple approaches tried in order:

1. **Environment variables**: `XDG_CURRENT_DESKTOP`
2. **COSMIC check**: Pop!_OS specific
3. **Command fallbacks**: dconf, gsettings, plasma-apply, swaymsg, hyprctl

### Wayland Compatibility

GNOME Wayland → XCB override in `main.py`:

```python
os.environ['QT_QPA_PLATFORM'] = 'xcb'
os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '0'
os.environ['QT_SCALE_FACTOR'] = '1'
```

### PyInstaller Issues (wallpaper_manager.py:44-52)

`_clean_env()` removes `LD_LIBRARY_PATH` because PyInstaller sets it to its temp directory, causing system binaries (gsettings, dconf) to load incompatible bundled libraries.

---

## Extending Wallppy

### Creating New Extension

1. Create `extensions/mysource.py`:

```python
from core.extension import WallpaperExtension

class MySourceExtension(WallpaperExtension):
    def __init__(self):
        super().__init__()
        self.name = "MySource"

    def search(self, query: str, page: int = 1, **kwargs) -> List[Dict]:
        # Implement search
        return results

    def get_total_pages(self, query: str, **kwargs) -> int:
        return total

    def get_thumbnail_url(self, data) -> str: ...
    def get_download_url(self, data) -> str: ...
    def get_wallpaper_id(self, data) -> str: ...
    def get_file_extension(self, data) -> str: ...
    def get_resolution(self, data) -> str: ...

    def get_filters(self) -> Dict:
        return {
            "myfilter": {
                "type": "checkboxes",
                "label": "My Filter",
                "options": [
                    {"id": "opt1", "label": "Option 1", "default": True}
                ]
            }
        }
```

2. Register in `extensions/__init__.py`:

```python
from .mysource import MySourceExtension
register_extension("MySource", MySourceExtension)
```

### Filter Format

UI builds filter controls from definitions:

```python
{
    "filter_id": {
        "type": "checkboxes|dropdown|info",
        "label": "Display Label",
        "options": [
            {"id": "...", "label": "...", "default": bool},
        ]
    }
}
```

**checkboxes**: Multiple selection, returns:
- Categories: string like "101" (checked=1, unchecked=0)
- Ratio: comma-separated IDs
- Other: list of checked IDs

**dropdown**: Single selection, returns selected ID

**info**: Display-only text for notes/warnings

---

## Troubleshooting

### Common Issues

| Symptom | Cause | Solution |
|--------|-------|----------|
| App crashes on startup | GNOME Wayland Qt issue | Set `QT_QPA_PLATFORM=xcb` |
| SSL errors | PyInstaller stale certs | Use system certs (main.py:61-69) |
| Wallpaper doesn't change | Unsupported DE | Install feh/nitrogen |
| Network errors | Cloudflare blocking | Curl fallback in workers |
| Slow thumbnail loading | Too many concurrent | ThumbnailLoader semaphore=8 |

### Debug Log Locations

- Crash log: `~/.config/wallppy/crash.log`
- SSL debug: `~/.config/wallppy/debug.log`
- Windows cache: `~/.cache/wallppy/`
- Local metadata: `~/.cache/wallppy/local_metadata.json`

### Logging In

Enable crash logging in code:

```python
import logging
logging.getLogger("wallppy.crash").setLevel(logging.DEBUG)
```

---

## Key Files Reference

| File | Purpose | Key Classes/Functions |
|------|---------|---------------------|
| main.py | Entry point | `main()`, `is_gnome_wayland()`, `debug_ssl()` |
| core/extension.py | Base abstraction | `WallpaperExtension`, registry functions |
| core/wallpaper_manager.py | Set wallpaper | `WallpaperManager`, `WallpaperSetterWorker` |
| core/settings.py | Config persistence | `Settings` |
| core/crash_handler.py | Error catching | `CrashHandler` |
| core/workers.py | Background tasks | `SearchWorker`, `DownloadWorker`, `ThumbnailLoader` |
| ui/main_window.py | Main frame | `MainWindow`, `FadeStackedWidget` |
| ui/landing_page.py | Home page | `LandingPage` |
| ui/results_page.py | Gallery | `ResultsPage`, `AnimatedFilterPanel`, `ImageOverlay` |
| ui/wallpaper_widget.py | Card component | `WallpaperWidget`, `HoverScaleEffect` |
| extensions/wallhaven.py | Wallhaven API | `WallhavenExtension` |
| extensions/local.py | Local folder | `LocalExtension` |
| extensions/all_sources.py | Multi-source | `AllExtension` |