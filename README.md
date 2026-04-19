
<!-- <div align="center">
  <img src="https://raw.githubusercontent.com/stingy-namake/Wallppy/main/assets/Wallppy-banner.png" alt="Wallppy banner" /> -->
  
  # Wallppy
  
  *A beautiful (questionable) wallpaper manager for the linux desktop, because I'm too lazy to enter a website and download a wallpaper manually*
  
  [![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-blue)](https://github.com/stingy-namake/Wallppy)
  [![Python](https://img.shields.io/badge/python-3.11%2B-1E6FF0)](https://www.python.org/)
  [![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](https://github.com/stingy-namake/Wallppy/pulls)
  
  <br/>
  
  <!-- <img src="https://raw.githubusercontent.com/stingy-namake/Wallppy/main/assets/screenshot.png" alt="Wallppy screenshot" width="800"/> -->
  
</div>

---

## ✨ Features

- 🎯 **Multi-source browsing** - Search and browse wallpapers from multiple sources
- 🌐 **Cross-platform** - Works on Windows, macOS, and Linux (including Wayland)
- 📁 **Local library** - Browse your downloaded wallpapers with ease
- 🔍 **Powerful filtering** - Filter by resolution, aspect ratio, categories, and more
- ⚡ **Fast & responsive** - Smooth scrolling, lazy loading, and efficient caching
- 🎨 **Beautiful UI** - Modern dark theme with smooth animations
- 📥 **Batch downloads** - Queue multiple wallpapers for download
- 🖥️ **One-click apply** - Set any wallpaper as your desktop background instantly

---

## 📦 Supported Sources

| Source | Status | Description |
|--------|--------|-------------|
| **Wallhaven** | ✅ Stable | High-quality wallpapers with extensive filtering |
| **Local** | ✅ Stable | Browse your downloaded collection |
| **4K Wallpapers** | 🧪 Beta | Ultra HD wallpapers (experimental) |

*More sources coming soon!*

---

## 📋 Requirements

- **Python** 3.11 or higher
- **PyQt5** - Qt GUI framework
- **Linux** - Only runs on Linux for now

---

## 🚀 Installation

### Option 1: One-liner (Recommended)

```bash
curl -sL https://github.com/stingy-namake/Wallppy/releases/latest/download/wallppy-installer.sh | bash
```
No Python installation or dependencies required!

### Option 2: From Source (Development)

```bash
# Clone the repository
git clone https://github.com/stingy-namake/Wallppy.git
cd Wallppy

# Create a virtual environment (optional but recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run Wallppy
python main.py
```
---

## 📖 Usage

### Basic Navigation

1. **Select a source** - Choose from available wallpaper sources in the dropdown
2. **Search** - Enter keywords and press Enter (or click "explore" for recent uploads)
3. **Filter** - Click "Filters" to refine results by resolution, aspect ratio, and more
4. **Apply Filters** - Click "Apply Filters" to update results

### Working with Wallpapers

| Action | How To |
|--------|--------|
| **Preview** | Click the expand icon (⤢) on any wallpaper |
| **Download** | Double-click a thumbnail|
| **Set as Wallpaper** | Click the monitor icon (🖵) |
| **Batch Download** | Double-click multiple wallpapers - they'll queue automatically |

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` | Search (from search bar) |
| `ESC` | Close image preview |
| `↑` | Scroll to top (floating button) |

---

## 🛠️ Configuration

Wallppy stores its configuration in:
- **Linux**: `~/.config/Wallppy/settings.json`
<!-- - **Windows**: `%APPDATA%\Wallppy\settings.json` -->

### Default Settings

```json
{
  "download_folder": "./wallpapers",
  "extension": "Wallhaven",
  "categories": {
    "general": false,
    "anime": true,
    "people": false
  },
  "purity": {
    "sfw": true,
    "sketchy": false,
  }
}
```

---

## 🐛 Troubleshooting

### Wallpaper doesn't change on Linux

Wallppy supports multiple desktop environments. If automatic detection fails:

```bash
# GNOME (X11/Wayland)
gsettings set org.gnome.desktop.background picture-uri "file:///path/to/image.jpg"

# KDE Plasma
plasma-apply-wallpaperimage /path/to/image.jpg

# Sway
swaymsg output * bg /path/to/image.jpg fill

# Hyprland
hyprctl hyprpaper preload /path/to/image.jpg
hyprctl hyprpaper wallpaper ",/path/to/image.jpg"
```

### App crashes on startup

1. Check the crash log at `~/.config/Wallppy/crash.log`
2. Ensure all dependencies are installed: `pip install -r requirements.txt`
3. Try running with: `python main.py --debug`

### Wayland-specific issues

If you experience crashes on Wayland, try running with:

```bash
QT_QPA_PLATFORM=wayland python main.py
```

---

## ⚠️ Disclaimers

### Content Warning
Wallppy is a tool that aggregates wallpapers from various online sources. **We do not host, control, or take responsibility for any content served through third-party APIs.** By using Wallppy, you acknowledge that:

- You may encounter content that some users find inappropriate
- It is your responsibility to configure content filters appropriately
- You must comply with the terms of service of each wallpaper source

### Privacy
Wallppy does not collect any personal data. All settings and cache are stored locally on your device.

### API Usage
Please be respectful of the wallpaper sources' APIs. Excessive requests may result in temporary or permanent IP bans.

---

## 🙏 Acknowledgments

### Special Thanks to **Wallhaven.cc**

This project would not exist without the incredible **Wallhaven** platform (but they don't know yet). Their extensive collection of high-quality wallpapers and well-documented API make Wallppy possible.

**If you enjoy using Wallppy, please consider:**
- Supporting Wallhaven by creating an account
- Uploading your own wallpapers to the platform
- Considering a Wallhaven subscription

*Thank you, Wallhaven team, for your amazing service. And sorry for any extra load I might have generated!* 🙇

### Other Thanks

- **4kwallpapers.com** - For their collection of ultra HD wallpapers
- **The PyQt5 team** - For the excellent GUI framework
- **All contributors** - Who help make Wallppy better

---

## 🤝 Contributing

Contributions are welcome and appreciated! Here's how you can help:

```bash
# Fork and clone
git clone https://github.com/YOUR_USERNAME/Wallppy.git
cd Wallppy

# Create a feature branch
git checkout -b feature/amazing-feature

# Make your changes and commit
git commit -m "Add amazing feature"

# Push and create a Pull Request
git push origin feature/amazing-feature
```

### Ways to Contribute
- 🐛 Report bugs
- 💡 Suggest new features
- 📝 Improve documentation
- 🌐 Add new wallpaper sources
- 🎨 Improve the UI/UX
---

<!-- ## 🌟 Star History

[![Star History Chart](https://api.star-history.com/svg?repos=stingy-namake/Wallppy&type=Date)](https://star-history.com/#stingy-namake/Wallppy&Date)

---

<div align="center">
  <br/>
  <p>Made with ❤️ by <a href="https://github.com/stingy-namake">stingy-namake</a> and contributors</p>
  <p>
    <a href="https://github.com/stingy-namake/Wallppy/issues">Report Bug</a> •
    <a href="https://github.com/stingy-namake/Wallppy/issues">Request Feature</a>
  </p>
</div> -->
