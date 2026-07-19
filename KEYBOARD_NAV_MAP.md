# Keyboard Navigation Map — Wallppy

## User Workflows (Keyboard Paths)

### 1. Search & Set Wallpaper (Primary Flow)
```
App Start
  ↓
[Focus: Search Bar] — auto-focus on launch
  ↓
Type query → "mountains"
  ↓
Enter ──────────────────────── → Results Page
  ↓
[results_page.start_search()]
  ↓
[rebuild_grid() — wallpapers added]
  ↓
[QTimer.singleShot(50, focus_first_wallpaper)]
  ↓
[Focus: First wallpaper in grid — focus ring visible]
  ↓
Arrow keys / j/k/h/l ──────── → Navigate grid
  ↓
  ├─ Space ────────────────── → Preview (ImageOverlay)
  │     ↓
  │   Escape ──────────────── → Close preview, back to grid
  │
  ├─ Enter ────────────────── → Set as wallpaper
  │
  ├─ Ctrl+D ───────────────── → Download
  │
  ├─ Ctrl+K ───────────────── → Jump back to search bar
  │
  └─ Tab ──────────────────── → Move to next zone (filters → actions → ...)
```

**Focus transition detail:**
- After `on_search_finished()` → `rebuild_grid()` populates grid
- `QTimer.singleShot(50, self._focus_first_wallpaper)` — short delay for render
- `_focus_first_wallpaper()`:
  - If grid has items: `self.grid_layout.itemAt(0).widget().setFocus()`
  - If grid empty: focus stays on search bar
  - Sets `self._focused_index = (0, 0)` (row, col)

### 2. Explore Recent (No Query)
```
Landing Page
  ↓
Tab → "explore content →" link
  ↓
Enter ──────────────────────── → Results Page (recent uploads)
  ↓
[Grid navigation same as above]
```

### 3. Change Wallpaper Source
```
Landing Page
  ↓
Tab → Source Dropdown
  ↓
↑/↓ ───────────────────────── → Select source
  ↓
Enter ──────────────────────── → Confirm selection
  ↓
Tab → Search Bar
```

### 4. Refine Search with Filters
```
Results Page
  ↓
Ctrl+F ─────────────────────── → Toggle filter panel
  ↓
Tab → Filter controls
  ↓
Space ──────────────────────── → Toggle checkboxes
  ↓
Tab → "Apply Filters" button
  ↓
Enter ──────────────────────── → Apply & reload results
```

### 5. Download Workflow
```
Results Page [Grid focused]
  ↓
Navigate to target wallpaper (arrows/jkhl)
  ↓
  ├─ Double-click ─────────── → Download (mouse, existing)
  ├─ Ctrl+D ───────────────── → Download (keyboard)
  └─ Enter ────────────────── → Set wallpaper (auto-downloads if needed)
```

### 6. Quick Search from Results
```
Results Page
  ↓
Ctrl+K ─────────────────────── → Focus search bar
  ↓
Type new query → Enter
  ↓
[Results reload, focus returns to grid]
```

### 7. Return Home
```
Results Page
  ↓
  ├─ Home key ─────────────── → Go to Landing Page
  └─ Ctrl+N ───────────────── → Go to Landing Page + focus search
```

### 8. Change Download Location
```
Landing Page
  ↓
Tab → "Change" button
  ↓
Enter ──────────────────────── → QFileDialog opens
  ↓
Navigate dialog → Select folder → Enter
```

---

## Contextual Hint Display

### Landing Page Hints
| Element | Hint Shown | Style |
|---------|-----------|-------|
| Search bar | `Search wallpapers... [(Enter)]` | Inline right-aligned |
| Source dropdown | `Source [(↑↓ select)]` | Below label |
| "explore content →" | `Explore recent [(Tab + Enter)]` | Inline after text |
| "Change" button | `Change folder [(Enter)]` | Tooltip on hover |
| Clear cache | `Clear cache [(Enter)]` | Tooltip on hover |

### Results Page Hints
| Element | Hint Shown | Style |
|---------|-----------|-------|
| Search bar | `Search... [(Ctrl+K)]` | Inline when not focused |
| Filters button | `Filters [(Ctrl+F)]` | Inline after label |
| Grid (when focused) | `Navigate [(↑↓←→ jkhl)]` | Status bar message |
| Wallpaper hover | `[(Space) preview  [(Enter) set  [(Ctrl+D) download]` | Overlay on thumbnail |
| Scroll-to-top | `Top [(Home)]` | Tooltip on hover |

