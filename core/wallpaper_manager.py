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
        cls._current_wallpaper_path = os.path.abspath(path) if path else None

    @classmethod
    def get_current_wallpaper(cls):
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
    def _run_cmd(cmd, env=None, timeout=5):
        """Run a command silently, return True on success."""
        try:
            result = subprocess.run(
                cmd, env=env or WallpaperManager._clean_env(),
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=timeout
            )
            return result.returncode == 0
        except Exception:
            return False

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
        """Detect the current Linux desktop environment or compositor."""
        xdg = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()

        if "cosmic" in xdg:
            return "cosmic"

        if os.environ.get("NIRI_SOCKET") or "niri" in xdg:
            if WallpaperManager._run_cmd(
                ["qs", "-c", "noctalia-shell", "--version"]
            ):
                return "niri+noctalia"
            return "niri"

        if "gnome" in xdg or "unity" in xdg or "cinnamon" in xdg or "mate" in xdg or "budgie" in xdg:
            return "gnome"

        if "kde" in xdg:
            return "kde"

        if os.environ.get("SWAYSOCK") or "sway" in xdg:
            return "sway"

        if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") or "hyprland" in xdg:
            return "hyprland"

        # Fallback: infer from running processes
        if WallpaperManager._run_cmd(["pgrep", "-x", "gnome-shell"], timeout=3):
            return "gnome"

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
        if noctalia:
            if WallpaperManager._run_cmd(
                ["qs", "-c", "noctalia-shell", "ipc", "call",
                 "wallpaper", "set", image_path, "all"],
                timeout=10
            ):
                return True

        if shutil.which("swww"):
            if WallpaperManager._run_cmd(["swww", "img", image_path], timeout=10):
                return True

        if shutil.which("swaybg"):
            if WallpaperManager._run_cmd(["swaybg", "-i", image_path, "-m", "fill"], timeout=10):
                return True

        return False

    # ------------------------------------------------------------------
    # Linux — GNOME
    # ------------------------------------------------------------------

    @staticmethod
    def _set_gnome_wallpaper(image_path):
        """Set GNOME wallpaper via dconf/gsettings."""
        file_uri = f"file://{image_path}"
        keys = ["picture-uri", "picture-uri-dark"]
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
                WallpaperManager._run_cmd(
                    ["dconf", "write", "/org/gnome/desktop/background/picture-uri-dark",
                     f"'{file_uri}'"],
                    env=env, timeout=5
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
                    WallpaperManager._run_cmd(
                        ["gsettings", "set", "org.gnome.desktop.background",
                         "picture-uri-dark", file_uri],
                        env=env_kf, timeout=5
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
                WallpaperManager._run_cmd(
                    ["bash", "-c",
                     f"dbus-launch --exit-with-session gsettings set "
                     f"org.gnome.desktop.background picture-uri-dark '{file_uri}'"],
                    env=env, timeout=5
                )
                return True
        except Exception:
            pass

        # gconftool-2 (older GNOME)
        if WallpaperManager._run_cmd(
            ["gconftool-2", "--set",
             "/desktop/gnome/background/picture_filename",
             "--type", "string", image_path],
            env=env, timeout=5
        ):
            return True

        return False

    # ------------------------------------------------------------------
    # Linux — Dispatcher
    # ------------------------------------------------------------------

    @staticmethod
    def _set_linux_wallpaper(image_path):
        """Set wallpaper on Linux by detecting the desktop environment."""
        desktop = WallpaperManager._detect_desktop()

        dispatch = {
            "cosmic":       lambda: WallpaperManager._set_cosmic_wallpaper(image_path),
            "niri+noctalia": lambda: WallpaperManager._set_niri_wallpaper(image_path, noctalia=True),
            "niri":         lambda: WallpaperManager._set_niri_wallpaper(image_path, noctalia=False),
            "gnome":        lambda: WallpaperManager._set_gnome_wallpaper(image_path),
            "kde":          lambda: WallpaperManager._run_cmd(["plasma-apply-wallpaperimage", image_path]),
            "sway":         lambda: WallpaperManager._run_cmd(["swaymsg", f"output * bg {image_path} fill"]),
            "hyprland":     lambda: WallpaperManager._run_cmd(
                ["hyprctl", "hyprpaper", "preload", image_path]
            ) and WallpaperManager._run_cmd(
                ["hyprctl", "hyprpaper", "wallpaper", f",{image_path}"]
            ),
        }

        if desktop in dispatch and dispatch[desktop]():
            return

        # Fallbacks
        for cmd in [["feh", "--bg-scale", image_path],
                     ["nitrogen", "--set-zoom-fill", image_path]]:
            if WallpaperManager._run_cmd(cmd):
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

            # Use curl — requests is broken on some machines
            import subprocess
            temp_filepath = filepath + ".tmp"
            try:
                result = subprocess.run(
                    ["curl", "-sL", "--max-time", "60",
                     "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                     "-o", temp_filepath, "-w", "%{http_code}",
                     image_url],
                    capture_output=True, text=True, timeout=70)
                http_code = result.stdout.strip()
                if http_code != "200" or not os.path.exists(temp_filepath) or os.path.getsize(temp_filepath) == 0:
                    if os.path.exists(temp_filepath):
                        os.unlink(temp_filepath)
                    self.finished.emit(False, f"Download failed: HTTP {http_code}", "")
                    return

                self.progress.emit(100)

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
