# ashwin-conrad.github.io
Ashwin Conrad's Github Portfolio Website

## Repository layout

- `content/` - editable site, resume, gallery, project, and case-study source data.
- `content/context/` - supporting notes used while maintaining content.
- `assets/photos/` - optimized images referenced by the site.
- `assets/brand/` - brand references and visual assets.
- `scripts/` - build and content-editing tools; `site_renderer.py` contains the presentation layer and `project_paths.py` contains shared paths.
- `portfolio/resume.docx` - retained editable Word resume, including the Content Controls used for Word-to-website synchronization.
- `index.html`, `styles.css`, `script.js`, and `portfolio/resume.pdf` - generated GitHub Pages output.
- `tmp/` - local-only previews, downloads, and cloned reference repositories.

## Editing workflow

For a fresh local checkout, install the build dependencies first:

```powershell
python -m pip install -r requirements.txt
```

Edit structure, navigation, and resume high-level details in `content/site.json`. Edit the recruiter-facing engineering case studies, skills, figures, captions, gallery groups, and contact copy in `content/details.json` under `portfolio`. Then rebuild the generated files:

```powershell
python scripts/build_site.py
```

The script regenerates `index.html`, `styles.css`, `script.js`, and `portfolio/resume.pdf`, while refreshing the editable fields in `portfolio/resume.docx`. The resume block in `content/site.json` remains the structured source for roles, organizations, locations, dates, bullets, leadership, and awards. The case-study copy is deliberately separate so longer descriptions and placeholders can be maintained without bloating the resume.

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

The primary portfolio renderer also uses image objects in `content/details.json > portfolio`. Images in case studies and documentation figures open in a small dependency-free lightbox. Keep public images in `assets/photos/` and add any missing engineering evidence listed in `CONTENT_TODO.md`.

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

## Resume architecture

`content/site.json` is the structured synchronization data behind the resume and website. `content/details.json` remains for longer website case studies and is not used to duplicate resume text.

`portfolio/resume.docx` is both the public editable Word resume and the retained layout artifact. Its Content Controls are addressed by tag, not by Word's numeric `w:id`. Keep the controls intact when adjusting its layout; the build validates their complete tag inventory.

`scripts/resume/mapper.py` adapts stable resume IDs to the template's fixed slots: AltaGas and Spartan Controls are the two page-one experience entries; Formula EV is leadership plus a page-two technical project; four explicitly selected stable-ID projects populate page two. This makes any intentional fixed-template selection clear without duplicating resume prose.

Use `portfolio/resume.docx` as the only concise-resume editor. After making changes in Word, save and close it, then run `python scripts/sync_resume_from_word.py`. This imports its controls into `content/site.json` and rebuilds the PDF and website.

Do not run the regular build after manual Word content changes without first running the Word sync command, because the regular build applies the structured JSON values back to the document. Technical-category labels and the portfolio callout are Word-only presentation copy, so direct edits to those controls remain in Word and are not copied into website JSON.

Build only the resume:

```powershell
python scripts/build_resume.py
```

Useful validation/build variants:

```powershell
python scripts/build_resume.py --validate-only
python scripts/build_resume.py --docx-only
```

The renderer validates Content Control tags, required values, configurable field-length limits, and the final two-page PDF. PDF export uses Microsoft Word automation when available, with LibreOffice headless as a local fallback. If neither is installed, the DOCX remains valid and the command reports how to proceed.
