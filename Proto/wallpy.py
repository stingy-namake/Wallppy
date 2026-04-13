#!/usr/bin/env python3
# wallhaven_terminal.py
# Simple script to search and download wallpapers from Wallhaven

import requests
import os
import sys

# =============================================================================
# STEP 1: CONFIGURATION (Things you can change)
# =============================================================================

# API address. This is where we ask for wallpapers
API_URL = "https://wallhaven.cc/api/v1/search"

# Folder where we save pictures. ./ means "same folder as script"
DOWNLOAD_FOLDER = "./wallpapers"

# Create download folder if not exist. If folder no exist, make it.
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)
    print(f"Cave make folder: {DOWNLOAD_FOLDER}")

# =============================================================================
# STEP 2: FUNCTION TO SEARCH WALLPAPERS
# =============================================================================

def search_wallpapers(query="", category="111", purity="100", page=1):
    """
    Ask Wallhaven for wallpapers.
    
    query = what to search (like "nature", "car", "space")
    category = 111 means General + Anime + People (1=on, 0=off)
    purity = 100 means only SFW (Safe For Work). 110 = SFW+Sketchy. 111 = all
    page = which page of results (24 wallpapers per page)
    """
    
    # Build the request URL with parameters
    params = {
        "q": query,           # Search words
        "categories": category,  # What types (General/Anime/People)
        "purity": purity,     # SFW filter
        "page": page,         # Page number
        "sorting": "date_added",  # Show newest first
        "order": "desc"
    }
    
    print(f"\nCaveman searching for: '{query}'...")
    
    try:
        # Send request to internet
        response = requests.get(API_URL, params=params, timeout=10)
        
        # Check if internet angry (status code not 200)
        if response.status_code != 200:
            print(f"Internet angry! Code: {response.status_code}")
            return []
        
        # Parse JSON (JSON is text that computer understand like dictionary)
        data = response.json()
        
        # Return list of wallpapers
        return data.get("data", [])
        
    except Exception as e:
        print(f"Something broke: {e}")
        return []

# =============================================================================
# STEP 3: FUNCTION TO SHOW WALLPAPERS IN TERMINAL
# =============================================================================

def show_wallpapers(wallpapers):
    """
    Show list of wallpapers as numbered list in terminal.
    Terminal cannot show real pictures (unless use special magic),
    so we show text info: number, resolution, file type.
    """
    
    if not wallpapers:
        print("No wallpapers found. Search different word.")
        return
    
    print("\n" + "="*60)
    print("WALLPAPERS FOUND (pick number to download)")
    print("="*60)
    
    for index, wall in enumerate(wallpapers, 1):
        # Get info from wallpaper data
        wall_id = wall.get("id", "unknown")
        resolution = wall.get("resolution", "unknown")
        file_type = wall.get("file_type", "unknown")
        purity = wall.get("purity", "unknown")
        category = wall.get("category", "unknown")
        
        # Print line like: [1] 1920x1080 - image/jpeg (SFW)
        print(f"[{index:2}] {resolution:>10} | {purity:^6} | {category:<8} | ID:{wall_id}")

    print("="*60)
    print(f"Total: {len(wallpapers)} wallpapers")
    print("Type number to download, 'n' for next page, 'q' to quit")

# =============================================================================
# STEP 4: FUNCTION TO DOWNLOAD ONE WALLPAPER
# =============================================================================

def download_wallpaper(wallpaper_data):
    """
    Download actual image file from internet to computer.
    wallpaper_data = dictionary with info about one wallpaper
    """
    
    # Get direct link to full image
    image_url = wallpaper_data.get("path")
    wall_id = wallpaper_data.get("id")
    file_type = wallpaper_data.get("file_type", "image/jpeg")
    
    if not image_url:
        print("No image URL found!")
        return False
    
    # Figure out file extension (.jpg or .png)
    if "jpeg" in file_type or "jpg" in file_type:
        ext = "jpg"
    elif "png" in file_type:
        ext = "png"
    else:
        ext = "jpg"  # Default guess
    
    # Make filename like: wallpapers/wallhaven-abc123.jpg
    filename = f"wallhaven-{wall_id}.{ext}"
    filepath = os.path.join(DOWNLOAD_FOLDER, filename)
    
    # Check if already have this file (no download twice)
    if os.path.exists(filepath):
        print(f"Already have {filename}, skip download.")
        return True
    
    print(f"\nDownloading {filename}...")
    print(f"From: {image_url}")
    
    try:
        # Download actual image bytes
        response = requests.get(image_url, stream=True, timeout=30)
        response.raise_for_status()  # Check for errors
        
        # Save to file in chunks (good for big files)
        with open(filepath, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file.write(chunk)
        
        print(f"Success! Saved to: {filepath}")
        
        # Show file size
        file_size = os.path.getsize(filepath) / 1024  # KB
        print(f"Size: {file_size:.1f} KB")
        
        return True
        
    except Exception as e:
        print(f"Download fail: {e}")
        return False

# =============================================================================
# STEP 5: MAIN MENU LOOP (Brain of program)
# =============================================================================

def main():
    """
    Main loop. Show menu, get user input, do what user want.
    Keep running until user say quit.
    """
    
    current_page = 1
    current_query = ""
    current_wallpapers = []
    
    print("\n" + "="*60)
    print("WALLHAVEN TERMINAL WALLPAPER DOWNLOADER")
    print("Caveman Style - Simple and Strong")
    print("="*60)
    print("Commands:")
    print("  s <word>  = Search (example: s nature)")
    print("  n         = Next page")
    print("  p         = Previous page")
    print("  <number>  = Download wallpaper by number (example: 5)")
    print("  q         = Quit")
    print("="*60)
    
    while True:
        # Get command from user
        try:
            user_input = input("\nCaveman command> ").strip().lower()
        except KeyboardInterrupt:
            print("\nBye bye!")
            break
        
        if not user_input:
            continue
        
        # QUIT COMMAND
        if user_input == 'q':
            print("Caveman go sleep now. Goodbye!")
            break
        
        # SEARCH COMMAND (user type 's' then word)
        elif user_input.startswith('s '):
            current_query = user_input[2:].strip()
            current_page = 1
            current_wallpapers = search_wallpapers(current_query, page=current_page)
            show_wallpapers(current_wallpapers)
        
        # NEXT PAGE
        elif user_input == 'n':
            if not current_wallpapers:
                print("Search something first! (type: s nature)")
                continue
            current_page += 1
            current_wallpapers = search_wallpapers(current_query, page=current_page)
            show_wallpapers(current_wallpapers)
        
        # PREVIOUS PAGE
        elif user_input == 'p':
            if current_page > 1:
                current_page -= 1
                current_wallpapers = search_wallpapers(current_query, page=current_page)
                show_wallpapers(current_wallpapers)
            else:
                print("Already on first page!")
        
        # DOWNLOAD BY NUMBER
        elif user_input.isdigit():
            number = int(user_input)
            if 1 <= number <= len(current_wallpapers):
                selected = current_wallpapers[number - 1]  # -1 because list start at 0
                download_wallpaper(selected)
            else:
                print(f"Number {number} not in list. Choose 1 to {len(current_wallpapers)}")
        
        # UNKNOWN COMMAND
        else:
            print("Caveman not understand. Try: s nature, n, p, 1, q")

# =============================================================================
# STEP 6: START PROGRAM
# =============================================================================

if __name__ == "__main__":
    # Check if requests library installed
    try:
        import requests
    except ImportError:
        print("ERROR: Need 'requests' library!")
        print("Install with: pip install requests")
        sys.exit(1)
    
   # Run main function
    main()