from __future__ import annotations

import html
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph


ROOT = Path(__file__).resolve().parents[1]
CONTENT_PATH = ROOT / "content" / "site.json"
DETAILS_PATH = ROOT / "content" / "details.json"
INDEX_PATH = ROOT / "index.html"
STYLES_PATH = ROOT / "styles.css"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def attrs(values: dict[str, str | None]) -> str:
    rendered = [f'{key}="{esc(value)}"' for key, value in values.items() if value]
    return (" " + " ".join(rendered)) if rendered else ""


def tag_list(items: list[str], class_name: str) -> str:
    tags = "\n".join(f"                    <span>{esc(item)}</span>" for item in items)
    return f'<div class="{class_name}">\n{tags}\n                </div>'


def image_markup(image: dict | None, class_name: str) -> str:
    if not image or not image.get("src"):
        return ""
    return (
        f'                        <figure class="{class_name}">\n'
        f'                            <img src="{esc(image["src"])}" alt="{esc(image.get("alt", ""))}" loading="lazy">\n'
        f"                        </figure>\n\n"
    )


def load_content() -> dict:
    data = json.loads(CONTENT_PATH.read_text(encoding="utf-8"))
    details = json.loads(DETAILS_PATH.read_text(encoding="utf-8")) if DETAILS_PATH.exists() else {}
    apply_resume_mirrors(data, details)
    return data


def apply_resume_mirrors(data: dict, details: dict) -> None:
    resume_items = {
        item["id"]: item
        for page in data.get("resume", {}).get("pages", [])
        for block in page.get("blocks", [])
        for item in block.get("items", [])
        if item.get("id")
    }

    detail_experience = details.get("experience", {})
    for item in data.get("experience", {}).get("items", []):
        item_id = item.get("id") or item.get("resume_id")
        if item_id:
            item["id"] = item_id
            mirror_resume_item(item, resume_items.get(item.get("resume_id", item_id)), "company")
            item.update(detail_experience.get(item_id, {}))

    detail_projects = details.get("projects", {})
    for item in data.get("projects", {}).get("items", []):
        item_id = item.get("id") or item.get("resume_id")
        if item_id:
            item["id"] = item_id
            mirror_resume_item(item, resume_items.get(item.get("resume_id", item_id)), "organization")
            item.update(detail_projects.get(item_id, {}))

    if details.get("photos"):
        data.setdefault("photos", {}).update(details["photos"])


def mirror_resume_item(site_item: dict, resume_item: dict | None, organization_key: str) -> None:
    if not resume_item:
        return
    site_item["role"] = resume_item.get("role", site_item.get("role", ""))
    site_item["date"] = resume_item.get("dates", site_item.get("date", ""))
    site_item["location"] = resume_item.get("location", site_item.get("location", ""))
    site_item[organization_key] = resume_item.get("organization", site_item.get(organization_key, ""))
    if organization_key == "organization" and site_item.get("mirror_name", True):
        site_item["name"] = resume_item.get("role", site_item.get("name", ""))


def anchor_id(prefix: str, item: dict) -> str:
    return f'{prefix}-{esc(item["id"])}' if item.get("id") else ""


def render_related_links(item: dict) -> str:
    links = item.get("related", [])
    if not links:
        return ""
    rendered_links = "\n".join(
        f'                                <a href="{esc(link["href"])}">{esc(link["label"])}</a>'
        for link in links
        if link.get("href") and link.get("label")
    )
    if not rendered_links:
        return ""
    return f"""                            <div class="related-links">
                                <span>Related</span>
{rendered_links}
                            </div>"""


