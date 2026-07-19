# Wallppy - Project Knowledge

## Overview
Wallppy is a cross-platform wallpaper manager built with Python/PyQt5. Currently Linux-focused with plans for Windows/macOS support. Aggregates wallpapers from multiple online sources (Wallhaven, 4KWallpapers, Backiee) and local files.

## Architecture

```
Wallppy/
├── main.py              # Entry point, Wayland detection, SSL setup
├── core/
│   ├── extension.py     # WallpaperExtension ABC + registry
│   ├── settings.py      # Persistent settings (~/.config/wallppy/settings.json)
│   ├── workers.py       # QThread workers (search, download, thumbnail)
│   ├── wallpaper_manager.py  # Cross-platform wallpaper setter
│   └── crash_handler.py # Crash logging and recovery
├── extensions/
│   ├── __init__.py      # Extension registration (WARNING: register once only)
│   ├── wallhaven.py     # Wallhaven.cc API
│   ├── local.py         # Local folder browsing
│   ├── fourkwallpapers.py
│   ├── backiee.py
│   └── all_sources.py   # Experimental multi-source
├── ui/
│   ├── main_window.py   # Main window with dark theme
│   ├── landing_page.py  # Search/explore interface
│   ├── results_page.py  # Gallery view with filters
│   └── wallpaper_widget.py  # Thumbnail card with hover effects
└── requirements.txt     # Python dependencies
```

## Key Patterns

### Extension System
- Subclass `WallpaperExtension` ABC from `core/extension.py`
- Implement: `search()`, `get_total_pages()`, `get_thumbnail_url()`, `get_download_url()`, `get_wallpaper_id()`, `get_file_extension()`, `get_resolution()`
- Optional: `get_filters()`, `get_download_urls_by_priority()`, `shutdown()`
- Register in `extensions/__init__.py` using `register_extension("Name", ExtensionClass)`
- **CRITICAL**: Never register an extension more than once - it will crash

### Settings
- Stored at `~/.config/wallppy/settings.json`
- Keys: `download_folder`, `extension`, `categories`, `purity`
- Default download folder: `./wallpapers`

### Thumbnail Cache
- In-memory cache: `ThumbnailLoader._cache` dict
- Persistent metadata: `~/.cache/wallppy/local_metadata.json`

## Theme Colors
```python
COLOR_BG_PRIMARY = "#050508"      # Deep charcoal
COLOR_BG_SECONDARY = "#0a0a0c"
COLOR_BG_TERTIARY = "#1e1e24"
COLOR_ACCENT_PRIMARY = "#00d4ff"  # Neon cyan
COLOR_ACCENT_SECONDARY = "#7b61ff" # Lavender
COLOR_TEXT_PRIMARY = "#ffffff"
COLOR_TEXT_SECONDARY = "#a0a0b0"
COLOR_TEXT_MUTED = "#6a6a7a"
COLOR_BORDER = "#2a2a35"
```

## Commands
```bash
# Run the app
python main.py

# Install dependencies
pip install -r requirements.txt

# Run with debug
python main.py --debug

# Wayland workaround
QT_QPA_PLATFORM=wayland python main.py
```

## Commit Convention
Conventional Commits format based on git history:
```
<type>: <description>

Types: feat, fix
- feat: new feature or enhancement
- fix: bug fix or correction

Rules:
- Lowercase after colon
- No scope (rarely used)
- No body (most commits are subject-only)
- Imperative mood: "add", "fix", "update" not "added", "fixes"
- Short, direct descriptions

Examples:
  feat: add subtle glow to text in main screen
  fix: curl fallback for downloads and thumbnails
  feat: rework all extensions; add "all_sources" as a source
  fix: Wallppy taking too long to load wallpapers
```

## Code Conventions
- No comments unless requested
- PyQt5 signal/slot pattern for communication
- Worker threads for network/IO operations (SearchWorker, DownloadWorker, ThumbnailLoader)
- Thread safety via `threading.local()` for sessions, locks for caches
- SVG icons inline as bytes (b"""<svg...""")
- Animated hover effects via custom `HoverScaleEffect` QGraphicsEffect

## Dependencies
- PyQt5 (GUI), requests (HTTP), Pillow (images), numpy/opencv (image processing)
- PyInstaller (packaging), beautifulsoup4 (parsing)
