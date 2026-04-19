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
    def _find_command(cmd_name):
        """Find the full path of a command, handling PyInstaller environment."""
        # Check if running in PyInstaller bundle
        if getattr(sys, 'frozen', False):
            # Common paths in PyInstaller environment
            paths = [
                '/usr/bin',
                '/usr/local/bin',
                '/bin',
                '/snap/bin',
                os.environ.get('PATH', '').split(':')
            ]
            # Flatten the list
            all_paths = []
            for p in paths:
                if isinstance(p, str) and p not in all_paths:
                    all_paths.append(p)
            
            for path in all_paths:
                full_path = os.path.join(path, cmd_name)
                if os.path.exists(full_path) and os.access(full_path, os.X_OK):
                    return full_path
        return cmd_name  # Return as-is, let subprocess use PATH

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
    def _set_linux_wallpaper(image_path):
        """Set wallpaper on Linux - supports GNOME, KDE, XFCE, COSMIC, Sway, Hyprland."""
        escaped_path = image_path.replace('\\', '\\\\')
        file_uri = f"file://{escaped_path}"
        
        # ===== GNOME / Unity / Cinnamon (Wayland & X11) =====
        gsettings_path = WallpaperManager._find_command("gsettings")
        gnome_commands = [
            [gsettings_path, "set", "org.gnome.desktop.background", "picture-uri", file_uri],
            [gsettings_path, "set", "org.gnome.desktop.background", "picture-uri-dark", file_uri],
            [gsettings_path, "set", "org.gnome.desktop.screensaver", "picture-uri", file_uri],
        ]
        
        gnome_success = False
        for cmd in gnome_commands:
            try:
                result = subprocess.run(
                    cmd, 
                    check=False,
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.PIPE,
                    timeout=5,
                    env=os.environ.copy()  # Pass full environment
                )
                if result.returncode == 0:
                    gnome_success = True
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
        
        if gnome_success:
            return
        
        # ===== COSMIC desktop (System76) =====
        cosmic_config = os.path.expanduser("~/.config/cosmic/com.system76.CosmicBackground/v1/all")
        if os.path.exists(os.path.dirname(cosmic_config)):
            try:
                os.makedirs(os.path.dirname(cosmic_config), exist_ok=True)
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
        
        # ===== KDE Plasma =====
        plasma_cmd = WallpaperManager._find_command("plasma-apply-wallpaperimage")
        try:
            result = subprocess.run(
                [plasma_cmd, image_path],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                env=os.environ.copy()
            )
            if result.returncode == 0:
                return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # ===== Sway (Wayland) =====
        sway_cmd = WallpaperManager._find_command("swaymsg")
        try:
            result = subprocess.run(
                [sway_cmd, f"output * bg {image_path} fill"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                env=os.environ.copy()
            )
            if result.returncode == 0:
                return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # ===== Hyprland (Wayland) =====
        hyprctl_cmd = WallpaperManager._find_command("hyprctl")
        try:
            subprocess.run(
                [hyprctl_cmd, "hyprpaper", "preload", image_path],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
                env=os.environ.copy()
            )
            result = subprocess.run(
                [hyprctl_cmd, "hyprpaper", "wallpaper", f",{image_path}"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                env=os.environ.copy()
            )
            if result.returncode == 0:
                return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # ===== XFCE =====
        xfconf_cmd = WallpaperManager._find_command("xfconf-query")
        try:
            monitor_name = "monitor0"
            try:
                xrandr_cmd = WallpaperManager._find_command("xrandr")
                result = subprocess.run(
                    [xrandr_cmd, "--listmonitors"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    env=os.environ.copy()
                )
                monitors = result.stdout.strip().split('\n')
                if len(monitors) > 1:
                    match = re.search(r'(\S+)$', monitors[1])
                    if match:
                        monitor_name = match.group(1)
            except Exception:
                pass
            
            xfce_success = False
            for ws in range(4):
                try:
                    result = subprocess.run([
                        xfconf_cmd, "-c", "xfce4-desktop", "-p",
                        f"/backdrop/screen0/{monitor_name}/workspace{ws}/last-image",
                        "-s", image_path
                    ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3,
                       env=os.environ.copy())
                    if result.returncode == 0:
                        xfce_success = True
                except Exception:
                    continue
            if xfce_success:
                return
        except Exception:
            pass
        
        # ===== feh (minimal WMs) =====
        feh_cmd = WallpaperManager._find_command("feh")
        try:
            result = subprocess.run(
                [feh_cmd, "--bg-scale", image_path],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                env=os.environ.copy()
            )
            if result.returncode == 0:
                return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # ===== nitrogen =====
        nitrogen_cmd = WallpaperManager._find_command("nitrogen")
        try:
            result = subprocess.run(
                [nitrogen_cmd, "--set-zoom-fill", image_path],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                env=os.environ.copy()
            )
            if result.returncode == 0:
                return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
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
        self._is_cancelled = False

    def cancel(self):
        """Cancel the wallpaper setting operation."""
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