def render_index(data: dict) -> str:
    site = data["site"]
    nav = "\n".join(f'                <a href="{esc(item["href"])}">{esc(item["label"])}</a>' for item in data["nav"])
    hero_buttons = "\n\n".join(
        f'                <a href="{esc(button["href"])}" class="button {esc(button.get("style", "secondary"))}"{attrs({"target": button.get("target")})}>\n'
        f'                    {esc(button["label"])}\n'
        f"                </a>"
        for button in data["hero"]["buttons"]
    )
    experience_items = "\n\n".join(render_experience_item(item) for item in data["experience"]["items"])
    project_items = "\n\n".join(render_project_item(item) for item in data["projects"]["items"])
    photos_section = render_photos_section(data.get("photos", {}))
    passion_items = "\n\n".join(render_passion_item(item) for item in data["passions"]["items"])
    contact_links = "\n\n".join(
        f'                    <a href="{esc(link["href"])}"{attrs({"target": link.get("target")})}>\n'
        f'                        {esc(link["label"])}\n'
        f"                    </a>"
        for link in data["contact"]["links"]
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{esc(site["title"])}</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <!-- Generated by scripts/build_site.py from content/site.json and content/details.json. -->
    <nav class="navbar">
        <div class="nav-container">
            <a href="#home" class="logo">{esc(site["initials"])}</a>

            <div class="nav-links">
{nav}
            </div>
        </div>
    </nav>

    <header class="hero" id="home">
        <div class="container hero-content">
            <p class="eyebrow">{esc(data["hero"]["eyebrow"])}</p>

            <h1>
                {esc(data["hero"]["headline_prefix"])} <span>{esc(data["hero"]["headline_name"])}</span>
            </h1>

            <p class="hero-description">
                {esc(data["hero"]["description"])}
            </p>

            <div class="hero-buttons">
{hero_buttons}
            </div>
        </div>
    </header>

    <main>
        <section class="section" id="about">
            <div class="container narrow">
                <p class="section-number">{esc(data["about"]["number"])}</p>
                <h2>{esc(data["about"]["heading"])}</h2>

                <p class="large-text">
                    {esc(data["about"]["lead"])}
                </p>

                <p>
                    {esc(data["about"]["body"])}
                </p>

                {tag_list(data["about"]["skills"], "skills")}
            </div>
        </section>

        <section class="section alternate" id="experience">
            <div class="container">
                <p class="section-number">{esc(data["experience"]["number"])}</p>
                <h2>{esc(data["experience"]["heading"])}</h2>

                <div class="timeline">
{experience_items}
                </div>

                <div class="resume-callout">
                    <div>
                        <p class="section-number">{esc(data["experience"]["callout"]["number"])}</p>
                        <h3>{esc(data["experience"]["callout"]["heading"])}</h3>
                    </div>

                    <a href="{esc(site["resume_path"])}" target="_blank" class="button primary">
                        {esc(data["experience"]["callout"]["button_label"])}
                    </a>
                </div>
            </div>
        </section>

        <section class="section" id="projects">
            <div class="container">
                <p class="section-number">{esc(data["projects"]["number"])}</p>
                <h2>{esc(data["projects"]["heading"])}</h2>

                <div class="project-grid">
{project_items}
                </div>
            </div>
        </section>

{photos_section}

        <section class="section alternate" id="passions">
            <div class="container">
                <p class="section-number">{esc(data["passions"]["number"])}</p>
                <h2>{esc(data["passions"]["heading"])}</h2>

                <div class="passion-grid">
{passion_items}
                </div>
            </div>
        </section>

        <section class="section contact-section" id="contact">
            <div class="container narrow">
                <p class="section-number">{esc(data["contact"]["number"])}</p>
                <h2>{esc(data["contact"]["heading"])}</h2>

                <p class="large-text">
                    {esc(data["contact"]["lead"])}
                </p>

                <div class="contact-links">
{contact_links}
                </div>
            </div>
        </section>
    </main>

    <footer>
        <div class="container footer-content">
            <p>&copy; {esc(site["year"])} {esc(site["name"])}</p>
            <a href="#home">Back to top ^</a>
        </div>
    </footer>
</body>
</html>
"""


def render_experience_item(item: dict) -> str:
    location = f'\n                            <span>{esc(item["location"])}</span>' if item.get("location") else ""
    return f"""                    <article class="experience-item"{attrs({"id": anchor_id("work", item)})}>
                        <div class="experience-date">
                            {esc(item["date"])}
                        </div>

                        <div class="experience-content">
                            <h3>{esc(item["role"])}</h3>
                            <p class="company">
                                <span>{esc(item["company"])}</span>{location}
                            </p>

                            <p>
                                {esc(item["description"])}
                            </p>

                            {tag_list(item["tags"], "tags")}
{render_related_links(item)}
                        </div>
                    </article>"""


def render_project_item(item: dict) -> str:
    class_name = "project-card featured" if item.get("featured") else "project-card"
    meta_parts = [item.get("organization"), item.get("location"), item.get("date")]
    meta = " | ".join(part for part in meta_parts if part)
    project_meta = (
        f"""                            <p class="project-meta">
                                {esc(meta)}
                            </p>
"""
        if meta
        else ""
    )
    return f"""                    <article class="{class_name}"{attrs({"id": anchor_id("project", item)})}>
                        <div class="project-number">{esc(item["number"])}</div>

                        <div>
{image_markup(item.get("image"), "project-image")}
                            <p class="project-type">
                                {esc(item["type"])}
                            </p>

                            <h3>{esc(item["name"])}</h3>

{project_meta}
                            <p>
                                {esc(item["description"])}
                            </p>

                            {tag_list(item["tags"], "tags")}
{render_related_links(item)}
                        </div>
                    </article>"""


def render_photos_section(photos: dict) -> str:
    groups = photos.get("groups", [])
    items = photos.get("items", [])
    if not groups and not items:
        return ""
    if groups:
        photo_content = f"""                <div class="photo-groups">
{chr(10).join(render_photo_group(group) for group in groups)}
                </div>"""
    else:
        photo_items = "\n\n".join(render_photo_item(item) for item in items)
        photo_content = f"""                <div class="photo-grid">
{photo_items}
                </div>"""
    intro = (
        f"""
                <p class="photo-intro">
                    {esc(photos.get("intro", ""))}
                </p>
"""
        if photos.get("intro")
        else ""
    )
    return f"""        <section class="section alternate" id="{esc(photos.get("id", "photos"))}">
            <div class="container">
                <p class="section-number">{esc(photos.get("number", "PHOTOS"))}</p>
                <h2>{esc(photos.get("heading", "Photos"))}</h2>
{intro}
{photo_content}
            </div>
        </section>"""


def render_photo_group(group: dict) -> str:
    photo_items = "\n\n".join(render_photo_item(item) for item in group.get("items", []))
    intro = (
        f"""
                            <p>
                                {esc(group.get("intro", ""))}
                            </p>"""
        if group.get("intro")
        else ""
    )
    return f"""                    <section class="photo-group">
                        <div class="photo-group-header">
                            <h3>{esc(group.get("heading", "Photo Set"))}</h3>{intro}
                        </div>

                        <div class="photo-grid">
{photo_items}
                        </div>
                    </section>"""


def render_photo_item(item: dict) -> str:
    title = item.get("title", "")
    caption = item.get("caption", "")
    caption_markup = (
        f"""                        <figcaption>
                            {f"<strong>{esc(title)}</strong>" if title else ""}
                            {f"<span>{esc(caption)}</span>" if caption else ""}
{render_related_links(item)}
                        </figcaption>
"""
        if title or caption or item.get("related")
        else ""
    )
    class_name = "photo-card featured" if item.get("featured") else "photo-card"
    return f"""                            <figure class="{class_name}">
                        <img src="{esc(item["src"])}" alt="{esc(item.get("alt", ""))}" loading="lazy" decoding="async">
{caption_markup}                    </figure>"""


def render_passion_item(item: dict) -> str:
    return f"""                    <div class="passion">
                        <span class="passion-number">{esc(item["number"])}</span>
                        <h3>{esc(item["name"])}</h3>
                        <p>
                            {esc(item["description"])}
                        </p>
                    </div>"""


def render_styles() -> str:
    return """/* Generated by scripts/build_site.py from content/site.json and content/details.json. */

:root {
    /* Brand palette, ordered from cool to warm. */
    --palette-violet: #9d2f9b;
    --palette-magenta: #c43c7c;
    --palette-coral: #dc514d;
    --palette-orange: #ed761d;
    --palette-gold: #f2a51c;

    /* Neutral grayscale ramp. */
    --gray-0: #ffffff;
    --gray-50: #f5f5f5;
    --gray-100: #e6e6e6;
    --gray-300: #c4c4c4;
    --gray-500: #737373;
    --gray-700: #3d3d3d;
    --gray-900: #151515;

    --background: var(--gray-50);
    --surface: var(--gray-100);
    --text: var(--gray-900);
    --muted: var(--gray-500);
    --border: var(--gray-300);
    --accent: var(--palette-orange);
    --accent-dark: var(--palette-coral);
    --highlight: var(--palette-gold);
    --on-accent: var(--gray-0);
    --max-width: 1180px;
}

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

html {
    scroll-behavior: smooth;
}

body {
    font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
    background: var(--background);
    color: var(--text);
    line-height: 1.6;
}

a {
    color: inherit;
    text-decoration: none;
}

.container {
    width: min(90%, var(--max-width));
    margin: 0 auto;
}

.narrow {
    max-width: 850px;
}

.section {
    padding: 120px 0;
}

.alternate {
    background: var(--surface);
}

.section-number {
    font-size: 0.75rem;
    letter-spacing: 0.16em;
    font-weight: 700;
    color: var(--accent);
    margin-bottom: 18px;
}

h1,
h2,
h3 {
    line-height: 1.08;
}

h2 {
    font-size: clamp(2.6rem, 6vw, 5rem);
    letter-spacing: -0.05em;
    margin-bottom: 50px;
}

h3 {
    font-size: 1.6rem;
}

p {
    color: var(--muted);
}

.large-text {
    font-size: clamp(1.35rem, 2.5vw, 2rem);
    color: var(--text);
    line-height: 1.45;
    margin-bottom: 25px;
}

.navbar {
    position: sticky;
    top: 0;
    z-index: 100;
    background: color-mix(in srgb, var(--background) 92%, transparent);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid var(--border);
}

.nav-container {
    width: min(90%, var(--max-width));
    height: 72px;
    margin: 0 auto;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.logo {
    font-size: 1.4rem;
    font-weight: 800;
}

.nav-links {
    display: flex;
    gap: 30px;
    font-size: 0.9rem;
    font-weight: 600;
}

.nav-links a {
    transition: color 0.2s;
}

.nav-links a:hover {
    color: var(--accent);
}

.hero {
    min-height: calc(100vh - 72px);
    display: flex;
    align-items: center;
    padding: 80px 0;
}

.hero-content {
    max-width: var(--max-width);
}

.eyebrow {
    color: var(--accent);
    letter-spacing: 0.18em;
    font-size: 0.8rem;
    font-weight: 700;
    margin-bottom: 25px;
}

.hero h1 {
    font-size: clamp(4rem, 10vw, 9rem);
    letter-spacing: -0.07em;
    max-width: 1000px;
}

.hero h1 span {
    color: var(--accent);
}

.hero-description {
    max-width: 680px;
    font-size: clamp(1.1rem, 2vw, 1.45rem);
    margin-top: 35px;
}

.hero-buttons {
    display: flex;
    gap: 15px;
    flex-wrap: wrap;
    margin-top: 40px;
}

.button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 13px 22px;
    border: 1px solid var(--text);
    font-weight: 700;
    font-size: 0.9rem;
    transition: 0.2s ease;
}

.button.primary {
    background: var(--text);
    color: var(--on-accent);
}

.button.primary:hover {
    background: var(--accent);
    border-color: var(--accent);
}

.button.secondary:hover {
    background: var(--text);
    color: var(--on-accent);
}

.skills,
.tags {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.skills {
    margin-top: 35px;
}

.skills span,
.tags span {
    border: 1px solid var(--border);
    padding: 6px 11px;
    font-size: 0.8rem;
    font-weight: 600;
}

.timeline {
    border-top: 1px solid var(--border);
}

.experience-item {
    display: grid;
    grid-template-columns: 200px 1fr;
    gap: 60px;
    padding: 45px 0;
    border-bottom: 1px solid var(--border);
}

.experience-date {
    color: var(--muted);
    font-family: monospace;
    font-size: 0.85rem;
}

.experience-content {
    max-width: 700px;
}

.company {
    color: var(--accent);
    font-weight: 600;
    margin: 5px 0 18px;
}

.company span + span {
    color: var(--muted);
    font-weight: 500;
}

.company span + span::before {
    content: " | ";
    color: var(--border);
}

.experience-content .tags {
    margin-top: 20px;
}

.related-links {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 18px;
}

.related-links span {
    color: var(--muted);
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

.related-links a {
    border-bottom: 1px solid var(--text);
    font-size: 0.88rem;
    font-weight: 700;
    transition: color 0.2s, border-color 0.2s;
}

.related-links a:hover {
    color: var(--accent);
    border-color: var(--accent);
}

.resume-callout {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 30px;
    margin-top: 80px;
    padding: 35px;
    border: 1px solid var(--border);
}

.resume-callout .section-number {
    margin-bottom: 6px;
}

.project-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 15px;
}

.project-card {
    min-height: 350px;
    border: 1px solid var(--border);
    padding: 30px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: transform 0.2s, border-color 0.2s;
}

.project-card:hover {
    transform: translateY(-5px);
    border-color: var(--accent);
}

.project-card.featured {
    grid-column: span 2;
    min-height: 430px;
}

.project-number {
    font-family: monospace;
    color: var(--accent);
    margin-bottom: 80px;
}

.project-type {
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.15em;
    margin-bottom: 8px;
}

.project-card h3 {
    font-size: clamp(1.8rem, 3vw, 2.6rem);
    margin-bottom: 15px;
}

.project-meta {
    color: var(--accent);
    font-size: 0.9rem;
    font-weight: 700;
    margin: -6px 0 14px;
}

.project-card p {
    max-width: 600px;
}

.project-card .tags {
    margin-top: 25px;
}

.project-image {
    aspect-ratio: 16 / 10;
    margin-bottom: 28px;
    overflow: hidden;
    border: 1px solid var(--border);
    background: var(--surface);
}

.project-image img {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.photo-card img {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: contain;
    background: var(--gray-900);
}

.photo-intro {
    max-width: 700px;
    margin-top: -25px;
    margin-bottom: 35px;
    font-size: 1.05rem;
}

.photo-groups {
    display: flex;
    flex-direction: column;
    gap: 70px;
}

.photo-group {
    border-top: 1px solid var(--border);
    padding-top: 30px;
}

.photo-group-header {
    display: grid;
    grid-template-columns: minmax(220px, 0.42fr) 1fr;
    gap: 35px;
    margin-bottom: 24px;
}

.photo-group-header h3 {
    font-size: clamp(1.55rem, 3vw, 2.2rem);
}

.photo-group-header p {
    max-width: 760px;
}

.photo-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 15px;
}

.photo-card {
    border: 1px solid var(--border);
    background: var(--background);
}

.photo-card.featured {
    grid-column: span 2;
}

.photo-card img {
    aspect-ratio: 4 / 3;
}

.photo-card.featured img {
    aspect-ratio: 16 / 9;
}

.photo-card figcaption {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 16px;
}

.photo-card strong {
    line-height: 1.2;
}

.photo-card span {
    color: var(--muted);
    font-size: 0.9rem;
}

.photo-card .related-links {
    margin-top: 8px;
}

.passion-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    border-top: 1px solid var(--border);
}

.passion {
    padding: 40px;
    min-height: 260px;
    border-right: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
}

.passion:nth-child(even) {
    border-right: none;
}

.passion-number {
    display: block;
    font-family: monospace;
    color: var(--accent);
    margin-bottom: 45px;
}

.passion h3 {
    margin-bottom: 15px;
}

.contact-section {
    min-height: 70vh;
    display: flex;
    align-items: center;
}

.contact-links {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
    margin-top: 40px;
}

.contact-links a {
    font-size: 1.2rem;
    font-weight: 700;
    border-bottom: 1px solid var(--text);
    transition: color 0.2s;
}

.contact-links a:hover {
    color: var(--accent);
}

footer {
    border-top: 1px solid var(--border);
    padding: 30px 0;
}

.footer-content {
    display: flex;
    justify-content: space-between;
    font-size: 0.85rem;
}

@media (max-width: 800px) {
    .section {
        padding: 80px 0;
    }

    .nav-links {
        display: none;
    }

    .hero {
        min-height: 85vh;
    }

    .experience-item {
        grid-template-columns: 1fr;
        gap: 15px;
    }

    .project-grid {
        grid-template-columns: 1fr;
    }

    .project-card.featured {
        grid-column: span 1;
    }

    .photo-grid {
        grid-template-columns: 1fr;
    }

    .photo-group-header {
        grid-template-columns: 1fr;
        gap: 10px;
    }

    .photo-card.featured {
        grid-column: span 1;
    }

    .passion-grid {
        grid-template-columns: 1fr;
    }

    .passion {
        border-right: none;
    }

    .resume-callout {
        flex-direction: column;
        align-items: flex-start;
    }

    .footer-content {
        flex-direction: column;
        gap: 8px;
    }
}
"""


def build_pdf(data: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    resume = data.get("resume")
    if not resume:
        raise ValueError("content/site.json must include a resume block")
    if len(resume.get("pages", [])) > 2:
        raise ValueError("Resume template supports a maximum of two pages")

    renderer = ResumeRenderer(output_path)
    renderer.draw(resume)


class ResumeRenderer:
    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path
        self.width, self.height = LETTER
        self.margin_x = 0.58 * inch
        self.top = self.height - 0.52 * inch
        self.bottom = 0.5 * inch
        self.content_width = self.width - (2 * self.margin_x)
        self.canvas = canvas.Canvas(str(output_path), pagesize=LETTER)
        self.resume_text = colors.HexColor("#151515")
        self.resume_muted = colors.HexColor("#737373")
        self.resume_accent = colors.HexColor("#ed761d")
        self.resume_border = colors.HexColor("#c4c4c4")
        self.styles = {
            "headline": ParagraphStyle(
                "headline",
                fontName="Helvetica",
                fontSize=9,
                leading=11,
                textColor=self.resume_muted,
            ),
            "body": ParagraphStyle(
                "body",
                fontName="Helvetica",
                fontSize=8.7,
                leading=10.5,
                textColor=self.resume_text,
            ),
            "bullet": ParagraphStyle(
                "bullet",
                fontName="Helvetica",
                fontSize=8.5,
                leading=10.2,
                leftIndent=10,
                bulletIndent=0,
                textColor=self.resume_text,
            ),
            "classic_profile": ParagraphStyle(
                "classic_profile",
                fontName="Helvetica",
                fontSize=10.5,
                leading=13,
                textColor=self.resume_text,
            ),
            "classic_body": ParagraphStyle(
                "classic_body",
                fontName="Helvetica",
                fontSize=8.3,
                leading=9.8,
                textColor=self.resume_muted,
            ),
            "classic_body_bold": ParagraphStyle(
                "classic_body_bold",
                fontName="Helvetica-Bold",
                fontSize=8.4,
                leading=9.8,
                textColor=self.resume_text,
            ),
            "classic_sidebar": ParagraphStyle(
                "classic_sidebar",
                fontName="Helvetica",
                fontSize=9.5,
                leading=11.2,
                textColor=self.resume_muted,
            ),
            "classic_bullet": ParagraphStyle(
                "classic_bullet",
                fontName="Helvetica",
                fontSize=8.1,
                leading=9.6,
                leftIndent=11,
                bulletIndent=0,
                textColor=self.resume_muted,
            ),
            "classic_title": ParagraphStyle(
                "classic_title",
                fontName="Helvetica-Bold",
                fontSize=18,
                leading=20,
                textColor=self.resume_text,
            ),
        }

    def draw(self, resume: dict) -> None:
        if resume.get("template") == "classic_sidebar":
            pages = resume.get("pages", [])
            self._draw_classic_sidebar(resume)
            for page_index, page in enumerate(pages[1:], start=2):
                self.canvas.showPage()
                self._draw_classic_content_page(resume, page, page_index)
            self.canvas.save()
            return

        pages = resume.get("pages", [])
        for page_index in range(2):
            page = pages[page_index] if page_index < len(pages) else {"title": "", "blocks": []}
            self._draw_page(resume, page, page_index + 1)
            if page_index == 0:
                self.canvas.showPage()
        self.canvas.save()

    def _draw_classic_sidebar(self, resume: dict) -> None:
        c = self.canvas
        margin_x = 0.52 * inch
        top = self.height - 0.58 * inch
        bottom = 0.42 * inch
        gutter = 0.35 * inch
        sidebar_width = 1.85 * inch
        main_width = self.width - (2 * margin_x) - gutter - sidebar_width
        sidebar_x = margin_x + main_width + gutter

        c.setFillColor(self.resume_text)
        c.setFont("Helvetica-Bold", 34)
        c.drawString(margin_x, top, str(resume.get("name", "")))

        contact_y = top + 4
        for contact in resume.get("contact", []):
            c.setFont("Helvetica-Bold" if "@" in str(contact) or "." in str(contact) and " " not in str(contact) else "Helvetica", 8.8)
            c.setFillColor(self.resume_accent if "@" in str(contact) or str(contact).endswith(".ca") else self.resume_text)
            c.drawString(sidebar_x, contact_y, str(contact))
            contact_y -= 12

        profile_y = top - 34
        self._draw_paragraph_at(
            str(resume.get("headline", "")),
            margin_x,
            profile_y,
            main_width + 0.25 * inch,
            "classic_profile",
            bottom,
            gap=0,
        )

        page = resume.get("pages", [{}])[0]
        main_blocks = [block for block in page.get("blocks", []) if block.get("column", "main") != "sidebar"]
        sidebar_blocks = [block for block in page.get("blocks", []) if block.get("column") == "sidebar"]

        y_main = top - 118
        for block in main_blocks:
            y_main = self._draw_classic_block(block, margin_x, y_main, main_width, bottom)
            y_main -= 8

        y_side = top - 118
        for block in sidebar_blocks:
            y_side = self._draw_classic_block(block, sidebar_x, y_side, sidebar_width, bottom, sidebar=True)
            y_side -= 26

    def _draw_classic_content_page(self, resume: dict, page: dict, page_number: int) -> None:
        c = self.canvas
        margin_x = 0.52 * inch
        top = self.height - 0.55 * inch
        bottom = 0.45 * inch
        width = self.width - (2 * margin_x)

        c.setFillColor(self.resume_text)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(margin_x, top, str(resume.get("name", "")))
        c.setFont("Helvetica", 8.2)
        c.setFillColor(self.resume_muted)
        c.drawRightString(self.width - margin_x, top + 1, f"Page {page_number} of {max(len(resume.get('pages', [])), page_number)}")

        c.setStrokeColor(self.resume_border)
        c.setLineWidth(0.7)
        c.line(margin_x, top - 11, self.width - margin_x, top - 11)

        y = top - 34
        if page.get("title"):
            c.setFillColor(self.resume_text)
            c.setFont("Helvetica-Bold", 23)
            c.drawString(margin_x, y, str(page["title"]))
            y -= 34

        for block in page.get("blocks", []):
            y = self._draw_classic_block(block, margin_x, y, width, bottom)
            y -= 11

    def _draw_classic_block(
        self,
        block: dict,
        x: float,
        y: float,
        width: float,
        bottom: float,
        sidebar: bool = False,
    ) -> float:
        y = self._draw_classic_heading(str(block.get("heading", "")), x, y, bottom)
        block_type = block.get("type", "section")
        if block_type == "skills":
            for group in block.get("groups", []):
                items = ", ".join(str(item) for item in group.get("items", []))
                y = self._draw_paragraph_at(items, x + 18, y, width - 18, "classic_body", bottom, bullet_text="-", gap=3)
            return y
        if block_type == "list":
            for item in block.get("items", []):
                text = item.get("text", item) if isinstance(item, dict) else item
                style = "classic_sidebar" if sidebar else "classic_body"
                y = self._draw_paragraph_at(str(text), x, y, width, style, bottom, gap=9 if sidebar else 4)
            return y

        for item in block.get("items", []):
            y = self._draw_classic_item(item, x, y, width, bottom)
        return y

    def _draw_classic_heading(self, heading: str, x: float, y: float, bottom: float) -> float:
        if y - 14 < bottom:
            raise RuntimeError(f"Resume overflowed before heading {heading!r}. Shorten content/site.json.")
        self.canvas.setFillColor(self.resume_accent)
        self.canvas.setFont("Helvetica-Bold", 10)
        self.canvas.drawString(x, y, heading.upper())
        return y - 20

    def _draw_classic_item(self, item: dict, x: float, y: float, width: float, bottom: float) -> float:
        org = str(item.get("organization", ""))
        loc = str(item.get("location", ""))
        role = str(item.get("role", ""))
        dates = str(item.get("dates", ""))
        left = ", ".join(part for part in [org, loc] if part)
        meta_parts = []
        if left:
            meta_parts.append(f"<b>{html.escape(left, quote=False)}</b>")
        if role:
            meta_parts.append(html.escape(role, quote=False))
        if dates:
            meta_parts.append(f"<i>{html.escape(dates, quote=False)}</i>")
        y = self._draw_paragraph_at(" - ".join(meta_parts), x, y, width, "classic_body", bottom, allow_markup=True, gap=3)

        for bullet in item.get("bullets", []):
            style = "classic_body_bold" if str(bullet).startswith("2nd Year") else "classic_bullet"
            y = self._draw_paragraph_at(str(bullet), x + 18, y, width - 18, style, bottom, bullet_text="-", gap=1)
        return y - 6

    def _draw_paragraph_at(
        self,
        text: str,
        x: float,
        y: float,
        width: float,
        style_name: str,
        bottom: float,
        gap: float = 4,
        bullet_text: str | None = None,
        allow_markup: bool = False,
    ) -> float:
        if not text:
            return y
        paragraph_text = text if allow_markup else html.escape(text, quote=False)
        paragraph = Paragraph(paragraph_text, self.styles[style_name], bulletText=bullet_text)
        _, height = paragraph.wrap(width, y - bottom)
        if y - height - gap < bottom:
            raise RuntimeError("Resume page overflowed. Shorten content/site.json to fit the classic one-page template.")
        paragraph.drawOn(self.canvas, x, y - height)
        return y - height - gap

    def _draw_page(self, resume: dict, page: dict, page_number: int) -> None:
        c = self.canvas
        y = self.top

        c.setFillColor(self.resume_text)
        c.setFont("Helvetica-Bold", 20)
        c.drawString(self.margin_x, y, str(resume.get("name", "[insert name]")))
        c.setFont("Helvetica", 9)
        c.setFillColor(self.resume_muted)
        c.drawRightString(self.width - self.margin_x, y + 1, f"Page {page_number} of 2")
        y -= 16

        y = self._draw_paragraph(str(resume.get("headline", "")), y, "headline", page_number, gap=5)
        contact = "  |  ".join(str(item) for item in resume.get("contact", []) if item)
        y = self._draw_paragraph(contact, y, "headline", page_number, gap=12)

        c.setStrokeColor(self.resume_accent)
        c.setLineWidth(1.3)
        c.line(self.margin_x, y, self.width - self.margin_x, y)
        y -= 14

        if page.get("title"):
            c.setFont("Helvetica-Bold", 8.5)
            c.setFillColor(self.resume_accent)
            c.drawString(self.margin_x, y, str(page["title"]).upper())
            y -= 18

        for block in page.get("blocks", []):
            y = self._draw_block(block, y, page_number)

        c.setStrokeColor(self.resume_border)
        c.setLineWidth(0.6)
        c.line(self.margin_x, self.bottom - 5, self.width - self.margin_x, self.bottom - 5)

    def _draw_block(self, block: dict, y: float, page_number: int) -> float:
        block_type = block.get("type", "section")
        y = self._draw_heading(str(block.get("heading", "[insert section heading]")), y, page_number)
        if block_type == "skills":
            for group in block.get("groups", []):
                label = html.escape(str(group.get("label", "[insert skill group]")), quote=False)
                items = html.escape(", ".join(str(item) for item in group.get("items", [])), quote=False)
                text = f"<b>{label}:</b> {items}"
                y = self._draw_paragraph(text, y, "body", page_number, gap=4, allow_markup=True)
            return y - 7

        for item in block.get("items", []):
            y = self._draw_resume_item(item, y, page_number)
        return y - 4

    def _draw_heading(self, heading: str, y: float, page_number: int) -> float:
        y = self._ensure_space(y, 22, page_number)
        self.canvas.setFillColor(self.resume_text)
        self.canvas.setFont("Helvetica-Bold", 10.5)
        self.canvas.drawString(self.margin_x, y, heading.upper())
        self.canvas.setStrokeColor(self.resume_border)
        self.canvas.setLineWidth(0.5)
        self.canvas.line(self.margin_x, y - 4, self.width - self.margin_x, y - 4)
        return y - 16

    def _draw_resume_item(self, item: dict, y: float, page_number: int) -> float:
        title = str(item.get("role", "[insert role or project title]"))
        org = str(item.get("organization", "[insert organization]"))
        location = str(item.get("location", ""))
        dates = str(item.get("dates", "[insert dates]"))
        meta = " | ".join(part for part in [org, location] if part)

        y = self._ensure_space(y, 36, page_number)
        self.canvas.setFillColor(self.resume_text)
        self.canvas.setFont("Helvetica-Bold", 9.4)
        self.canvas.drawString(self.margin_x, y, title)
        self.canvas.setFont("Helvetica", 8.4)
        self.canvas.setFillColor(self.resume_muted)
        self.canvas.drawRightString(self.width - self.margin_x, y, dates)
        y -= 10

        y = self._draw_paragraph(meta, y, "headline", page_number, gap=4)
        for bullet in item.get("bullets", []):
            y = self._draw_paragraph(str(bullet), y, "bullet", page_number, gap=2, bullet_text="-")
        return y - 6

    def _draw_paragraph(
        self,
        text: str,
        y: float,
        style_name: str,
        page_number: int,
        gap: float = 4,
        bullet_text: str | None = None,
        allow_markup: bool = False,
    ) -> float:
        if not text:
            return y
        paragraph_text = text if allow_markup else html.escape(text, quote=False)
        paragraph = Paragraph(paragraph_text, self.styles[style_name], bulletText=bullet_text)
        _, height = paragraph.wrap(self.content_width, y - self.bottom)
        y = self._ensure_space(y, height + gap, page_number)
        paragraph.drawOn(self.canvas, self.margin_x, y - height)
        return y - height - gap

    def _ensure_space(self, y: float, needed: float, page_number: int) -> float:
        if y - needed < self.bottom:
            raise RuntimeError(
                f"Resume page {page_number} overflowed. Shorten blocks in content/site.json to keep the resume at two pages."
            )
        return y


def main() -> None:
    data = load_content()
    INDEX_PATH.write_text(render_index(data), encoding="utf-8", newline="\n")
    STYLES_PATH.write_text(render_styles(), encoding="utf-8", newline="\n")
    build_pdf(data, ROOT / data["site"]["resume_path"])
    print(f"Built {INDEX_PATH.relative_to(ROOT)}, {STYLES_PATH.relative_to(ROOT)}, and {data['site']['resume_path']}")


if __name__ == "__main__":
    main()
