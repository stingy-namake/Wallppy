#!/usr/bin/env python3

import os
import sys
import subprocess
import shutil
import json
import argparse
import tempfile
from pathlib import Path

__version__ = "3.6.2"

REPO = "stingy-namake/Wallppy"
GITHUB_API = "https://api.github.com/repos"


# ── CLI Commands ──────────────────────────────────────────────────

def cmd_update(args):
    print("Checking for updates...")
    tag = args.version or _github_latest_tag()
    if not tag:
        print("Failed to fetch latest version from GitHub.")
        sys.exit(1)

    current = f"v{__version__}"
    if tag == current and not args.force:
        print(f"Already up to date ({current}).")
        return

    print(f"Updating: {current} -> {tag}")

    binary_path = _find_binary()
    if not binary_path:
        print("Cannot find wallppy binary. Was it installed via installer?")
        sys.exit(1)

    install_prefix = Path(binary_path).parent.parent
    arch = "x86_64" if sys.maxsize > 2**32 else "arm64"

    tmp_dir = tempfile.mkdtemp()
    try:
        asset_name = _github_find_asset(tag, arch)
        if not asset_name:
            print(f"Could not find release asset for {tag} ({arch}).")
            sys.exit(1)

        download_url = f"https://github.com/{REPO}/releases/download/{tag}/{asset_name}"
        tmp_bin = os.path.join(tmp_dir, "wallppy-new")

        print(f"Downloading {asset_name}...")
        result = subprocess.run(
            ["curl", "-sL", "--fail", "-o", tmp_bin, download_url],
            capture_output=True, text=True)
        if result.returncode != 0 or not os.path.exists(tmp_bin):
            print("Download failed.")
            sys.exit(1)
        os.chmod(tmp_bin, 0o755)

        backup = binary_path + ".bak"
        shutil.copy2(binary_path, backup)
        try:
            shutil.move(tmp_bin, binary_path)
        except Exception:
            shutil.move(backup, binary_path)
            print("Failed to replace binary. Restored backup.")
            sys.exit(1)
        os.remove(backup)

        _install_icon(install_prefix, tag, tmp_dir)
        _install_desktop(install_prefix, binary_path)
        print(f"Updated to {tag}. Restart wallppy to use the new version.")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def cmd_uninstall(args):
    binary_path = _find_binary()
    if not binary_path:
        print("wallppy not found.")
        sys.exit(1)

    install_prefix = Path(binary_path).parent.parent

    files = [
        binary_path,
        str(install_prefix / "share" / "applications" / "wallppy.desktop"),
        str(install_prefix / "share" / "icons" / "hicolor" / "256x256" / "apps" / "wallppy.png"),
    ]

    dirs = [
        Path.home() / ".config" / "wallppy",
        Path.home() / ".cache" / "wallppy",
    ]

    print("The following will be removed:")
    for f in files:
        if os.path.exists(f):
            print(f"  {f}")
    for d in dirs:
        if d.exists():
            print(f"  {d}/")

    if not args.yes:
        confirm = input("\nProceed? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return

    for f in files:
        if os.path.exists(f):
            os.remove(f)
    for d in dirs:
        if d.exists():
            shutil.rmtree(d)

    desktop_dir = install_prefix / "share" / "applications"
    if desktop_dir.exists() and shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", str(desktop_dir)],
                       capture_output=True)

    print("Uninstalled.")


def cmd_clean(_args):
    cache_dir = Path.home() / ".cache" / "wallppy"
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        print(f"Cache cleared: {cache_dir}")
    else:
        print("No cache found.")


def cmd_clean_all(_args):
    config_dir = Path.home() / ".config" / "wallppy"
    cache_dir = Path.home() / ".cache" / "wallppy"
    for d in [cache_dir, config_dir]:
        if d.exists():
            shutil.rmtree(d)
            print(f"Removed: {d}")
    if not config_dir.exists() and not cache_dir.exists():
        print("Nothing to clean.")


# ── CLI Helpers ───────────────────────────────────────────────────

def _find_binary():
    path = shutil.which("wallppy")
    if path:
        return path
    argv0 = Path(sys.argv[0]).resolve()
    if argv0.exists():
        return str(argv0)
    return None


def _github_latest_tag():
    result = subprocess.run(
        ["curl", "-sL", "--fail",
         f"{GITHUB_API}/{REPO}/releases/latest"],
        capture_output=True, text=True)
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
        return data.get("tag_name")
    except (json.JSONDecodeError, AttributeError):
        return None


def _github_find_asset(tag, arch):
    url = f"{GITHUB_API}/{REPO}/releases/tags/{tag}"
    result = subprocess.run(
        ["curl", "-sL", "--fail", url],
        capture_output=True, text=True)
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
        for asset in data.get("assets", []):
            name = asset.get("name", "")
            if "linux" in name and arch in name:
                return name
        for asset in data.get("assets", []):
            name = asset.get("name", "")
            if "linux" in name:
                return name
    except (json.JSONDecodeError, AttributeError):
        pass
    return None


