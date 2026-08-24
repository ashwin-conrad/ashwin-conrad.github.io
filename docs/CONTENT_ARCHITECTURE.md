# Content architecture

## Resulting data flow

```text
Structured JSON sources --> facts.json ----------------+
                      site.json + section files ------+--> HTML / CSS / JS website
                      content/assets/asset-record.json +
                           ^
                           `---- website-working.docx (editable projection)
                                                        |
                      resume.json <-------------------+  selected factual-field sync only
                           |
                           `--> resume-working.docx --> DOCX / PDF

styles.json --> website CSS + generated resume text theme
```

The separation is deliberate:

- `details/facts.json` is the canonical home for durable facts that are reused by more than one editing surface. It owns identity, organizations, education, experience facts, project metadata and metrics, skills, leadership, community involvement, recognition, and personal-project labels. Website and resume wording can still be tailored independently.
- `site.json` has durable global facts and navigation plus the ordered manifest for the reader-facing website story. Each section owns a smaller file below `content/details/website/`; the case-studies section is an ordered collection whose generic records live beneath the experience folder they support. The renderer composes both levels in manifest order.
- `resume.json` is the résumé manifest and Word-slot configuration; its section files under `details/resume/` contain short, recruiter-facing material and an independent order. It does not import website descriptions or case-study copy automatically.
- `content/styles.json` contains the colour, font, and named text-style values emitted as CSS custom properties and applied to the generated Word resume theme. Every text style has font family, size, weight, style, line height, letter spacing, colour, and text transform; `text.resume` covers every visible resume text treatment. It is not a prose source or a Word editing surface.
- `content/assets/asset-record.json` owns each image's path, alt text, title, and optional display flags, with the image files under `content/assets/photos/`. Content records reference these values with `assets.images.image_N.*`; contextual captions remain beside the page record that uses them. Pages publishes this source directory at the stable public `/assets/` path.
- `content/working/website-working.docx` is one tagged editing surface for website strings. Each row identifies its owning JSON path and exact `text.site.*` typography token; referenced facts and asset descriptions sync to the canonical owner without flattening `$source` objects.
- `content/working/resume-working.docx` is the retained, tagged resume layout. Both Word files use the same CLI refresh-and-sync workflow, while their public outputs remain independent.

## Details hierarchy

The editor-facing website content is split at real visual boundaries, and each featured project is independently editable:

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

`content/site.json > website.sections` stores the ordered section IDs and paths. Its case-studies record stores the ordered project IDs and paths. It is deliberately not a second copy of the content. The renderer loads that manifest into a composed `website` object and resolves references before rendering.

## Relationships and ordering

Resume records have stable, neutral `id` values. Their website relationship uses the same IDs rather than titles, which makes copy edits harmless:

```json
{
  "id": "experience_1",
  "include": true,
  "resume_id": "experience_1"
}
```

One case study can support more than one resume entry:

```json
{
  "id": "project_1",
  "include": true,
  "resume_ids": ["experience_1", "project_1"]
}
```

The source files keep stable IDs for records and validation rejects unknown relationships. Use neutral sequence IDs (`experience_4`, `project_7`, `build_3`) and set `include` to `false` when a record should stay in the source but not appear in output. New included records should receive a deliberate durable ID before they are used by Word slot mappings.

The Word template itself is fixed at two pages. Its explicit ID-based slot policy is stored in `resume.json > _meta.word_slot_order` and read by `scripts/resume/mapper.py`; no résumé-specific IDs are embedded in Python. This avoids an implicit "first four projects" rule while leaving the broader resume ordering independent.

## Shared facts, not shared copy

`resume._meta.shared_fields` has only the facts that are consciously shared. The sync code compares three values for every rule:

1. Current source value in `site.json`.
2. Current destination value in `resume.json`.
3. `last_synced_value` recorded by the prior sync.

If the resume still has its last-synced value, a changed source can be pulled in safely. If the resume differs, the resume wins and the command reports an override. `--force` is required to replace that override. No summaries, project descriptions, experience bullets, skills, captions, or ordering are shared unless a future rule explicitly says so.

## Shared Word working workflow

`content/working/website-working.docx` and `content/working/resume-working.docx` are editable projections populated from current JSON. The interactive **Working content** menu can recreate both, sync both, or operate on either document independently. The shared sync stages and validates both imports before writing, then rebuilds all public outputs once.

The website editor follows manifest order and exposes direct authored text plus referenced canonical text. IDs, relationship keys, include switches, file paths, image paths, and link destinations remain JSON-only structural data. Every editable row shows the source file and JSON path, typography token, font stack, responsive CSS size, weight, style, line height, tracking, and transform. The right column uses the closest Word representation, with an explicit preview-size cap for unusually large responsive headings while retaining the exact CSS value in the context column.

`content/resume.json` remains the manifest plus neutral slot selection for the fixed Word layout. Its section files under `content/details/resume/` are recombined before the resume mapper runs. Generated `portfolio/resume.docx` is a clean public projection. Experience and selected-project slots each require four bullets; leadership, community involvement, and recognition slots use the same title, organization, location, and dates fields with one detail bullet. The first-page order is Experience, Leadership, Community Involvement, then Recognition. Run the CLI quality check after source edits.
