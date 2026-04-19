import os
import platform
import subprocess
import re
import hashlib
import shutil
import sys
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
        try:
            stat = os.stat(source_path)
            cache_key = hashlib.md5(f"{source_path}:{stat.st_mtime}".encode()).hexdigest()
            return cls._cache_dir / f"{cache_key}.jpg"
        except Exception:
            return None

    @classmethod
    def set_current_wallpaper(cls, path: str):
        """Store the path of the currently active wallpaper."""
        cls._current_wallpaper_path = os.path.abspath(path) if path else None

    @classmethod
    def get_current_wallpaper(cls):
        """Return the path of the currently active wallpaper, or None."""
        return cls._current_wallpaper_path

    @staticmethod
    def _get_desktop_environment():
        """Detect the current desktop environment."""
        desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
        if 'gnome' in desktop:
            return 'gnome'
        elif 'kde' in desktop or 'plasma' in desktop:
            return 'kde'
        elif 'xfce' in desktop:
            return 'xfce'
        elif 'cosmic' in desktop:
            return 'cosmic'
        elif 'sway' in desktop:
            return 'sway'
        elif 'hyprland' in desktop:
            return 'hyprland'
        return desktop

    @staticmethod
    def _get_dbus_session_env():
        """Get the D-Bus session environment variables from the user's session."""
        env = os.environ.copy()
        
        # Try to find the D-Bus session address from various sources
        dbus_address = os.environ.get('DBUS_SESSION_BUS_ADDRESS', '')
        
        if not dbus_address:
            # Try to read from user's dbus session file
            dbus_file = os.path.expanduser(f'~/.dbus/session-bus/{os.uname().nodename}-{os.getuid()}')
            if os.path.exists(dbus_file):
                try:
                    with open(dbus_file, 'r') as f:
                        for line in f:
                            if 'DBUS_SESSION_BUS_ADDRESS' in line:
                                dbus_address = line.strip().split('=', 1)[1]
                                break
                except Exception:
                    pass
        
        if not dbus_address:
            # Try to get from dbus-launch
            try:
                result = subprocess.run(
                    ['dbus-launch', '--sh-syntax'],
                    capture_output=True, text=True, timeout=2
                )
                for line in result.stdout.split('\n'):
                    if 'DBUS_SESSION_BUS_ADDRESS' in line:
                        dbus_address = line.strip().split('=', 1)[1].strip("'\"")
                        break
            except Exception:
                pass
        
        if dbus_address:
            env['DBUS_SESSION_BUS_ADDRESS'] = dbus_address
        
        return env

    @staticmethod
    def set_wallpaper(image_path):
        """Set the desktop wallpaper based on the current OS."""
        system = platform.system()
        try:
            image_path = os.path.abspath(image_path)

            if system == "Windows":
                cached = WallpaperManager.get_cached_path(image_path)
                if cached and not cached.exists():
                    shutil.copy2(image_path, cached)
                WallpaperManager._set_windows_wallpaper(str(cached if cached else image_path))
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
        subprocess.run(["osascript", "-e", script], check=True, timeout=10)

    @staticmethod
    def _set_gnome_wallpaper(image_path, env):
        """Set GNOME wallpaper - tries multiple methods."""
        escaped_path = image_path.replace('\\', '\\\\')
        file_uri = f"file://{escaped_path}"
        
        # Method 1: Direct gsettings with preserved environment
        try:
            result = subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", file_uri],
                env=env, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=5
            )
            if result.returncode == 0:
                # Also set dark variant
                subprocess.run(
                    ["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", file_uri],
                    env=env, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
                )
                return True
        except Exception:
            pass
        
        # Method 2: dbus-send (bypasses gsettings entirely)
        try:
            cmd = [
                "dbus-send", "--session",
                "--dest=org.gnome.Shell",
                "--type=method_call",
                "--print-reply",
                "/org/gnome/Shell",
                "org.gnome.Shell.Eval",
                f"string:global.background_settings.set_string('picture-uri', '{file_uri}')"
            ]
            result = subprocess.run(cmd, env=env, check=False, capture_output=True, timeout=5)
            if result.returncode == 0:
                return True
        except Exception:
            pass
        
        # Method 3: dconf
        try:
            result = subprocess.run(
                ["dconf", "write", "/org/gnome/desktop/background/picture-uri", f"'{file_uri}'"],
                env=env, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            if result.returncode == 0:
                return True
        except Exception:
            pass
        
        return False

    @staticmethod
    def _set_linux_wallpaper(image_path):
        """Set wallpaper on Linux - detects DE and uses appropriate method."""
        escaped_path = image_path.replace('\\', '\\\\')
        file_uri = f"file://{escaped_path}"
        env = WallpaperManager._get_dbus_session_env()
        desktop = WallpaperManager._get_desktop_environment()
        
        # Try GNOME methods first (most common)
        if 'gnome' in desktop or not desktop:
            if WallpaperManager._set_gnome_wallpaper(image_path, env):
                return
        
        # ===== KDE Plasma =====
        if 'kde' in desktop or 'plasma' in desktop:
            try:
                result = subprocess.run(
                    ["plasma-apply-wallpaperimage", image_path],
                    env=env, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
                )
                if result.returncode == 0:
                    return
            except Exception:
                pass
        
        # ===== COSMIC =====
        cosmic_config = os.path.expanduser("~/.config/cosmic/com.system76.CosmicBackground/v1/all")
        cosmic_dir = os.path.dirname(cosmic_config)
        if cosmic_dir:
            try:
                os.makedirs(cosmic_dir, exist_ok=True)
                pattern = r'source: Path\(".*?"\)'
                replacement = f'source: Path("{escaped_path}")'
                
                if os.path.exists(cosmic_config):
                    with open(cosmic_config, 'r') as f:
                        content = f.read()
                    new_content = re.sub(pattern, replacement, content)
                    if "source:" not in new_content:
                        new_content += f'\nsource: Path("{escaped_path}")'
                else:
                    new_content = f'source: Path("{escaped_path}")\n'
                    
                with open(cosmic_config, 'w') as f:
                    f.write(new_content)
                return
            except Exception:
                pass
        
        # ===== Sway =====
        try:
            result = subprocess.run(
                ["swaymsg", f"output * bg {image_path} fill"],
                env=env, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            if result.returncode == 0:
                return
        except Exception:
            pass
        
        # ===== Hyprland =====
        try:
            subprocess.run(
                ["hyprctl", "hyprpaper", "preload", image_path],
                env=env, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3
            )
            result = subprocess.run(
                ["hyprctl", "hyprpaper", "wallpaper", f",{image_path}"],
                env=env, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            if result.returncode == 0:
                return
        except Exception:
            pass
        
        # ===== XFCE =====
        try:
            result = subprocess.run(
                ["xfconf-query", "-c", "xfce4-desktop", "-p", "/backdrop/screen0/monitor0/workspace0/last-image", "-s", image_path],
                env=env, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            if result.returncode == 0:
                return
        except Exception:
            pass
        
        # ===== feh (fallback) =====
        try:
            result = subprocess.run(
                ["feh", "--bg-scale", image_path],
                env=env, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            if result.returncode == 0:
                return
        except Exception:
            pass
        
        raise OSError(f"Could not set wallpaper. Desktop: {desktop}")


class WallpaperSetterWorker(QThread):
    """Worker thread to download (if needed) and set wallpaper without freezing the UI."""
    finished = pyqtSignal(bool, str, str)
    progress = pyqtSignal(int)

    def __init__(self, image_data, extension, download_folder):
        super().__init__()
        self.image_data = image_data
        self.extension = extension
        self.download_folder = download_folder
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            if self._is_cancelled:
                return
            
            image_url = self.extension.get_download_url(self.image_data)
            if not image_url:
                self.finished.emit(False, "No download URL available", "")
                return
                
            wall_id = self.extension.get_wallpaper_id(self.image_data)
            ext = self.extension.get_file_extension(self.image_data)
            filename = f"wallppy-{wall_id}.{ext}"
            filepath = os.path.join(self.download_folder, filename)

            os.makedirs(self.download_folder, exist_ok=True)

            if os.path.exists(filepath):
                if self._is_cancelled:
                    return
                success, message = WallpaperManager.set_wallpaper(filepath)
                if success:
                    WallpaperManager.set_current_wallpaper(filepath)
                self.finished.emit(success, message, filepath)
                return

            if os.path.exists(image_url):
                if self._is_cancelled:
                    return
                success, message = WallpaperManager.set_wallpaper(image_url)
                if success:
                    WallpaperManager.set_current_wallpaper(image_url)
                self.finished.emit(success, message, image_url)
                return

            if self._is_cancelled:
                return
                
            self.progress.emit(0)
            
            from core.workers import get_session
            session = get_session()
            
            try:
                response = session.get(image_url, stream=True, timeout=30)
                response.raise_for_status()
            except Exception as e:
                self.finished.emit(False, f"Download failed: {str(e)}", "")
                return

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            temp_filepath = filepath + ".tmp"
            
            try:
                with open(temp_filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if self._is_cancelled:
                            f.close()
                            os.unlink(temp_filepath)
                            return
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size:
                                progress_pct = int(downloaded * 100 / total_size)
                                self.progress.emit(progress_pct)
                
                if self._is_cancelled:
                    os.unlink(temp_filepath)
                    return
                
                shutil.move(temp_filepath, filepath)
                
                success, message = WallpaperManager.set_wallpaper(filepath)
                if success:
                    WallpaperManager.set_current_wallpaper(filepath)
                self.finished.emit(success, message, filepath)
                
            except Exception as e:
                if os.path.exists(temp_filepath):
                    try:
                        os.unlink(temp_filepath)
                    except Exception:
                        pass
                self.finished.emit(False, f"Download failed: {str(e)}", "")

        except Exception as e:
            self.finished.emit(False, str(e), "")