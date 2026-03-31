# Gallery Template Selection — Design Document

## Overview

Allow creators to choose from multiple gallery templates when publishing
content. Each template is a Jinja2 HTML file in `/templates/` with a
distinct visual style suited to different content types.

## Current State

- Single template: `templates/gallery.html` (card-based grid layout)
- Hardcoded in `render_gallery_html()` at line 239: `get_template("gallery.html")`
- Template receives: `data_pod`, `colors`, `ipfs_gateway`, `gallery_title`,
  `gallery_description`, `is_dark_mode`

## Proposed Templates

### 1. `gallery.html` — Default (Existing)
- **Style**: Card grid with gradient background
- **Best for**: Mixed media galleries, portfolios
- **Features**: Audio player, video controls, markdown collapse, media badges

### 2. `gallery_album.html` — Music/Audio Focused
- **Inspired by**: Spotify, Bandcamp
- **Style**: Dark background, large hero image (first item), tracklist layout
  below. Audio items displayed as a vertical track list with play buttons,
  duration, and waveform-style progress bars. Non-audio images shown as
  album art in a secondary grid.
- **Best for**: Music albums, audiobooks, podcast collections
- **Layout**:
  ```
  ┌─────────────────────────────────────────┐
  │           ┌──────────┐                  │
  │           │          │  Album Title     │
  │           │  Cover   │  Artist Name     │
  │           │  Art     │  12 tracks       │
  │           │          │  2026            │
  │           └──────────┘                  │
  ├─────────────────────────────────────────┤
  │  1  Track Title           ▶  3:42      │
  │  2  Another Track         ▶  4:15      │
  │  3  Third Song            ▶  2:58      │
  │  ...                                    │
  └─────────────────────────────────────────┘
  ```

### 3. `gallery_artstation.html` — Visual Art Focused
- **Inspired by**: ArtStation, Behance, DeviantArt
- **Style**: Clean white/dark background, images displayed large with
  generous spacing. Masonry or single-column layout. Focus on image
  quality with minimal UI chrome. Metadata shown on hover or below
  in muted typography.
- **Best for**: Illustrations, concept art, photography, graphic novels
- **Layout**:
  ```
  ┌─────────────────────────────────────────┐
  │  Gallery Title                          │
  │  by Artist Name                         │
  ├─────────────────────────────────────────┤
  │                                         │
  │  ┌─────────────────────────────────┐    │
  │  │                                 │    │
  │  │         Full-width Image        │    │
  │  │                                 │    │
  │  └─────────────────────────────────┘    │
  │  Title — 1920x1080                      │
  │                                         │
  │  ┌─────────────────────────────────┐    │
  │  │                                 │    │
  │  │         Full-width Image        │    │
  │  │                                 │    │
  │  └─────────────────────────────────┘    │
  │  Title — 2560x1440                      │
  │                                         │
  └─────────────────────────────────────────┘
  ```

### 4. `gallery_book.html` — Publication / Reading Focused
- **Inspired by**: Medium, Substack, e-readers
- **Style**: Serif typography, narrow reading column, images inline with
  text. Markdown/text content is primary, images are supporting. Clean
  page-like feel with ample line height and margins.
- **Best for**: Graphic novels with text, illustrated stories, photo essays
- **Layout**:
  ```
  ┌─────────────────────────────────────────┐
  │          Publication Title               │
  │          by Author Name                  │
  │          March 30, 2026                  │
  ├─────────────────────────────────────────┤
  │                                         │
  │  ┌───────────────────────────┐          │
  │  │       Cover Image         │          │
  │  └───────────────────────────┘          │
  │                                         │
  │  Chapter text flows here in a narrow    │
  │  reading column with serif font and     │
  │  generous line height...                │
  │                                         │
  │  ┌───────────────────────────┐          │
  │  │     Inline Illustration    │          │
  │  └───────────────────────────┘          │
  │                                         │
  │  More text continues below the image... │
  │                                         │
  └─────────────────────────────────────────┘
  ```

## Template Contract

All templates receive the same Jinja2 context and must handle the same
data structures. This is the shared contract:

