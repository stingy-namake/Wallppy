#!/bin/bash
# wallppy Installer Script
# Installs wallppy to the system with desktop integration

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="wallppy"
APP_VERSION="1.0.0"
APP_COMMENT="A beautiful cross-platform wallpaper manager"
INSTALL_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
CONFIG_DIR="$HOME/.config/$APP_NAME"

# Binary and resource paths (assumed to be in same directory as this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BINARY_SOURCE="$SCRIPT_DIR/$APP_NAME-linux-"*
ICON_PNG_SOURCE="$SCRIPT_DIR/.resources/cool_image.png"
ICON_ICO_SOURCE="$SCRIPT_DIR/.resources/cool_image.ico"

# ASCII art banner
show_banner() {
    echo -e "${BLUE}"
    cat << "EOF"
 _    _      _ _                           
| |  | |    | | |                          
| |  | | __| | |_ __  _ __  _   _ 
| |/\| |/ _` | | '_ \| '_ \| | | |
\  /\  / (_| | | |_) | |_) | |_| |
 \/  \/ \__,_|_| .__/| .__/ \__, |
               | |   | |     __/ |
               |_|   |_|    |___/ 
EOF
    echo -e "${NC}"
    echo -e "${GREEN}wallppy Installer v${APP_VERSION}${NC}\n"
}

# Check if running with sudo (for system-wide install)
check_sudo() {
    if [ "$EUID" -eq 0 ]; then
        INSTALL_DIR="/usr/local/bin"
        DESKTOP_DIR="/usr/share/applications"
        ICON_DIR="/usr/share/icons/hicolor/256x256/apps"
        echo -e "${YELLOW}Running as root - installing system-wide${NC}"
        return 0
    fi
    return 1
}

# Find the binary file
find_binary() {
    # Look for wallppy-linux-* binary
    BINARY=$(ls $BINARY_SOURCE 2>/dev/null | head -n1)
    
    if [ -z "$BINARY" ]; then
        echo -e "${RED}Error: Could not find wallppy binary!${NC}"
        echo "Expected pattern: $APP_NAME-linux-*"
        echo "Files in current directory:"
        ls -la "$SCRIPT_DIR" | grep -i wallppy || echo "  No wallppy files found"
        exit 1
    fi
    
    echo -e "${GREEN}Found binary: $(basename $BINARY)${NC}"
}

# Check for existing installation
check_existing() {
    if [ -f "$INSTALL_DIR/$APP_NAME" ]; then
        echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
        echo -e "${YELLOW}  Existing installation found at:${NC}"
        echo -e "${YELLOW}  $INSTALL_DIR/$APP_NAME${NC}"
        
        # Try to get version of existing install
        if [ -f "$CONFIG_DIR/version" ]; then
            EXISTING_VERSION=$(cat "$CONFIG_DIR/version" 2>/dev/null || echo "unknown")
            echo -e "${YELLOW}  Existing version: $EXISTING_VERSION${NC}"
        fi
        echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
        echo ""
        
        echo -n "Do you want to overwrite it? [Y/n] "
        read -r response
        case "$response" in
            [nN][oO]|[nN])
                echo -e "${RED}Installation cancelled${NC}"
                exit 0
                ;;
        esac
        
        # Backup existing installation
        echo -e "${BLUE}Backing up existing installation...${NC}"
        cp "$INSTALL_DIR/$APP_NAME" "$INSTALL_DIR/$APP_NAME.bak"
        echo -e "${GREEN}✓ Backup created at $INSTALL_DIR/$APP_NAME.bak${NC}"
    fi
}

# Install binary
install_binary() {
    echo -e "${BLUE}Installing binary to $INSTALL_DIR...${NC}"
    
    # Create directory if it doesn't exist
    mkdir -p "$INSTALL_DIR"
    
    # Copy binary
    cp "$BINARY" "$INSTALL_DIR/$APP_NAME"
    chmod +x "$INSTALL_DIR/$APP_NAME"
    
    # Verify installation
    if [ -x "$INSTALL_DIR/$APP_NAME" ]; then
        echo -e "${GREEN}✓ Binary installed successfully${NC}"
    else
        echo -e "${RED}✗ Failed to install binary${NC}"
        exit 1
    fi
    
    # Check if directory is in PATH
    if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
        echo -e "${YELLOW}⚠ Note: $INSTALL_DIR is not in your PATH${NC}"
        echo -e "${CYAN}  Add this to your ~/.bashrc or ~/.profile:${NC}"
        echo -e "${CYAN}  export PATH=\"\$PATH:$INSTALL_DIR\"${NC}"
        echo ""
    fi
}

# Create icon from bundled resources
create_icon() {
    echo -e "${BLUE}Creating application icon...${NC}"
    
    mkdir -p "$ICON_DIR"
    
    # Check for PNG icon first (preferred for Linux)
    if [ -f "$ICON_PNG_SOURCE" ]; then
        cp "$ICON_PNG_SOURCE" "$ICON_DIR/$APP_NAME.png"
        echo -e "${GREEN}✓ Icon installed from .resources/cool_image.png${NC}"
    elif [ -f "$ICON_ICO_SOURCE" ]; then
        # Try to convert ICO to PNG if ImageMagick is available
        if command -v convert &> /dev/null; then
            convert "$ICON_ICO_SOURCE" "$ICON_DIR/$APP_NAME.png" 2>/dev/null && {
                echo -e "${GREEN}✓ Icon converted and installed from .resources/cool_image.ico${NC}"
                return
            }
        fi
        # Fallback: just copy the ICO file
        cp "$ICON_ICO_SOURCE" "$ICON_DIR/$APP_NAME.ico"
        echo -e "${YELLOW}⚠ Installed .ico file (PNG preferred for Linux)${NC}"
    else
        echo -e "${YELLOW}⚠ No icon found in .resources/, skipping...${NC}"
        echo -e "${CYAN}  Expected: .resources/cool_image.png or .resources/cool_image.ico${NC}"
    fi
}

# Create desktop entry
create_desktop_entry() {
    echo -e "${BLUE}Creating desktop entry...${NC}"
    
    mkdir -p "$DESKTOP_DIR"
    
    # Determine icon name (prefer PNG)
    ICON_NAME="$APP_NAME"
    
    cat > "$DESKTOP_DIR/$APP_NAME.desktop" << EOF
[Desktop Entry]
Version=1.0
Name=wallppy
Comment=$APP_COMMENT
Exec=$INSTALL_DIR/$APP_NAME
Icon=$ICON_NAME
Terminal=false
Type=Application
Categories=Graphics;Utility;
Keywords=wallpaper;background;desktop;image;anime;
StartupWMClass=wallppy
StartupNotify=true
Actions=SetWallpaper;

[Desktop Action SetWallpaper]
Name=Set Wallpaper
Exec=$INSTALL_DIR/$APP_NAME --set-wallpaper
Icon=$ICON_NAME
EOF
    
    # Validate desktop entry if tool is available
    if command -v desktop-file-validate &> /dev/null; then
        desktop-file-validate "$DESKTOP_DIR/$APP_NAME.desktop" 2>/dev/null && \
            echo -e "${GREEN}✓ Desktop entry validated${NC}" || \
            echo -e "${YELLOW}⚠ Desktop entry has warnings${NC}"
    else
        echo -e "${GREEN}✓ Desktop entry created${NC}"
    fi
}

# Update desktop database and icon cache
update_desktop_database() {
    echo -e "${BLUE}Updating system databases...${NC}"
    
    # Update desktop database
    if command -v update-desktop-database &> /dev/null; then
        update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
        echo -e "${GREEN}✓ Desktop database updated${NC}"
    fi
    
    # Update icon cache
    if command -v gtk-update-icon-cache &> /dev/null; then
        gtk-update-icon-cache -f -t "$(dirname "$ICON_DIR")" 2>/dev/null || true
        echo -e "${GREEN}✓ Icon cache updated${NC}"
    fi
    
    # For KDE Plasma
    if command -v kbuildsycoca5 &> /dev/null; then
        kbuildsycoca5 2>/dev/null || true
        echo -e "${GREEN}✓ KDE menu updated${NC}"
    fi
    
    # For COSMIC (System76)
    if [ -d "$HOME/.local/share/cosmic" ] || [ -d "/usr/share/cosmic" ]; then
        echo -e "${GREEN}✓ COSMIC desktop detected - menu will update automatically${NC}"
    fi
}

# Create uninstall script
create_uninstall_script() {
    echo -e "${BLUE}Creating uninstall script...${NC}"
    
    mkdir -p "$CONFIG_DIR"
    
    cat > "$CONFIG_DIR/uninstall.sh" << EOF
#!/bin/bash
# wallppy Uninstall Script
# Generated on $(date)

set -e

APP_NAME="wallppy"
INSTALL_DIR="$INSTALL_DIR"
DESKTOP_DIR="$DESKTOP_DIR"
ICON_DIR="$ICON_DIR"
CONFIG_DIR="$CONFIG_DIR"
CACHE_DIR="$HOME/.cache/$APP_NAME"

echo -e "\033[0;34m═══════════════════════════════════════════════════════════\033[0m"
echo -e "\033[0;34m  wallppy Uninstaller\033[0m"
echo -e "\033[0;34m═══════════════════════════════════════════════════════════\033[0m"
echo ""

# Confirm uninstallation
echo -n "Are you sure you want to uninstall wallppy? [y/N] "
read -r response
if [[ ! "\$response" =~ ^[Yy] ]]; then
    echo "Uninstall cancelled."
    exit 0
fi

echo ""
echo "Removing wallppy..."

# Remove binary
if [ -f "\$INSTALL_DIR/\$APP_NAME" ]; then
    rm -f "\$INSTALL_DIR/\$APP_NAME"
    echo "✓ Removed binary"
fi

# Remove backup if exists
if [ -f "\$INSTALL_DIR/\$APP_NAME.bak" ]; then
    rm -f "\$INSTALL_DIR/\$APP_NAME.bak"
    echo "✓ Removed backup"
fi

# Remove desktop entry
if [ -f "\$DESKTOP_DIR/\$APP_NAME.desktop" ]; then
    rm -f "\$DESKTOP_DIR/\$APP_NAME.desktop"
    echo "✓ Removed desktop entry"
fi

# Remove icons
if [ -f "\$ICON_DIR/\$APP_NAME.png" ]; then
    rm -f "\$ICON_DIR/\$APP_NAME.png"
    echo "✓ Removed PNG icon"
fi
if [ -f "\$ICON_DIR/\$APP_NAME.ico" ]; then
    rm -f "\$ICON_DIR/\$APP_NAME.ico"
    echo "✓ Removed ICO icon"
fi

# Ask about config and cache
echo ""
echo -n "Remove configuration and cache? [y/N] "
read -r response
if [[ "\$response" =~ ^[Yy] ]]; then
    rm -rf "\$CONFIG_DIR"
    rm -rf "\$CACHE_DIR"
    echo "✓ Removed configuration and cache"
else
    echo "✓ Kept configuration at \$CONFIG_DIR"
    echo "✓ Kept cache at \$CACHE_DIR"
fi

# Update databases
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "\$DESKTOP_DIR" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache &> /dev/null; then
    gtk-update-icon-cache -f -t "\$(dirname "\$ICON_DIR")" 2>/dev/null || true
fi

echo ""
echo -e "\033[0;32mwallppy has been uninstalled.\033[0m"
EOF
    
    chmod +x "$CONFIG_DIR/uninstall.sh"
    echo -e "${GREEN}✓ Uninstall script created at $CONFIG_DIR/uninstall.sh${NC}"
}

# Create version file
create_version_file() {
    mkdir -p "$CONFIG_DIR"
    echo "$APP_VERSION" > "$CONFIG_DIR/version"
    echo "$(date)" > "$CONFIG_DIR/install_date"
    echo -e "${GREEN}✓ Installation recorded${NC}"
}

# Check for updates
check_for_updates() {
    echo -e "${BLUE}Checking for updates...${NC}"
    
    # This is a placeholder - you can implement actual update checking
    # by fetching from GitHub releases API
    
    echo -e "${CYAN}  To check for updates, visit:${NC}"
    echo -e "${CYAN}  https://github.com/stingy-namake/wallppy/releases${NC}"
}

# Show success message
show_success() {
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✓ wallppy has been successfully installed!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${BLUE}Binary:${NC}     $INSTALL_DIR/$APP_NAME"
    echo -e "  ${BLUE}Desktop:${NC}    $DESKTOP_DIR/$APP_NAME.desktop"
    echo -e "  ${BLUE}Icon:${NC}       $ICON_DIR/$APP_NAME.png"
    echo -e "  ${BLUE}Config:${NC}     $CONFIG_DIR"
    echo -e "  ${BLUE}Cache:${NC}      $HOME/.cache/$APP_NAME"
    echo ""
    echo -e "  ${YELLOW}To uninstall:${NC}"
    echo -e "  ${CYAN}$CONFIG_DIR/uninstall.sh${NC}"
    echo ""
    echo -e "  ${GREEN}You can now launch wallppy from your application menu${NC}"
    echo -e "  ${GREEN}or by running: ${CYAN}$APP_NAME${NC}"
    echo ""
    
    # Remind about PATH if needed
    if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
        echo -e "  ${YELLOW}⚠ Remember to add $INSTALL_DIR to your PATH:${NC}"
        echo -e "  ${CYAN}echo 'export PATH=\"\$PATH:$INSTALL_DIR\"' >> ~/.bashrc${NC}"
        echo -e "  ${CYAN}source ~/.bashrc${NC}"
        echo ""
    fi
    
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
}

# Main installation flow
main() {
    show_banner
    
    # Check for sudo (system-wide vs user install)
    check_sudo
    
    # Find the binary
    find_binary
    
    # Check for existing installation
    check_existing
    
    # Create directories
    echo -e "\n${BLUE}Creating directories...${NC}"
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$CONFIG_DIR"
    mkdir -p "$HOME/.cache/$APP_NAME"
    echo -e "${GREEN}✓ Directories created${NC}"
    
    echo ""
    
    # Install components
    install_binary
    create_icon
    create_desktop_entry
    create_uninstall_script
    create_version_file
    
    echo ""
    
    # Update desktop database
    update_desktop_database
    
    echo ""
    
    # Check for updates
    check_for_updates
    
    # Show success
    show_success
}

# Run main function
main "$@"