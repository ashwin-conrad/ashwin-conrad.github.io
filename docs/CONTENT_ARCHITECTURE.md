# Content architecture

## Resulting data flow

```text
Local Content Editor --> site.json -------------------+
                      details.json + section files ---+--> HTML / CSS / JS website
                                                        |
                      resume.json <-------------------+  selected factual-field sync only
                           |
                           `--> Word Content Controls --> DOCX / PDF

Figma frames + component library + design tokens --> renderer/CSS decisions
```

The separation is deliberate:

- `site.json` has durable global facts and navigation, rather than section prose.
- `details.json` is the ordered manifest for the reader-facing website story. Each section owns a smaller file below `content/details/portfolio/`; the case-studies section is an ordered collection whose individual records own project files. The renderer composes both levels in manifest order.
- `resume.json` has short, recruiter-facing material and an independent order. It does not import website descriptions or case-study copy automatically.
- `design-tokens.json` contains the visual foundation values emitted as CSS custom properties. It is not a content source.

## Details hierarchy

The editor-facing website content is split at real visual boundaries, and each featured project is independently editable:

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

`content/details.json` stores the ordered section IDs and paths. Its case-studies record stores the ordered project IDs and paths. It is deliberately not a second copy of the content. The renderer and editor load that manifest into a composed `details.portfolio` object; the editor writes each affected section or case-study file after the full relationship check passes.

## Relationships and ordering

Resume records have stable `id` values. Their website relationship uses the same IDs rather than titles, which makes copy edits harmless:

```json
{
  "id": "formula-ev-lv",
  "resume_id": "formula-ev-lv"
}
```

One case study can support more than one resume entry:

```json
{
  "id": "formula-ev",
  "resume_ids": ["formula-ev-lv", "formula-ev-electrical-systems"]
}
```

The editor allows card, skill, figure, link, and bullet reordering. It locks existing ID fields, and validation rejects an unknown relationship. New cards receive a visible temporary `new-item-*` ID; replace it in a deliberate code review if the new card is intended to become a durable relationship.

The Word template itself is fixed at two pages. Its explicit ID-based slot policy is stored in `resume.json > _meta.word_slot_order` and implemented by `scripts/resume/mapper.py`. This avoids an implicit "first four projects" rule while leaving the broader resume ordering independent.

## Shared facts, not shared copy

`resume._meta.shared_fields` has only the facts that are consciously shared. The sync code compares three values for every rule:

1. Current source value in `site.json`.
2. Current destination value in `resume.json`.
3. `last_synced_value` recorded by the prior sync.

If the resume still has its last-synced value, a changed source can be pulled in safely. If the resume differs, the resume wins and the command reports an override. `--force` is required to replace that override. No summaries, project descriptions, experience bullets, skills, captions, or ordering are shared unless a future rule explicitly says so.

## Local editor safety model

The editor sends the three documents with SHA-256 revisions. The server checks those revisions against disk before any write, returning a conflict rather than overwriting a change made in VS Code, Git, or another editor tab. It validates source shape and relationships first, then writes each JSON file through a sibling temporary file and replace operation.

For images, selecting an existing file uses an asset-path list and shows a thumbnail. Importing an image copies a user-selected file into `assets/photos/` only if its simple filename is new; it never overwrites an existing asset. The image path and non-empty alt text remain normal structured content fields.

## Why the local editor is the default

| Option | Best role here | Why it is not the primary content editor |
| --- | --- | --- |
| Local browser editor | **Recommended** | It groups fields by real website sections, previews changes, manages images, preserves IDs, and safely writes the existing JSON. |
| Word | Resume layout and final visual review | It is excellent for the DOCX template, but not for grouped web content, images, or reliable record relationships. |
| Excel | Occasional bulk inventory/export | A grid is useful for auditing a lot of records, but it lacks page context and becomes awkward for long prose, nested figures, and links. |
| PowerPoint | Design discussion only | It is useful for visual narrative ideas, but is not a durable structured-content store. |
