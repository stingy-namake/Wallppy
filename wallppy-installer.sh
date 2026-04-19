#!/usr/bin/env bash
set -euo pipefail

REPO="stingy-namake/Wallppy"
BINARY_NAME="wallppy"
DESKTOP_FILE_NAME="wallppy.desktop"
VERSION=""
INSTALL_PREFIX="${HOME}/.local"
SYSTEM=false
LOCAL_MODE=false

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Install Wallppy wallpaper manager.

OPTIONS:
    --system          Install system-wide to /usr/local (requires sudo)
    --prefix PATH     Install to custom prefix (default: ~/.local)
    --version TAG     Install specific version (default: latest)
    --local           Install from local directory (for bundled releases)
    -h, --help        Show this help message
EOF
    exit 0
}

log_info() { echo -e "${GREEN}[*]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[!]${NC} $1"; }
log_error() { echo -e "${RED}[x]${NC} $1"; }

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --system)
                SYSTEM=true
                INSTALL_PREFIX="/usr/local"
                shift
                ;;
            --prefix)
                INSTALL_PREFIX="$2"
                shift 2
                ;;
            --version)
                VERSION="$2"
                shift 2
                ;;
            --local)
                LOCAL_MODE=true
                shift
                ;;
            -h|--help)
                usage
                ;;
            *)
                log_error "Unknown option: $1"
                usage
                ;;
        esac
    done
}

detect_arch() {
    local arch
    arch=$(uname -m)
    case "$arch" in
        x86_64|amd64)
            echo "x86_64"
            ;;
        aarch64|arm64)
            echo "arm64"
            ;;
        *)
            log_error "Unsupported architecture: $arch"
            exit 1
            ;;
    esac
}

get_latest_version() {
    local api_url="https://api.github.com/repos/${REPO}/releases/latest"
    local tag
    tag=$(curl -sL --fail "$api_url" | grep -oP '"tag_name": "\K[^"]+' || true)
    if [[ -z "$tag" ]]; then
        log_error "Failed to fetch latest version from GitHub"
        exit 1
    fi
    echo "$tag"
}

find_local_binary() {
    # Look for binary in current directory and common patterns
    local candidates=("wallppy-linux-"* "wallppy" "dist/wallppy" "dist/wallppy-linux-"*)
    for candidate in "${candidates[@]}"; do
        if [[ -f "$candidate" && -x "$candidate" ]]; then
            echo "$candidate"
            return 0
        fi
    done
    return 1
}

download_release() {
    local tag="$1"
    local arch="$2"
    local tmp_dir="$3"
    
    local api_url="https://api.github.com/repos/${REPO}/releases/tags/${tag}"
    local asset_name
    
    # Try to find exact asset name from release
    asset_name=$(curl -sL --fail "$api_url" | grep -oP '"name": "\Kwallppy-linux-[^"]+' | head -1 || true)
    
    # Fallback to pattern
    if [[ -z "$asset_name" ]]; then
        asset_name="wallppy-linux-${tag}"
    fi
    
    local download_url="https://github.com/${REPO}/releases/download/${tag}/${asset_name}"
    
    log_info "Downloading ${asset_name}..."
    if ! curl -sL --fail -o "${tmp_dir}/wallppy-binary" "$download_url"; then
        log_error "Failed to download binary from ${download_url}"
        log_error "Make sure the release exists and the binary was uploaded."
        exit 1
    fi
    
    chmod +x "${tmp_dir}/wallppy-binary"
    
    # Download icon from repo raw content for this tag
    local icon_url="https://raw.githubusercontent.com/${REPO}/${tag}/.resources/cool_image.png"
    log_info "Downloading icon..."
    if ! curl -sL --fail -o "${tmp_dir}/wallppy.png" "$icon_url"; then
        # Try alternate path
        icon_url="https://raw.githubusercontent.com/${REPO}/${tag}/.resources/wallppy.png"
        curl -sL --fail -o "${tmp_dir}/wallppy.png" "$icon_url" || true
    fi
}

