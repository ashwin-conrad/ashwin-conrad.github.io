# Ashwin Conrad portfolio

A local-first static portfolio. The generated public files are `index.html`, `styles.css`, `script.js`, and `portfolio/resume.pdf`; edit the structured sources rather than those outputs.

## Fast editing workflow

Install the small Python dependency set once:

```powershell
python -m pip install -r requirements.txt
```

Edit the structured JSON files under `content/`, or use the Word working files described below, then open the workflow menu:

```powershell
python scripts/portfolio.py
```

Choose a numbered purpose area, then a numbered action. The menu groups every operation into **Build & release**, **Working content**, **Resume**, and **Quality checks**. The Working content area can refresh or synchronize both Word editors together, or operate on the website and resume files independently.

`scripts/portfolio.py` is the sole operational entry point in Codespaces and locally. Its named commands include `new-working` and `sync-working` for the shared workflow, `new-working-website` / `sync-word-website`, `new-working-resume` / `sync-word-resume`, plus the build, check, test, shared-fact, and Pages commands. Use `python scripts/portfolio.py --help` for details. The original `sync-word` name remains a resume-only compatibility alias.

## Source ownership

| Source | Owns |
| --- | --- |
| `content/details/facts.json` | Canonical identity, organization, experience, and project facts shared by editing surfaces |
| `content/site.json` | Site-wide settings, metadata, navigation, references to canonical identity facts, and the ordered website section manifest |
| `content/details/website/` | Individual website sections and case studies, including copy, images, captions, links, and contact content |
| `content/resume.json` | Resume manifest, shared-field policy, and fixed Word slot selections |
| `content/details/resume/` | Resume section files recombined by `content/resume.json` |
| `content/styles.json` | Colour, font-family, and complete named text-style tokens emitted as site CSS variables and applied to the generated resume during the build |
| `content/assets/asset-record.json` | Canonical image paths, alt text, titles, and display controls; photos live beside it under `content/assets/photos/` |
| `content/working/website-working.docx` | Editable projection of website copy, referenced facts, image descriptions, and exact site typography context |
| `content/working/resume-working.docx` | Editable two-page resume projection used to build and sync resume content |

`resume.json` is intentionally independent: editing a resume bullet does not replace a longer portfolio case study, and editing website copy does not alter the resume.

## Design tokens

`content/styles.json` is the global visual configuration. Each entry under `text.site` and `text.resume` defines a complete text treatment: `fontFamily`, `fontSize`, `fontWeight`, `fontStyle`, `lineHeight`, `letterSpacing`, `color`, and `textTransform`. The `text.resume` styles cover the name, section headings, contact details, dates, role and project titles, body copy, skills, awards, and project notes.

Edit a token value and select **Build & release → Rebuild everything** to regenerate the website CSS and the public résumé DOCX/PDF. The Word working template stays unchanged; the generated public résumé receives the configured text styles during the build.

Website records are kept as individual files under `content/details/website/`. Generic records use neutral IDs and file names (`experience_1`, `leadership_1`, `project_1`, `build_1`); project records live below the experience folder they support. Resume content is defined by `content/resume.json` and its section files under `content/details/resume/`; both surfaces connect to `content/details/facts.json`.

`site.json` contains the section manifest, while day-to-day website edits follow the page hierarchy:

```text
content/details/website/
|- hero.json
|- profile.json
|- projects/
|  |- experience_1/
|  |  `- project_1.json
|  |- experience_2/
|  |  `- project_2.json
|  `- experience_3/
|     `- project_5.json
|- experience/
|  |- experience_1.json
|  |- experience_2.json
|  `- experience_3.json
|- skills.json
|- documentation.json
|- leadership/
|  |- leadership_1.json
|  |- leadership_2.json
|  `- leadership_3.json
|- personal-builds/
|  |- build_1.json
|  |- build_2.json
|  `- build_3.json
`- contact.json
```

The build loads those files as one coherent website and writes generated output from the matching section or case-study file. Each optional experience, leadership item, project, personal build, or resume item has an `"include": true` switch; set it to `false` to omit that record without deleting its source. Keep the manifest IDs and file paths stable; they preserve intentional page and project order.

Image descriptions live in `content/assets/asset-record.json`. Reference an image with `assets.images.image_01.*`; its `display.figure`, `display.title`, and `display.caption` flags control the corresponding optional metadata without altering the image or its required alt text. The build publishes `content/assets/` at the stable public `/assets/` path.

Stable IDs connect the files. Website experience cards have `id` and `resume_id`; case studies have `id` and `resume_ids`. The validators reject unknown or duplicate relationships.

## Shared factual fields

`content/resume.json > _meta.shared_fields` is an explicit allow-list for fields such as name, phone, and portfolio URL. Nothing else synchronizes.

Use the **Resume** menu to preview, apply, or force the shared-facts sync. The menu labels explain whether an action only previews changes, preserves independent resume overrides, or replaces them.

Each rule records `last_synced_value`. If a resume value differs from that value, it is reported as an override instead of being overwritten.

## Word editing workflow

The two retained editors live under `content/working/`. Use **Working content → Create both fresh working Word files** to populate them from current JSON. The action asks for confirmation before replacing a file because Word-only edits would otherwise be lost.

`website-working.docx` lists each editable value beside its canonical source path and full website typography token (family, size, weight, style, line height, tracking, and transform). The editable control is styled as a Word preview of that token. `$source` values point to their canonical `facts.json` or `asset-record.json` leaf, so an import updates the owner while preserving the reference in the section file. Structural values such as IDs, file paths, image paths, URLs, include switches, and relationship keys stay in JSON.

`resume-working.docx` contains the fixed-capacity two-page resume layout, including four bullet controls per work-experience slot. A build reads it without changing it, removes public rows whose optional controls are blank, and writes generated `portfolio/resume.docx` and PDF.

After editing either file, select **Working content → Sync both Word files to JSON and rebuild**. Both documents are validated before any source is written, their controls are imported to the owning JSON files, and all public outputs are rebuilt once. Independent website and resume sync actions are available when only one working file was edited.

Build and sync commands print each import, render, conversion, and validation stage as it starts. PDF generation prefers an isolated LibreOffice profile; if that backend is unavailable or fails, Windows uses Microsoft Word in a separate process with a 30-second limit. LibreOffice also has a bounded conversion time, so a blocked converter returns an actionable error instead of indefinitely freezing the menu.

## Validate before publishing

Use **Quality checks → Check content and generated output** followed by **Run the test suite**.

For the clean GitHub Pages artifact used in CI:

Select **Build & release → Rebuild and prepare GitHub Pages files**.

## More detail

See [docs/CONTENT_ARCHITECTURE.md](docs/CONTENT_ARCHITECTURE.md) for the data flow, relationships, and safe save behaviour.