```python
template_context = {
    "data_pod": {
        "uri": str,
        "items": [
            {
                "headline": str,
                "description_text": str,
                "renditions": [{"href": str, "mimetype": str, ...}],
                "imageType": str,  # "raw", "processed", "aposematic", "enciphered"
                "hasAudio": bool,
                "hasVideo": bool,
                "hasMarkdown": bool,
                "audio": {"data": str, "format": str, ...},  # if hasAudio
                "video": {...},                                # if hasVideo
                "markdown": {"files": [{"filename": str, "text_html": str}]},
            }
        ],
        "creator_public_key": str,
        "content_type": str,
        "type_distribution": dict,
    },
    "ipfs_gateway": str,        # e.g., "http://localhost:8081"
    "gallery_title": str,       # User-set title
    "gallery_description": str, # User-set description
    "colors": {                 # Theme colors (light or dark)
        "primary": str,
        "secondary": str,
        "text": str,
        "bg": str,
        "card": str,
        "border": str,
    },
    "is_dark_mode": bool,
}
```

Templates should:
- Handle missing/empty fields gracefully
- Support both light and dark mode via `colors` and `is_dark_mode`
- Use the collapsible `<details>` pattern for markdown content
- Include audio player UI if any item has `hasAudio`
- Include video player UI if any item has `hasVideo`
- Be fully self-contained (inline CSS, no external dependencies)

## Template Registry

Templates are registered in a Python dict for the dropdown:

```python
GALLERY_TEMPLATES = {
    "gallery.html": {
        "name": "Default",
        "description": "Card grid with gradient background",
        "icon": "grid_view",
    },
    "gallery_album.html": {
        "name": "Album",
        "description": "Music-focused tracklist layout",
        "icon": "album",
    },
    "gallery_artstation.html": {
        "name": "Showcase",
        "description": "Full-width art showcase",
        "icon": "palette",
    },
    "gallery_book.html": {
        "name": "Publication",
        "description": "Reading-focused layout with serif typography",
        "icon": "menu_book",
    },
}
```

## UI Changes

### Gallery Information Dialog

Add a template dropdown to the existing `gallery_info_dialog()` in
`dialogs.py`:

```
┌───────────────────────────────────────┐
│ Gallery Information                   │
│                                       │
│ Gallery Title:                        │
│ [My Art Collection              ]     │
│                                       │
│ Gallery Description:                  │
│ [A collection of digital art    ]     │
│ [from 2026...                   ]     │
│                                       │
│ Template:                             │
│ [Default ▼                      ]     │
│   ├ Default — Card grid               │
│   ├ Album — Music tracklist           │
│   ├ Showcase — Full-width art         │
│   └ Publication — Reading layout      │
│                                       │
│                  [Cancel] [Save]       │
└───────────────────────────────────────┘
```

Selected template stored in `app.storage.user["gallery_template"]`
(default: `"gallery.html"`).

### render_gallery_html Changes

```python
def render_gallery_html(data_pod: dict) -> str:
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    jinja_env = Environment(loader=FileSystemLoader(template_dir))

    # Use selected template, fallback to default
    template_name = app.storage.user.get("gallery_template", "gallery.html")
    template = jinja_env.get_template(template_name)

    # ... rest unchanged
```

## Implementation Steps

### Phase 1: Template Selection Infrastructure
- Add `GALLERY_TEMPLATES` registry to `main.py`
- Update `render_gallery_html()` to use selected template
- Add template dropdown to `gallery_info_dialog()`
- Persist selection in `app.storage.user["gallery_template"]`

### Phase 2: Album Template
- Create `templates/gallery_album.html`
- Hero cover art from first image
- Track list layout for audio items
- Dark theme by default
- Waveform-style audio progress bars

### Phase 3: Showcase Template
- Create `templates/gallery_artstation.html`
- Full-width images, single column
- Minimal chrome, focus on image quality
- Hover metadata reveal
- Masonry option for mixed aspect ratios

### Phase 4: Publication Template
- Create `templates/gallery_book.html`
- Narrow reading column, serif typography
- Inline images between text blocks
- Chapter-like navigation for multi-item pods
- Print-friendly styling

## Design Principles

- **Self-contained**: Each template is one HTML file with inline CSS.
  No external stylesheets, fonts loaded from CDN only if needed.
- **Same data, different presentation**: Templates don't change what
  data is available, only how it's displayed.
- **Dark/light aware**: All templates must respect the `colors` and
  `is_dark_mode` context variables.
- **Progressive enhancement**: If a template is designed for audio
  content but receives images-only, it should still render sensibly.
- **Mobile responsive**: All templates should work on mobile viewports
  (the gallery may be shared as a standalone HTML page).
