# ashwin-conrad.github.io
Ashwin Conrad's Github Portfolio Website

## Repository layout

- `content/` - editable site, resume, gallery, and project source data.
- `content/context/` - supporting notes used while maintaining content.
- `assets/photos/` - optimized images referenced by the site.
- `assets/brand/` - brand references and visual assets.
- `scripts/` - build and content-editing tools; shared paths live in `project_paths.py`.
- `index.html`, `styles.css`, and `portfolio/resume.pdf` - generated GitHub Pages output.
- `tmp/` - local-only previews, downloads, and cloned reference repositories.

## Editing workflow

Edit structure, navigation, and resume high-level details in `content/site.json`. Edit longer website descriptions, tags, image captions, gallery groups, and related links in `content/details.json`. Then rebuild the generated files:

```powershell
python scripts/build_site.py
```

The script regenerates `index.html`, `styles.css`, and `portfolio/resume.pdf`. The resume block in `content/site.json` is the source of truth for roles, organizations, locations, and dates. Experience and project cards reference those resume items with `resume_id`, so the website mirrors the resume automatically.

## Shared resume and site links

Use stable IDs to connect resume entries, work cards, and project cards:

```json
{
  "id": "altagas-coop",
  "resume_id": "altagas-coop"
}
```

Longer body copy lives in `content/details.json` under the same ID:

```json
{
  "experience": {
    "altagas-coop": {
      "description": "Longer website copy...",
      "related": [
        {
          "label": "Corrosion Monitoring Dashboard",
          "href": "#project-corrosion-monitoring-dashboard"
        }
      ]
    }
  }
}
```

Resume bullets stay in the resume block and can be filled in later per organization or project.

## Photos

Keep original uploads in `assets/` if you want the source files preserved. The website should reference optimized copies in `assets/photos/` so the page stays fast.

Project cards support an optional image:

```json
"image": {
  "src": "assets/photos/project-photo.jpg",
  "alt": "Short description of the project photo"
}
```

The grouped gallery is defined in `content/details.json` under `photos.groups`:

```json
{
  "heading": "Spartan Controls: Panels + Shop Systems",
  "intro": "A short group overview.",
  "items": [
    {
      "src": "assets/photos/spartan-panel-1.jpg",
      "alt": "Open electrical control panel",
      "title": "Panel Build Sample",
      "caption": "Context for the photo.",
      "related": [
        {
          "label": "Control Panel Builds",
          "href": "#project-spartan-control-panel-builds"
        }
      ]
    }
  ]
}
```

## Resume template

The PDF resume is generated from the `resume` block in `content/site.json`.

- Page 1 is reserved for work experience, skills, and volunteering.
- Page 2 is reserved for projects and clubs.
- The builder enforces a two-page maximum and fails if a page has too much content.
- The resume never includes website photos, photo captions, or project images.

Edit placeholder fields such as `[insert job title]`, `[insert impact-focused bullet]`, and `[insert project name]`, then rebuild:

```powershell
python scripts/build_site.py
```

## Excel resume editing

Create or refresh the editable Excel template:

```powershell
python scripts/create_resume_template.py
```

Edit `content/resume_template.xlsx`:

- Yellow merged cells are editable placeholders.
- Borders show the reserved text areas that will be imported.
- You can resize merged-cell boundaries in Excel to reserve more or less space.
- Do not delete the top-left anchor cell of a placeholder block.

Sync Excel back into JSON and rebuild the generated site/resume:

```powershell
python scripts/sync_resume_from_excel.py
```
