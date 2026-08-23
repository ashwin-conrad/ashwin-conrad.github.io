# Ashwin Conrad portfolio

A local-first static portfolio. The generated public files are `index.html`, `styles.css`, `script.js`, and `portfolio/resume.pdf`; edit the structured sources rather than those outputs.

## Fast editing workflow

Install the small Python dependency set once:

```powershell
python -m pip install -r requirements.txt
```

Edit the structured JSON files under `content/details/`, then open the workflow menu:

```powershell
python scripts/portfolio.py
```

Choose a numbered purpose area, then a numbered action. The menu groups every operation into **Build & release**, **Resume**, and **Quality checks**, including rebuilding everything, creating a fresh working Word resume, syncing Word edits back to JSON, validation, tests, and GitHub Pages preparation.

`scripts/portfolio.py` is the sole operational entry point in Codespaces and locally. Its named commands (`build`, `build-pages`, `check`, `test`, `sync-shared`, `sync-word`, `new-working-resume`, and `prepare-pages`) remain available for CI and repeatable automation; use `python scripts/portfolio.py --help` for details. The other Python files in `scripts/` are reusable implementation modules.

## Source ownership

| Source | Owns |
| --- | --- |
| `content/details/facts.json` | Canonical identity, organization, experience, and project facts shared by editing surfaces |
| `content/site.json` | Site-wide settings, metadata, navigation, and references to canonical identity facts |
| `content/details.json` + `content/details/website/` | Ordered website sections and individual case studies, including copy, images, captions, links, and contact content |
| `content/resume.json` | Resume manifest, shared-field policy, and fixed Word slot selections |
| `content/details/resume/` | Resume section files recombined by `content/resume.json` |
| `content/details/design-tokens.json` | Colour, font-family, and complete named text-style tokens emitted as site CSS variables and applied to the generated resume during the build |
| `assets/asset-record.json` | Canonical image paths, alt text, titles, and display controls |

`resume.json` is intentionally independent: editing a resume bullet does not replace a longer portfolio case study, and editing website copy does not alter the resume.

## Design tokens

`content/details/design-tokens.json` is the global visual configuration. Each entry under `text.site` and `text.resume` defines a complete text treatment: `fontFamily`, `fontSize`, `fontWeight`, `fontStyle`, `lineHeight`, `letterSpacing`, `color`, and `textTransform`. The `text.resume` styles cover the name, section headings, contact details, dates, role and project titles, body copy, skills, awards, and project notes.

Edit a token value and select **Build & release → Rebuild everything** to regenerate the website CSS and the public résumé DOCX/PDF. The Word working template stays unchanged; the generated public résumé receives the configured text styles during the build.

Website records are kept as individual files under `content/details/website/`. Generic records use neutral IDs and file names (`experience_1`, `leadership_1`, `project_1`, `build_1`); project records live below the experience folder they support. Resume content is defined by `content/resume.json` and its section files under `content/details/resume/`; both surfaces connect to `content/details/facts.json`.

`details.json` is a manifest, so day-to-day website edits follow the page hierarchy:

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

Image descriptions live in `assets/asset-record.json`. Reference an image with `assets.images.image_01.*`; its `display.figure`, `display.title`, and `display.caption` flags control the corresponding optional metadata without altering the image or its required alt text.

Stable IDs connect the files. Website experience cards have `id` and `resume_id`; case studies have `id` and `resume_ids`. The validators reject unknown or duplicate relationships.

## Shared factual fields

`content/resume.json > _meta.shared_fields` is an explicit allow-list for fields such as name, phone, and portfolio URL. Nothing else synchronizes.

Use the **Resume** menu to preview, apply, or force the shared-facts sync. The menu labels explain whether an action only previews changes, preserves independent resume overrides, or replaces them.

Each rule records `last_synced_value`. If a resume value differs from that value, it is reported as an override instead of being overwritten.

## Resume and Word

`portfolio/resume-working.docx` is the editable working resume and contains fixed capacity rows, including four bullet controls per work-experience slot. Use **Resume → Create a fresh working Word resume** to generate a populated copy of the current JSON content. That action asks for confirmation before replacing an existing working file. A build reads it without changing it, removes rows whose controls are blank, and writes generated `portfolio/resume.docx` and PDF.

After editing the working file in Word, select **Resume → Sync Word edits to JSON and rebuild everything**. It imports its Content Control values into `content/details/resume/`, then regenerates the website, public Word resume, and PDF.

The Word import updates the section files under `content/details/resume/`; it does not rewrite website copy. Before running a normal build after a manual Word edit, use the Word sync action first.

## Validate before publishing

Use **Quality checks → Check content and generated output** followed by **Run the test suite**.

For the clean GitHub Pages artifact used in CI:

Select **Build & release → Rebuild and prepare GitHub Pages files**.

## More detail

See [docs/CONTENT_ARCHITECTURE.md](docs/CONTENT_ARCHITECTURE.md) for the data flow, relationships, and safe save behaviour.
