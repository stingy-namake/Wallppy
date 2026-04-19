import os
import platform
import subprocess
import re
import hashlib
import shutil
from pathlib import Path
from PyQt5.QtCore import QThread, pyqtSignal


class WallpaperManager:
    """Cross-platform manager to set the desktop wallpaper."""

    _cache_dir = Path.home() / ".cache" / "wallppy"
    _current_wallpaper_path = None

    @classmethod
    def _ensure_cache_dir(cls):
        cls._cache_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_cached_path(cls, source_path):
        """Get cached path for a wallpaper copy (prevents file locks on Windows)."""
        cls._ensure_cache_dir()
        stat = os.stat(source_path)
        cache_key = hashlib.md5(f"{source_path}:{stat.st_mtime}".encode()).hexdigest()
        return cls._cache_dir / f"{cache_key}.jpg"

    @classmethod
    def set_current_wallpaper(cls, path: str):
        """Store the path of the currently active wallpaper."""
        cls._current_wallpaper_path = os.path.abspath(path) if path else None

    @classmethod
    def get_current_wallpaper(cls):
        """Return the path of the currently active wallpaper, or None."""
        return cls._current_wallpaper_path

    @staticmethod
    def set_wallpaper(image_path):
        """Set the desktop wallpaper based on the current OS."""
        system = platform.system()
        try:
            image_path = os.path.abspath(image_path)

            if system == "Windows":
                cached = WallpaperManager.get_cached_path(image_path)
                if not cached.exists():
                    shutil.copy2(image_path, cached)
                WallpaperManager._set_windows_wallpaper(str(cached))
            elif system == "Darwin":
                WallpaperManager._set_macos_wallpaper(image_path)
            elif system == "Linux":
                WallpaperManager._set_linux_wallpaper(image_path)
            else:
                raise OSError(f"Unsupported operating system: {system}")
            return True, "Wallpaper set successfully!"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def _set_windows_wallpaper(image_path):
        import ctypes
        SPI_SETDESKWALLPAPER = 20
        SPIF_UPDATEINIFILE = 0x01
        SPIF_SENDWININICHANGE = 0x02
        ctypes.windll.user32.SystemParametersInfoW(
            SPI_SETDESKWALLPAPER, 0, image_path,
            SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE
        )

    @staticmethod
    def _set_macos_wallpaper(image_path):
        script = f'tell application "Finder" to set desktop picture to POSIX file "{image_path}"'
        subprocess.run(["osascript", "-e", script], check=True)

    @staticmethod    
    def _set_linux_wallpaper(image_path):
        """Set wallpaper on Linux - supports GNOME, KDE, XFCE, COSMIC, and fallbacks."""
        escaped_path = image_path.replace('\\', '\\\\')
        file_uri = f"file://{escaped_path}"
        
        # GNOME / Unity / Cinnamon (including Wayland)
        # Try both gsettings commands - they work on both X11 and Wayland
        gnome_commands = [
            ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", file_uri],
            ["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", file_uri],
            ["gsettings", "set", "org.gnome.desktop.screensaver", "picture-uri", file_uri],
        ]
        
        for cmd in gnome_commands:
            try:
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                # GNOME succeeded - return immediately
                return
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                continue
        
        # COSMIC desktop (System76)
        cosmic_config = os.path.expanduser("~/.config/cosmic/com.system76.CosmicBackground/v1/all")
        if os.path.exists(cosmic_config):
            try:
                pattern = r'source: Path\(".*?"\)'
                replacement = f'source: Path("{escaped_path}")'
                with open(cosmic_config, 'r') as f:
                    content = f.read()
                new_content = re.sub(pattern, replacement, content)
                if "source:" not in new_content:
                    new_content += f'\nsource: Path("{escaped_path}")'
                with open(cosmic_config, 'w') as f:
                    f.write(new_content)
                return
            except Exception:
                pass
        
        # KDE Plasma (X11 and Wayland)
        try:
            subprocess.run(["plasma-apply-wallpaperimage", image_path], 
                        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            return
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # XFCE
        try:
            # Try to get the current monitor
            result = subprocess.run(["xrandr", "--listmonitors"], capture_output=True, text=True, timeout=2)
            monitors = result.stdout.strip().split('\n')
            monitor_name = "monitor0"
            if len(monitors) > 1:
                # Extract monitor name from first monitor line
                import re
                match = re.search(r'(\S+)$', monitors[1])
                if match:
                    monitor_name = match.group(1)
            
            # Set for each workspace
            for ws in range(4):
                subprocess.run([
                    "xfconf-query", "-c", "xfce4-desktop", "-p", 
                    f"/backdrop/screen0/{monitor_name}/workspace{ws}/last-image", 
                    "-s", image_path
                ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
            return
        except Exception:
            pass
        
        # feh (common on minimal WMs)
        try:
            subprocess.run(["feh", "--bg-scale", image_path], 
                        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            return
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # sway (Wayland compositor)
        try:
            subprocess.run(["swaymsg", f"output * bg {image_path} fill"], 
                        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            return
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # hyprland (Wayland compositor)
        try:
            subprocess.run(["hyprctl", "hyprpaper", "preload", image_path], 
                        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
            subprocess.run(["hyprctl", "hyprpaper", "wallpaper", f",{image_path}"], 
                        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            return
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # If we get here, nothing worked
        raise OSError("Could not set wallpaper. No supported desktop environment found.")


class WallpaperSetterWorker(QThread):
    """Worker thread to download (if needed) and set wallpaper without freezing the UI."""
    finished = pyqtSignal(bool, str, str)  # success, message, final_filepath
    progress = pyqtSignal(int)

    def __init__(self, image_data, extension, download_folder):
        super().__init__()
        self.image_data = image_data
        self.extension = extension
        self.download_folder = download_folder

    def run(self):
        try:
            image_url = self.extension.get_download_url(self.image_data)
            wall_id = self.extension.get_wallpaper_id(self.image_data)
            ext = self.extension.get_file_extension(self.image_data)
            filename = f"wallppy-{wall_id}.{ext}"
            filepath = os.path.join(self.download_folder, filename)

            os.makedirs(self.download_folder, exist_ok=True)

            # Already downloaded locally
            if os.path.exists(filepath):
                success, message = WallpaperManager.set_wallpaper(filepath)
                if success:
                    WallpaperManager.set_current_wallpaper(filepath)
                self.finished.emit(success, message, filepath)
                return

            # Local file (e.g., from LocalExtension)
            if os.path.exists(image_url):
                success, message = WallpaperManager.set_wallpaper(image_url)
                if success:
                    WallpaperManager.set_current_wallpaper(image_url)
                self.finished.emit(success, message, image_url)
                return

            # Download from online source
            self.progress.emit(0)
            from core.workers import get_session
            session = get_session()
            response = session.get(image_url, stream=True, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size:
                            self.progress.emit(int(downloaded * 100 / total_size))

            success, message = WallpaperManager.set_wallpaper(filepath)
            if success:
                WallpaperManager.set_current_wallpaper(filepath)
            self.finished.emit(success, message, filepath)

        except Exception as e:
            self.finished.emit(False, str(e), "")