install_files() {
    local tmp_dir="$1"
    local binary_source="$2"
    
    local bin_dir="${INSTALL_PREFIX}/bin"
    local icon_dir="${INSTALL_PREFIX}/share/icons/hicolor/256x256/apps"
    local desktop_dir="${INSTALL_PREFIX}/share/applications"
    local hicolor_dir="${INSTALL_PREFIX}/share/icons/hicolor"
    
    # Create directories
    mkdir -p "$bin_dir" "$icon_dir" "$desktop_dir"
    
    # Install binary
    cp "$binary_source" "${bin_dir}/${BINARY_NAME}"
    chmod +x "${bin_dir}/${BINARY_NAME}"
    log_info "Installed binary to ${bin_dir}/${BINARY_NAME}"
    
    # Install icon
    local icon_source=""
    if [[ -f "${tmp_dir}/wallppy.png" ]]; then
        icon_source="${tmp_dir}/wallppy.png"
    elif [[ -f ".resources/cool_image.png" ]]; then
        icon_source=".resources/cool_image.png"
    elif [[ -f ".resources/wallppy.png" ]]; then
        icon_source=".resources/wallppy.png"
    fi
    
    if [[ -n "$icon_source" ]]; then
        cp "$icon_source" "${icon_dir}/${BINARY_NAME}.png"
        log_info "Installed icon to ${icon_dir}"
    else
        log_warn "No icon found, skipping icon installation"
    fi
    
    # Create .desktop entry
    cat > "${desktop_dir}/${DESKTOP_FILE_NAME}" << EOF
[Desktop Entry]
Name=Wallppy
GenericName=Wallpaper Manager
Comment=Download and apply desktop wallpapers
Exec=${bin_dir}/${BINARY_NAME}
Icon=${BINARY_NAME}
Type=Application
Categories=Graphics;Utility;
Terminal=false
StartupNotify=true
EOF
    
    log_info "Installed desktop entry to ${desktop_dir}"
    
    # Update desktop database and icon cache
    if command -v update-desktop-database &> /dev/null; then
        update-desktop-database "$desktop_dir" 2>/dev/null || true
    fi
    
    if command -v gtk-update-icon-cache &> /dev/null; then
        gtk-update-icon-cache -f -t "$hicolor_dir" 2>/dev/null || true
    fi
}

check_dependencies() {
    local deps=("curl")
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            log_error "Required dependency not found: $dep"
            exit 1
        fi
    done
}

main() {
    parse_args "$@"
    check_dependencies
    
    local arch
    arch=$(detect_arch)
    
    # Determine version
    if [[ -z "$VERSION" ]]; then
        VERSION=$(get_latest_version)
    fi
    log_info "Installing Wallppy ${VERSION} (${arch})"
    
    local tmp_dir
    tmp_dir=$(mktemp -d)
    trap 'rm -rf "$tmp_dir"' EXIT
    
    local binary_source=""
    
    if [[ "$LOCAL_MODE" == true ]]; then
        log_info "Local mode: installing from current directory"
        binary_source=$(find_local_binary) || {
            log_error "Could not find local binary. Make sure you're running this from the extracted release directory."
            exit 1
        }
        
        # Copy local icon to tmp if present
        if [[ -f ".resources/cool_image.png" ]]; then
            cp ".resources/cool_image.png" "${tmp_dir}/wallppy.png"
        elif [[ -f ".resources/wallppy.png" ]]; then
            cp ".resources/wallppy.png" "${tmp_dir}/wallppy.png"
        fi
    else
        log_info "Downloading from GitHub releases..."
        download_release "$VERSION" "$arch" "$tmp_dir"
        binary_source="${tmp_dir}/wallppy-binary"
    fi
    
    # Check if we need sudo for system install
    if [[ "$SYSTEM" == true ]]; then
        if [[ $EUID -ne 0 ]]; then
            log_error "System install requires root. Run with sudo or as root."
            exit 1
        fi
    fi
    
    install_files "$tmp_dir" "$binary_source"
    
    echo ""
    log_info "Installation complete!"
    echo ""
    echo "  Binary: ${INSTALL_PREFIX}/bin/${BINARY_NAME}"
    echo "  Desktop entry: ${INSTALL_PREFIX}/share/applications/${DESKTOP_FILE_NAME}"
    echo ""
    
    if [[ "$SYSTEM" == false ]]; then
        if [[ ":$PATH:" != *":${INSTALL_PREFIX}/bin:"* ]]; then
            log_warn "${INSTALL_PREFIX}/bin is not in your PATH"
            echo "  Add this to your ~/.bashrc or ~/.zshrc:"
            echo "    export PATH=\"${INSTALL_PREFIX}/bin:\$PATH\""
            echo ""
        fi
    fi
    
    echo "Run '${BINARY_NAME}' to start the application."
    echo "Or find it in your application menu as 'Wallppy'."
}

main "$@"