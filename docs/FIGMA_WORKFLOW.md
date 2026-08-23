# Figma-to-renderer workflow

Figma governs the portfolio's visual design, page hierarchy, components, and responsive intent. JSON governs published content. Treating Figma text layers as a content database creates fragile copy/paste synchronization, breaks stable record relationships, and makes the resume harder to maintain.

## Recommended setup

Create one Figma file with these pages:

1. **Foundations** - import `content/design-tokens.json` into a Figma Variables collection; document typography, grid, breakpoints, and image treatment.
2. **Components** - Header, hero, section heading, case-study header, image figure, experience row, skill group, contact link, and resume callout.
3. **Portfolio / desktop** - an annotated full page assembled from instances.
4. **Portfolio / mobile** - the same page at the mobile breakpoint, with explicit decisions about stacking, crop behaviour, and navigation.
5. **Ready for build** - only approved frames; use component descriptions to record non-obvious interaction and accessibility requirements.

Name frames after the renderer sections (`Hero`, `Profile`, `Case studies`, `Experience`, `Documentation`, `Contact`). Add the matching JSON file in each frame description, for example `content/details/portfolio/projects/formula-ev.json` (or `details.portfolio.case_studies` as the composed data path). This creates a simple visual-to-content map without trying to round-trip text layers.

## Day-to-day loop

1. Change layout, hierarchy, typography, spacing, component variants, or image aspect-ratio intent in Figma.
2. Update `content/design-tokens.json` for foundation-token changes. The next `python scripts/portfolio.py build` emits those values as CSS custom properties.
3. Implement structural/layout changes in `scripts/site_renderer.py` and its CSS renderer. Keep semantic HTML, accessible labels, and responsive rules in code; do not paste Figma-generated markup directly into the site.
4. Edit real titles, bullets, links, figures, and captions in the Local Content Editor. Preview the result, build, and compare it with the approved Figma frame.

For a small static portfolio, this is more maintainable than a Figma export or plugin that attempts to regenerate the page. Figma's inspect tools are useful for dimensions, typography, assets, variables, and component intent, while the Python renderer remains accountable for the actual web page.

## What not to automate

Do not make Figma the primary source for long text, skills, resume bullets, or record IDs. Do not auto-export entire Figma frames into production HTML/CSS. Those approaches make DOM semantics, responsiveness, accessibility, content relationships, and normal Git review unreliable.

Figma Code Connect can be useful for a larger component-based product, but it is unnecessary for this single Python-rendered site. If this portfolio later becomes a reusable component library, revisit Code Connect only after the renderer has real named UI components to link.
