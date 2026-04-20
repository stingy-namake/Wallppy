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
    def _clean_env():
        """Return environment safe for system binaries.
        
        PyInstaller onefile pollutes LD_LIBRARY_PATH with its temp dir,
        causing gsettings/dconf to load incompatible bundled libs.
        """
        env = os.environ.copy()
        env.pop('LD_LIBRARY_PATH', None)
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
        subprocess.run(
            ["osascript", "-e", script],
            env=WallpaperManager._clean_env(),
            check=True,
            timeout=10
        )

    @staticmethod
    def _set_linux_wallpaper(image_path):
        escaped_path = image_path.replace('\\', '\\\\')
        
        # ===== COSMIC desktop (System76) =====
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
        
        # ===== GNOME / Unity / Cinnamon =====
        gnome_commands = [
            ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", f"file://{image_path}"],
            ["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", f"file://{image_path}"]
        ]
        
        gnome_success = False
        for cmd in gnome_commands:
            try:
                subprocess.run(
                    cmd,
                    env=WallpaperManager._clean_env(),
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5
                )
                gnome_success = True
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        
        if gnome_success:
            return
        
        # ===== KDE Plasma =====
        try:
            subprocess.run(
                ["plasma-apply-wallpaperimage", image_path],
                env=WallpaperManager._clean_env(),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5
            )
            return
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # ===== XFCE =====
        try:
            subprocess.run(
                ["xfconf-query", "-c", "xfce4-desktop", "-p", "/backdrop/screen0/monitor0/workspace0/last-image", "-s", image_path],
                env=WallpaperManager._clean_env(),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5
            )
            return
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # ===== LXQt / PCManFM =====
        try:
            subprocess.run(
                ["pcmanfm", "--set-wallpaper", image_path],
                env=WallpaperManager._clean_env(),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5
            )
            return
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # ===== Sway =====
        try:
            subprocess.run(
                ["swaymsg", f"output * bg {image_path} fill"],
                env=WallpaperManager._clean_env(),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5
            )
            return
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # ===== Hyprland =====
        try:
            subprocess.run(
                ["hyprctl", "hyprpaper", "preload", image_path],
                env=WallpaperManager._clean_env(),
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3
            )
            subprocess.run(
                ["hyprctl", "hyprpaper", "wallpaper", f",{image_path}"],
                env=WallpaperManager._clean_env(),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5
            )
            return
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # ===== Fallback: feh (common on minimal WMs) =====
        try:
            subprocess.run(
                ["feh", "--bg-scale", image_path],
                env=WallpaperManager._clean_env(),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5
            )
            return
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # ===== Fallback: nitrogen =====
        try:
            subprocess.run(
                ["nitrogen", "--set-zoom-fill", image_path],
                env=WallpaperManager._clean_env(),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5
            )
            return
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        raise OSError("Could not set wallpaper. No supported desktop environment found.")


class WallpaperSetterWorker(QThread):
    """Worker thread to download (if needed) and set wallpaper without freezing the UI."""
    finished = pyqtSignal(bool, str, str)  # success, message, final_filepath
    progress = pyqtSignal(int)
    _is_cancelled = False

    def __init__(self, image_data, extension, download_folder):
        super().__init__()
        self.image_data = image_data
        self.extension = extension
        self.download_folder = download_folder

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

            # Already downloaded locally
            if os.path.exists(filepath):
                if self._is_cancelled:
                    return
                success, message = WallpaperManager.set_wallpaper(filepath)
                if success:
                    WallpaperManager.set_current_wallpaper(filepath)
                self.finished.emit(success, message, filepath)
                return

            # Local file (e.g., from LocalExtension)
            if os.path.exists(image_url):
                if self._is_cancelled:
                    return
                success, message = WallpaperManager.set_wallpaper(image_url)
                if success:
                    WallpaperManager.set_current_wallpaper(image_url)
                self.finished.emit(success, message, image_url)
                return

            # Download from online source
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
                                self.progress.emit(int(downloaded * 100 / total_size))

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