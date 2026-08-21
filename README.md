# ashwin-conrad.github.io
Ashwin Conrad's Github Portfolio Website

## Editing workflow

Edit the portfolio and resume content in `content/site.json`, then rebuild the generated files:

```powershell
python scripts/build_site.py
```

The script regenerates `index.html`, `styles.css`, and `portfolio/resume.pdf` from `content/site.json`. Website content, website photos, and resume blocks are edited in the same file but rendered separately.

## Photos

Save website photos in `assets/photos/`, then reference them in `content/site.json`.

Project cards support an optional image:

```json
"image": {
  "src": "assets/photos/project-photo.jpg",
  "alt": "Short description of the project photo"
}
```

The standalone photos section appears only when `photos.items` has entries:

```json
{
  "src": "assets/photos/shop-build.jpg",
  "alt": "Prototype assembly on a workbench",
  "title": "Prototype Assembly",
  "caption": "Early fit-up and wiring test."
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
