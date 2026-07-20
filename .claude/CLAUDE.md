# Wallppy - Project Knowledge

## Overview
Wallppy is a Linux/macOS wallpaper manager built with Python/PyQt5. Aggregates wallpapers from multiple online sources (Wallhaven, 4KWallpapers, Backiee) and local files. Linux support includes GNOME, COSMIC, Niri+Noctalia, KDE, Sway, Hyprland, and X11 fallbacks (feh, nitrogen).

## Architecture

```
Wallppy/
├── main.py              # Entry point, Wayland detection, SSL setup
├── core/
│   ├── extension.py     # WallpaperExtension ABC + registry
│   ├── settings.py      # Persistent settings (~/.config/wallppy/settings.json)
│   ├── workers.py       # QThread workers (search, download, thumbnail) + curl_fetch()
│   ├── wallpaper_manager.py  # Linux/macOS wallpaper setter (detect DE → set)
│   └── crash_handler.py # Crash logging and recovery
├── extensions/
│   ├── __init__.py      # Extension registration (WARNING: register once only)
│   ├── wallhaven.py     # Wallhaven.cc API (WallhavenAPI client + extension)
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
- In-memory LRU cache: `ThumbnailLoader._cache` (OrderedDict, max 200 entries)
- Lazy loading: thumbnails only fetched when widget visible in viewport
- API disk cache: `~/.cache/wallppy/api/` (10min TTL, per query hash)

## Networking
- All HTTP via curl (subprocess) — requests/urllib3 broken on some machines (IPv6/TLS)
- `curl_fetch()` in workers.py for thumbnails
- `WallhavenAPI.search()` uses curl for API calls
- `DownloadWorker` uses `curl -o` for downloads
- `FullImageLoader` uses curl for preview images
- `WallpaperSetterWorker` uses curl for wallpaper download

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
- Keyboard nav: `Qt.ApplicationShortcut` + `QShortcut`/`QAction` for global shortcuts
- Qt5 key constants are UPPERCASE: `Qt.Key_K` not `Qt.Key_k`
- `QApplication.focusWidget()` for detecting focused widget in event filters
- `WallpaperWidget` children (buttons, labels) all set to `setFocusPolicy(Qt.NoFocus)` — Tab moves between wallpapers, not children
- Filter panel: `AnimatedFilterPanel.eventFilter` intercepts Tab/Backtab for cycling, Enter triggers Apply
- `HoverScaleEffect` removed — was interfering with key event delivery

## Keyboard Navigation
Full reference: `KEYBOARD_NAV_MAP.md`

### Global Shortcuts (via QShortcut/QAction, Qt.ApplicationShortcut)
- `Ctrl+K` — focus search bar
- `Ctrl+N` — go home
- `Ctrl+S` — cycle source (skips Local)
- `Ctrl+D` — download focused wallpaper
- `Ctrl+L` — explore downloaded wallpapers
- `Ctrl+F` — toggle filter panel
- `Ctrl+/` — shortcuts overlay
- `Ctrl+,` — change download directory

### Grid Navigation (arrows + hjkl, wraps around rows)
- `Enter` — set wallpaper
- `Space` — preview
- `Delete` — remove downloaded file

### Filter Panel (Tab cycles within, Escape closes)
- Tab/Shift+Tab cycle checkboxes → combos → Apply button
- Enter on Apply button applies filters and closes panel
- Visual focus ring on focused filter widget (blue border)

## Dependencies
- PyQt5 (GUI), Pillow (images), numpy/opencv (image processing)
- PyInstaller (packaging), beautifulsoup4 (parsing)
- curl (system binary, used for all HTTP requests)
