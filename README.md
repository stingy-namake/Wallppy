# wallppy

A fast, dark-themed wallpaper browser and setter for Linux. Search Wallhaven.cc (more in the future) or browse your local collection.

## Features

- 🔍 Search Wallhaven.cc with filters (categories, purity, sorting, resolution, aspect ratio)
- 📁 Browse local wallpaper folders
- 💾 One-click download & set as desktop background
- 🖼️ Image preview overlay
- 🌑 Clean dark UI

## Requirements

- Python 3.9+
- PyQt5
- Linux (X11/Wayland)

## Installation

### From source

```bash
git clone https://github.com/stingy-namake/wallppy.git
cd wallppy
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py