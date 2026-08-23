# Ashwin Conrad portfolio

A local-first static portfolio. The generated public files are `index.html`, `styles.css`, `script.js`, and `portfolio/resume.pdf`; edit the structured sources rather than those outputs.

## Fast editing workflow

Install the small Python dependency set once:

```powershell
python -m pip install -r requirements.txt
```

Run the local content editor:

```powershell
python scripts/portfolio.py editor
```

Open `http://127.0.0.1:4173/editor/`. It groups fields by the part of the website where they appear, previews unsaved changes, supports item ordering and image import/selection, and saves with an on-disk revision check. It is local-only: no account, database, or remote dependency.

Use **Save all JSON**, then **Build website + resume**. The latter regenerates the HTML/CSS/JS, Word resume, and PDF.

`scripts/portfolio.py` is the sole operational entry point in Codespaces and locally. Its commands are `editor`, `build`, `check`, `sync-shared`, `sync-word`, and `prepare-pages`; the other Python files in `scripts/` are reusable implementation modules.

## Source ownership

| Source | Owns |
| --- | --- |
| `content/site.json` | Site-wide settings, metadata, identity facts, and navigation |
| `content/details.json` + `content/details/` | Ordered website sections and individual case studies, including copy, images, captions, links, and contact content |
| `content/resume.json` | Concise resume wording, chosen order, skills, bullets, awards, and Word-template slot selection |
| `content/design-tokens.json` | Visual foundation colours used by CSS and available to import into Figma |

`resume.json` is intentionally independent: editing a resume bullet does not replace a longer portfolio case study, and editing website copy does not alter the resume.

`details.json` is a manifest, so day-to-day website edits follow the page hierarchy:

```text
content/details/portfolio/
|- hero.json
|- profile.json
|- projects/
|  |- formula-ev.json
|  |- heat-exchanger.json
|  `- spartan-controls.json
|- experience.json
|- skills.json
|- documentation.json
|- leadership.json
|- personal-builds.json
`- contact.json
```

The local editor loads those files as one coherent page and writes changes back to the matching section or case-study file. Keep the manifest IDs and file paths stable; they preserve intentional page and project order.

Stable IDs connect the files. Website experience cards have `id` and `resume_id`; case studies have `id` and `resume_ids`. The local editor locks existing IDs against accidental changes. The validators reject unknown or duplicate relationships.

## Shared factual fields

`content/resume.json > _meta.shared_fields` is an explicit allow-list for fields such as name, phone, and portfolio URL. Nothing else synchronizes.

```powershell
# Preview safe changes without writing
python scripts/portfolio.py sync-shared

# Pull only fields not independently edited in the resume
python scripts/portfolio.py sync-shared --apply

# Intentionally overwrite independent resume values
python scripts/portfolio.py sync-shared --apply --force
```

Each rule records `last_synced_value`. If a resume value differs from that value, it is reported as an override instead of being overwritten.

## Resume and Word

`portfolio/resume.docx` remains the editable layout artifact and has stable Word Content Control tags. JSON is the normal content source; Word is the layout surface.

```powershell
python scripts/portfolio.py build                           # website + DOCX + PDF
python scripts/portfolio.py build --resume-only --docx-only # DOCX only
python scripts/portfolio.py sync-word                       # import Word edits, then rebuild
```

The Word import updates only `content/resume.json`; it does not rewrite website copy. Before running a normal build after a manual Word edit, run the Word sync command first.

## Validate before publishing

```powershell
python scripts/portfolio.py check
python -m unittest discover -s tests
```

For the clean GitHub Pages artifact used in CI:

```powershell
python scripts/portfolio.py prepare-pages
```

## Figma workflow

Use Figma for visual structure, responsive composition, components, and design tokens, not as the portfolio text database. The working agreement and Figma setup are in [docs/FIGMA_WORKFLOW.md](docs/FIGMA_WORKFLOW.md). The renderer remains the source of HTML semantics and responsive behaviour.

## More detail

See [docs/CONTENT_ARCHITECTURE.md](docs/CONTENT_ARCHITECTURE.md) for the data flow, relationships, and safe save behaviour.