### Global Overlay Hints
| Shortcut | Label |
|----------|-------|
| `Ctrl+/` | Show all shortcuts overlay |

---

## Complete Shortcut Reference

### Global (work everywhere)
| Shortcut | Action | Context |
|----------|--------|---------|
| `Ctrl+K` | Focus search bar | Any page |
| `Ctrl+N` | Go home + focus search | Any page |
| `Ctrl+S` | Cycle wallpaper source | Any page |
| `Ctrl+L` | Jump to Local source | Any page |
| `Ctrl+D` | Download focused wallpaper | Results grid |
| `Ctrl+Enter` | Set focused wallpaper as background | Results grid |
| `Ctrl+F` | Toggle filter panel | Results page |
| `Ctrl+/` | Show shortcuts overlay | Any page |
| `Escape` | Close overlay / cancel action | Context-dependent |
| `Home` | Scroll to top / go home | Results / Landing |

### Grid Navigation (Results page)
| Key | Action |
|-----|--------|
| `↑` / `k` | Move focus up |
| `↓` / `j` | Move focus down |
| `←` / `h` | Move focus left |
| `→` / `l` | Move focus right |
| `Enter` | Set as wallpaper |
| `Space` | Expand/preview |
| `Delete` | Delete downloaded file (if downloaded) |

**Edge behavior: Wrap around rows**
- `→` at last item in row → first item of next row
- `↓` at last row → stays at same column in last row
- `←` at first item in row → last item of previous row
- `↑` at first row → stays at same column in first row

**Focus tracking:**
- `self._focused_wallpaper: WallpaperWidget | None` — currently focused widget
- `self._focused_index: tuple[int, int]` — (row, col) in grid
- `self.grid_rows: int` — current row count
- `self.grid_cols: int` — current column count (responsive to window width)
- On window resize: recalculate `grid_cols`, adjust `_focused_index` to keep same wallpaper

### Tab Order (Landing Page)
1. Source dropdown
2. Clear cache button
3. Search bar
4. Search button
5. "explore content →" link
6. "Change" download folder button

### Tab Order (Results Page)
1. Home button
2. Search bar
3. Search button
4. Filters button
5. Filter panel (when open)
   - Filter controls...
   - "Apply Filters" button
6. Grid — each WallpaperWidget is one Tab stop (children are NoFocus)
7. Scroll-to-top button

---

## Visual Focus Indicators

### Focus Ring Style
- **Grid items**: 2px solid accent-color border, subtle glow (`box-shadow: 0 0 8px accent`)
- **Buttons**: Outline offset 2px, accent color
- **Search bar**: Accent border color change
- **Dropdown**: Accent border + background tint
- **Focused wallpaper**: Yellow/amber ring (distinct from hover state)

### Focus States
| State | Visual | Trigger |
|-------|--------|---------|
| No focus | No ring | App start, all elements unfocused |
| Search focused | Accent border | Tab or Ctrl+K |
| Grid item focused | 2px accent ring + glow | Arrow key nav, Tab, or auto-focus after search |
| Button focused | Outline ring | Tab navigation |
| Overlay open | No grid focus | Space pressed (preview) |

### Keyboard Hint Badge
```
┌─────────────────────────────┐
│  Search wallpapers...  [⏎]  │  ← rounded pill, muted bg
└─────────────────────────────┘

┌─────────────────────────────┐
│  Filters  [Ctrl+F]          │
└─────────────────────────────┘
```
Badge style: `border-radius: 4px`, `bg: rgba(128,128,128,0.15)`, `font-size: 0.75em`, `padding: 2px 6px`

### Wallpaper Hover/Focus Overlay
When wallpaper has focus or hover, show action badges:
```
┌────────────────────────┐
│  [thumbnail image]     │
│                        │
│  ⏎ set   ␣ preview    │  ← badges at bottom
│  Ctrl+D download       │
└────────────────────────┘
```

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Grid empty (no results) | Tab skips grid zone, goes to scroll-to-top/home |
| Filter panel open | Tab order includes filter controls |
| ImageOverlay open | Only Escape works; all other shortcuts disabled |
| Search bar focused | Enter = search, Escape = unfocus (return to grid on results page) |
| No wallpaper focused in grid | Ctrl+D / Ctrl+Enter / Enter do nothing (no-op) |
| Download in progress | Status bar shows progress; keyboard still responsive |
