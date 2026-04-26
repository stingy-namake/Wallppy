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
    def _clean_env():
        """Return environment safe for system binaries.

        PyInstaller onefile pollutes LD_LIBRARY_PATH with its temp dir,
        causing gsettings/dconf to load incompatible bundled libs.
        """
        env = os.environ.copy()
        env.pop('LD_LIBRARY_PATH', None)
        return env

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Windows
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # macOS
    # ------------------------------------------------------------------

    @staticmethod
    def _set_macos_wallpaper(image_path):
        script = f'tell application "Finder" to set desktop picture to POSIX file "{image_path}"'
        subprocess.run(
            ["osascript", "-e", script],
            env=WallpaperManager._clean_env(),
            check=True, timeout=10
        )

    # ------------------------------------------------------------------
    # Linux — GNOME
    # ------------------------------------------------------------------

    @staticmethod
    def _set_gnome_wallpaper_direct(image_path):
        """Set GNOME wallpaper by writing directly to config files (works in PyInstaller)."""
        file_uri = f"file://{image_path}"

        success = False

        # Method 1: dconf write
        try:
            result = subprocess.run(
                ["dconf", "write", "/org/gnome/desktop/background/picture-uri",
                 f"'{file_uri}'"],
                env=WallpaperManager._clean_env(),
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            if result.returncode == 0:
                subprocess.run(
                    ["dconf", "write",
                     "/org/gnome/desktop/background/picture-uri-dark",
                     f"'{file_uri}'"],
                    env=WallpaperManager._clean_env(),
                    check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
                )
                success = True
        except Exception:
            pass

        # Method 2: gsettings with keyfile backend
        keyfile_dir = os.path.expanduser("~/.config/dconf")
        if os.path.exists(keyfile_dir):
            try:
                env = WallpaperManager._clean_env()
                env['GSETTINGS_BACKEND'] = 'keyfile'
                env['DCONF_PROFILE'] = ''
                result = subprocess.run(
                    ["gsettings", "set", "org.gnome.desktop.background",
                     "picture-uri", file_uri],
                    env=env, check=False,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
                )
                if result.returncode == 0:
                    subprocess.run(
                        ["gsettings", "set", "org.gnome.desktop.background",
                         "picture-uri-dark", file_uri],
                        env=env, check=False,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
                    )
                    success = True
            except Exception:
                pass

        # Method 3: dbus-launch + gsettings
        if not success:
            try:
                cmd = (
                    f"dbus-launch --exit-with-session gsettings set "
                    f"org.gnome.desktop.background picture-uri '{file_uri}'"
                )
                result = subprocess.run(
                    ["bash", "-c", cmd],
                    env=WallpaperManager._clean_env(),
                    check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
                )
                if result.returncode == 0:
                    cmd_dark = (
                        f"dbus-launch --exit-with-session gsettings set "
                        f"org.gnome.desktop.background picture-uri-dark '{file_uri}'"
                    )
                    subprocess.run(
                        ["bash", "-c", cmd_dark],
                        env=WallpaperManager._clean_env(),
                        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
                    )
                    success = True
            except Exception:
                pass

        # Method 4: gconftool-2 (older GNOME)
        if not success:
            try:
                result = subprocess.run(
                    ["gconftool-2", "--set",
                     "/desktop/gnome/background/picture_filename",
                     "--type", "string", image_path],
                    env=WallpaperManager._clean_env(),
                    check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
                )
                if result.returncode == 0:
                    success = True
            except Exception:
                pass

        # Method 5: xfconf-query (XFCE)
        if not success:
            try:
                result = subprocess.run(
                    ["xfconf-query", "-c", "xfce4-desktop",
                     "-p", "/backdrop/screen0/monitor0/workspace0/last-image",
                     "-s", image_path],
                    env=WallpaperManager._clean_env(),
                    check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
                )
                if result.returncode == 0:
                    success = True
            except Exception:
                pass

        return success

    # ------------------------------------------------------------------
    # Linux — COSMIC
    # ------------------------------------------------------------------
    
    @staticmethod
    def _is_cosmic():
        """Check if the current desktop environment is COSMIC."""
        desktop = os.environ.get('XDG_CURRENT_DESKTOP', '')
        return 'COSMIC' in desktop.split(':')

    @staticmethod
    def _set_cosmic_wallpaper(image_path):
        """
        Set wallpaper on COSMIC Desktop instantly by writing its RON config file.
        The cosmic-bg daemon watches this file with inotify and reloads automatically.
        """
        config_dir = Path.home() / ".config" / "cosmic" / "com.system76.CosmicBackground" / "v1"
        config_file = config_dir / "all"

        try:
            config_dir.mkdir(parents=True, exist_ok=True)

            # If config file doesn't exist, create a minimal valid one
            if not config_file.exists():
                config_file.write_text(f'(all: [source: Path("{image_path}")])')
                return True

            # Read and update existing config
            content = config_file.read_text()
            escaped_path = image_path.replace('\\', '\\\\')
            new_content = re.sub(
                r'source:\s*Path\(".*?"\)',
                f'source: Path("{escaped_path}")',
                content
            )
            config_file.write_text(new_content)
            return True

        except Exception:
            return False

    # ------------------------------------------------------------------
    # Linux — dispatcher
    # ------------------------------------------------------------------

    @staticmethod
    def _set_linux_wallpaper(image_path):
        """Set wallpaper on Linux — tries multiple desktop environments."""

        # ===== COSMIC (must come before GNOME — COSMIC does NOT set GNOME vars) =====
        if WallpaperManager._is_cosmic():
            if WallpaperManager._set_cosmic_wallpaper(image_path):
                return
            # Fall through to generic methods if COSMIC write failed

        # ===== GNOME / Mutter-based =====
        if WallpaperManager._set_gnome_wallpaper_direct(image_path):
            return

        # ===== KDE Plasma =====
        try:
            result = subprocess.run(
                ["plasma-apply-wallpaperimage", image_path],
                env=WallpaperManager._clean_env(),
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            if result.returncode == 0:
                return
        except Exception:
            pass

        # ===== Sway =====
        try:
            result = subprocess.run(
                ["swaymsg", f"output * bg {image_path} fill"],
                env=WallpaperManager._clean_env(),
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            if result.returncode == 0:
                return
        except Exception:
            pass

        # ===== Hyprland =====
        try:
            subprocess.run(
                ["hyprctl", "hyprpaper", "preload", image_path],
                env=WallpaperManager._clean_env(),
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3
            )
            result = subprocess.run(
                ["hyprctl", "hyprpaper", "wallpaper", f",{image_path}"],
                env=WallpaperManager._clean_env(),
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            if result.returncode == 0:
                return
        except Exception:
            pass

        # ===== feh (X11 fallback) =====
        try:
            result = subprocess.run(
                ["feh", "--bg-scale", image_path],
                env=WallpaperManager._clean_env(),
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            if result.returncode == 0:
                return
        except Exception:
            pass

        # ===== nitrogen (X11 fallback) =====
        try:
            result = subprocess.run(
                ["nitrogen", "--set-zoom-fill", image_path],
                env=WallpaperManager._clean_env(),
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            if result.returncode == 0:
                return
        except Exception:
            pass

        raise OSError("Could not set wallpaper. No supported desktop environment found.")


# ----------------------------------------------------------------------
# Worker thread
# ----------------------------------------------------------------------

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

            if hasattr(self.extension, 'get_download_url_for_set'):
                image_url = self.extension.get_download_url_for_set(self.image_data)
            else:
                image_url = self.extension.get_download_url(self.image_data)
            if not image_url:
                self.finished.emit(False, "No download URL available", "")
                return

            wall_id = self.extension.get_wallpaper_id(self.image_data)
            ext = self.extension.get_file_extension(self.image_data)
            filename = f"wallppy-{wall_id}.{ext}"
            filepath = os.path.join(self.download_folder, filename)

            os.makedirs(self.download_folder, exist_ok=True)

            # Already downloaded — set directly
            if os.path.exists(filepath):
                if self._is_cancelled:
                    return
                success, message = WallpaperManager.set_wallpaper(filepath)
                if success:
                    WallpaperManager.set_current_wallpaper(filepath)
                self.finished.emit(success, message, filepath)
                return

            # Local file path provided (no download needed)
            if os.path.exists(image_url):
                if self._is_cancelled:
                    return
                success, message = WallpaperManager.set_wallpaper(image_url)
                if success:
                    WallpaperManager.set_current_wallpaper(image_url)
                self.finished.emit(success, message, image_url)
                return

            # Download required
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
