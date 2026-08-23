# Content architecture

## Resulting data flow

```text
Structured JSON sources --> facts.json ----------------+
                      site.json ----------------------+
                      details.json + section files ---+--> HTML / CSS / JS website
                      asset-record.json -------------+
                                                        |
                      resume.json <-------------------+  selected factual-field sync only
                           |
                           `--> Word Content Controls --> DOCX / PDF

Design tokens --> website CSS + generated resume text theme
```

The separation is deliberate:

- `details/facts.json` is the canonical home for durable facts that are reused by more than one editing surface. It owns identity, organizations, education, experience facts, project metadata and metrics, skills, leadership, community involvement, recognition, and personal-project labels. Website and resume wording can still be tailored independently.
- `site.json` has durable global facts and navigation, rather than section prose.
- `details.json` is the ordered manifest for the reader-facing website story. Each section owns a smaller file below `content/details/website/`; the case-studies section is an ordered collection whose generic records live beneath the experience folder they support. The renderer composes both levels in manifest order.
- `resume.json` is the résumé manifest and Word-slot configuration; its section files under `details/resume/` contain short, recruiter-facing material and an independent order. It does not import website descriptions or case-study copy automatically.
- `design-tokens.json` contains the colour, font, and named text-style values emitted as CSS custom properties and applied to the generated Word resume theme. Every text style has font family, size, weight, style, line height, letter spacing, colour, and text transform; `text.resume` covers every visible resume text treatment. It is not a content source or an editing surface.
- `assets/asset-record.json` owns each image's path, alt text, title, and optional display flags. Content records reference these values with `assets.images.image_N.*`; contextual captions remain beside the page record that uses them.

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

`content/details.json` stores the ordered section IDs and paths. Its case-studies record stores the ordered project IDs and paths. It is deliberately not a second copy of the content. The renderer loads that manifest into a composed `details.website` object and resolves references before rendering.

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

## Resume working workflow

`content/resume.json` is a manifest plus the neutral slot selection for the fixed Word layout. Its section files under `content/details/resume/` are recombined before the résumé mapper runs. `portfolio/resume-working.docx` is an editable projection populated from the current JSON; generated `portfolio/resume.docx` is a clean public projection. The interactive CLI creates the working resume, imports its Word Content Control edits back to the resume JSON, and then rebuilds the public outputs. Experience and selected-project slots each require four bullets; leadership, community involvement, and recognition slots use the same title, organization, location, and dates fields with one detail bullet. The first-page order is Experience, Leadership, Community Involvement, then Recognition. Run the CLI quality check after source edits.