def _install_icon(prefix, tag, tmp_dir):
    icon_dir = prefix / "share" / "icons" / "hicolor" / "256x256" / "apps"
    icon_dir.mkdir(parents=True, exist_ok=True)
    icon_path = icon_dir / "wallppy.png"
    url = f"https://raw.githubusercontent.com/{REPO}/{tag}/.resources/cool_image.png"
    result = subprocess.run(
        ["curl", "-sL", "--fail", "-o", str(icon_path), url],
        capture_output=True)
    if result.returncode != 0:
        url = f"https://raw.githubusercontent.com/{REPO}/{tag}/.resources/wallppy.png"
        subprocess.run(
            ["curl", "-sL", "--fail", "-o", str(icon_path), url],
            capture_output=True)


def _install_desktop(prefix, binary_path):
    desktop_dir = prefix / "share" / "applications"
    desktop_dir.mkdir(parents=True, exist_ok=True)
    desktop_path = desktop_dir / "wallppy.desktop"
    desktop_path.write_text(f"""[Desktop Entry]
Name=Wallppy
GenericName=Wallpaper Manager
Comment=Download and apply desktop wallpapers
Exec={binary_path}
Icon=wallppy
Type=Application
Categories=Graphics;Utility;
Terminal=false
StartupNotify=true
""")
    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", str(desktop_dir)],
                       capture_output=True)


# ── Wayland Detection ─────────────────────────────────────────────

def is_gnome_wayland():
    session_type = os.environ.get('XDG_SESSION_TYPE', '')
    desktop = os.environ.get('XDG_CURRENT_DESKTOP', '')

    if session_type == 'wayland' and desktop == 'GNOME':
        return True

    try:
        result = subprocess.run(['loginctl', 'show-session', 'self', '-p', 'Type'],
                                capture_output=True, text=True)
        if 'Type=wayland' in result.stdout:
            if 'GNOME' in os.environ.get('XDG_CURRENT_DESKTOP', ''):
                return True
    except Exception:
        pass

    if os.environ.get('WAYLAND_DISPLAY') and 'gnome' in os.environ.get('DESKTOP_SESSION', '').lower():
        return True

    return False


# ── Argument Parser ───────────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(
        prog="wallppy",
        description="Wallppy — Linux wallpaper manager")
    parser.add_argument("-v", "--version", action="version",
                        version=f"wallppy {__version__}")

    sub = parser.add_subparsers(dest="command")

    p_update = sub.add_parser("update", help="Update to latest version")
    p_update.add_argument("version", nargs="?", default=None,
                          help="Specific tag to install (default: latest)")
    p_update.add_argument("-f", "--force", action="store_true",
                          help="Reinstall even if same version")

    p_uninstall = sub.add_parser("uninstall", help="Remove wallppy")
    p_uninstall.add_argument("-y", "--yes", action="store_true",
                             help="Skip confirmation prompt")

    sub.add_parser("clean", help="Clear API cache")
    sub.add_parser("clean-all", help="Clear all config and cache")

    return parser


# ── GUI Entry ─────────────────────────────────────────────────────

def launch_gui():
    if getattr(sys, 'frozen', False):
        system_certs = "/etc/ca-certificates/extracted/tls-ca-bundle.pem"
        if os.path.exists(system_certs):
            os.environ["REQUESTS_CA_BUNDLE"] = system_certs
            os.environ["SSL_CERT_FILE"] = system_certs
        os.environ["OPENSSL_FIPS"] = "1"

    if sys.platform.startswith('linux'):
        if is_gnome_wayland():
            os.environ['QT_QPA_PLATFORM'] = 'xcb'
            os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '0'
            os.environ['QT_SCALE_FACTOR'] = '1'

    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtGui import QIcon
    from core.settings import Settings
    from core.crash_handler import CrashHandler
    from ui.main_window import MainWindow
    import extensions

    crash = CrashHandler()
    crash.install()

    app = QApplication(sys.argv)
    app.setApplicationName("Wallppy")
    settings = Settings()
    window = MainWindow(settings)
    window.show()

    crash.show_crash_dialog_if_needed(parent=window)

    exit_code = app.exec_()
    crash.mark_clean_shutdown()
    sys.exit(exit_code)


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        launch_gui()
    elif args.command == "update":
        cmd_update(args)
    elif args.command == "uninstall":
        cmd_uninstall(args)
    elif args.command == "clean":
        cmd_clean(args)
    elif args.command == "clean-all":
        cmd_clean_all(args)
    else:
        parser.print_help()
