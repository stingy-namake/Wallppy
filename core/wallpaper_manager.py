import os
import platform
import subprocess
import re
import shutil
from pathlib import Path
from PyQt5.QtCore import QThread, pyqtSignal


class WallpaperManager:
    """Cross-platform manager to set the desktop wallpaper."""

    _current_wallpaper_path = None

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

            if system == "Darwin":
                WallpaperManager._set_macos_wallpaper(image_path)
            elif system == "Linux":
                WallpaperManager._set_linux_wallpaper(image_path)
            else:
                raise OSError(f"Unsupported operating system: {system}")
            return True, "Wallpaper set successfully!"
        except Exception as e:
            return False, str(e)

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
    # Linux — Desktop environment detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_desktop():
        """Detect the current Linux desktop environment or compositor.

        Returns a string identifier: 'cosmic', 'niri+noctalia', 'niri',
        'gnome', 'kde', 'sway', 'hyprland', or 'unknown'.
        """
        xdg = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()

        # COSMIC
        if "cosmic" in xdg:
            return "cosmic"

        # Niri compositor
        if os.environ.get("NIRI_SOCKET") or "niri" in xdg:
            # Check for Noctalia Shell
            try:
                result = subprocess.run(
                    ["qs", "-c", "noctalia-shell", "--version"],
                    env=WallpaperManager._clean_env(),
                    capture_output=True, timeout=5
                )
                if result.returncode == 0:
                    return "niri+noctalia"
            except Exception:
                pass
            return "niri"

        # GNOME / Mutter-based
        if "gnome" in xdg or "unity" in xdg or "cinnamon" in xdg or "mate" in xdg or "budgie" in xdg:
            return "gnome"

        # KDE Plasma
        if "kde" in xdg:
            return "kde"

        # Sway
        if os.environ.get("SWAYSOCK") or "sway" in xdg:
            return "sway"

        # Hyprland
        if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") or "hyprland" in xdg:
            return "hyprland"

        # Fallback: try to infer from running processes
        try:
            result = subprocess.run(
                ["pgrep", "-x", "gnome-shell"],
                env=WallpaperManager._clean_env(),
                capture_output=True, timeout=3
            )
            if result.returncode == 0:
                return "gnome"
        except Exception:
            pass

        return "unknown"

    # ------------------------------------------------------------------
    # Linux — COSMIC
    # ------------------------------------------------------------------

    @staticmethod
    def _set_cosmic_wallpaper(image_path):
        """Set wallpaper on COSMIC Desktop by writing its RON config file."""
        config_dir = Path.home() / ".config" / "cosmic" / "com.system76.CosmicBackground" / "v1"
        config_file = config_dir / "all"

        try:
            config_dir.mkdir(parents=True, exist_ok=True)

            if not config_file.exists():
                config_file.write_text(f'(all: [source: Path("{image_path}")])')
                return True

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
    # Linux — Niri + Noctalia Shell
    # ------------------------------------------------------------------

    @staticmethod
    def _set_niri_wallpaper(image_path, noctalia=False):
        """Set wallpaper on Niri compositor."""
        env = WallpaperManager._clean_env()

        # Noctalia Shell IPC via qs
        if noctalia:
            try:
                result = subprocess.run(
                    ["qs", "-c", "noctalia-shell", "ipc", "call",
                     "wallpaper", "set", image_path, "all"],
                    env=env, check=False,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10
                )
                if result.returncode == 0:
                    return True
            except Exception:
                pass

        # swww fallback
        if shutil.which("swww"):
            try:
                result = subprocess.run(
                    ["swww", "img", image_path],
                    env=env, check=False,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10
                )
                if result.returncode == 0:
                    return True
            except Exception:
                pass

        # swaybg fallback
        if shutil.which("swaybg"):
            try:
                result = subprocess.run(
                    ["swaybg", "-i", image_path, "-m", "fill"],
                    env=env, check=False,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10
                )
                if result.returncode == 0:
                    return True
            except Exception:
                pass

        return False

    # ------------------------------------------------------------------
    # Linux — GNOME
    # ------------------------------------------------------------------

    @staticmethod
    def _set_gnome_wallpaper(image_path):
        """Set GNOME wallpaper via dconf/gsettings."""
        file_uri = f"file://{image_path}"
        env = WallpaperManager._clean_env()

        # dconf
        try:
            result = subprocess.run(
                ["dconf", "write", "/org/gnome/desktop/background/picture-uri",
                 f"'{file_uri}'"],
                env=env, check=False,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            if result.returncode == 0:
                subprocess.run(
                    ["dconf", "write", "/org/gnome/desktop/background/picture-uri-dark",
                     f"'{file_uri}'"],
                    env=env, check=False,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
                )
                return True
        except Exception:
            pass

        # gsettings with keyfile backend
        keyfile_dir = os.path.expanduser("~/.config/dconf")
        if os.path.exists(keyfile_dir):
            try:
                env_kf = env.copy()
                env_kf['GSETTINGS_BACKEND'] = 'keyfile'
                env_kf['DCONF_PROFILE'] = ''
                result = subprocess.run(
                    ["gsettings", "set", "org.gnome.desktop.background",
                     "picture-uri", file_uri],
                    env=env_kf, check=False,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
                )
                if result.returncode == 0:
                    subprocess.run(
                        ["gsettings", "set", "org.gnome.desktop.background",
                         "picture-uri-dark", file_uri],
                        env=env_kf, check=False,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
                    )
                    return True
            except Exception:
                pass

        # dbus-launch fallback
        try:
            result = subprocess.run(
                ["bash", "-c",
                 f"dbus-launch --exit-with-session gsettings set "
                 f"org.gnome.desktop.background picture-uri '{file_uri}'"],
                env=env, check=False,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            if result.returncode == 0:
                subprocess.run(
                    ["bash", "-c",
                     f"dbus-launch --exit-with-session gsettings set "
                     f"org.gnome.desktop.background picture-uri-dark '{file_uri}'"],
                    env=env, check=False,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
                )
                return True
        except Exception:
            pass

        # gconftool-2 (older GNOME)
        try:
            result = subprocess.run(
                ["gconftool-2", "--set",
                 "/desktop/gnome/background/picture_filename",
                 "--type", "string", image_path],
                env=env, check=False,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            if result.returncode == 0:
                return True
        except Exception:
            pass

        return False

    # ------------------------------------------------------------------
    # Linux — KDE Plasma
    # ------------------------------------------------------------------

    @staticmethod
    def _set_kde_wallpaper(image_path):
        """Set KDE Plasma wallpaper."""
        try:
            result = subprocess.run(
                ["plasma-apply-wallpaperimage", image_path],
                env=WallpaperManager._clean_env(),
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Linux — Sway
    # ------------------------------------------------------------------

    @staticmethod
    def _set_sway_wallpaper(image_path):
        """Set Sway wallpaper."""
        try:
            result = subprocess.run(
                ["swaymsg", f"output * bg {image_path} fill"],
                env=WallpaperManager._clean_env(),
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Linux — Hyprland
    # ------------------------------------------------------------------

    @staticmethod
    def _set_hyprland_wallpaper(image_path):
        """Set Hyprland wallpaper."""
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
            return result.returncode == 0
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Linux — Fallbacks (X11)
    # ------------------------------------------------------------------

    @staticmethod
    def _set_feh_wallpaper(image_path):
        """Set wallpaper via feh."""
        try:
            result = subprocess.run(
                ["feh", "--bg-scale", image_path],
                env=WallpaperManager._clean_env(),
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def _set_nitrogen_wallpaper(image_path):
        """Set wallpaper via nitrogen."""
        try:
            result = subprocess.run(
                ["nitrogen", "--set-zoom-fill", image_path],
                env=WallpaperManager._clean_env(),
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Linux — Dispatcher
    # ------------------------------------------------------------------

    @staticmethod
    def _set_linux_wallpaper(image_path):
        """Set wallpaper on Linux by detecting the desktop environment."""
        desktop = WallpaperManager._detect_desktop()

        if desktop == "cosmic":
            if WallpaperManager._set_cosmic_wallpaper(image_path):
                return

        elif desktop == "niri+noctalia":
            if WallpaperManager._set_niri_wallpaper(image_path, noctalia=True):
                return

        elif desktop == "niri":
            if WallpaperManager._set_niri_wallpaper(image_path, noctalia=False):
                return

        elif desktop == "gnome":
            if WallpaperManager._set_gnome_wallpaper(image_path):
                return

        elif desktop == "kde":
            if WallpaperManager._set_kde_wallpaper(image_path):
                return

        elif desktop == "sway":
            if WallpaperManager._set_sway_wallpaper(image_path):
                return

        elif desktop == "hyprland":
            if WallpaperManager._set_hyprland_wallpaper(image_path):
                return

        # Unknown DE or detected method failed — try fallbacks
        for fallback in [WallpaperManager._set_feh_wallpaper,
                         WallpaperManager._set_nitrogen_wallpaper]:
            if fallback(image_path):
                return

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
