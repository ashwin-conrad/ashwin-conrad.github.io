"""HTML, CSS, and small interaction layer for the engineering portfolio.

The narrative content stays in the manifest-backed ``content/details/``
collection under ``portfolio``; this module deliberately contains presentation
logic only.
"""

from __future__ import annotations

import html

from design_tokens import render_css_variables


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def attrs(values: dict[str, str | None]) -> str:
    rendered = [f'{key}="{esc(value)}"' for key, value in values.items() if value]
    return f" {' '.join(rendered)}" if rendered else ""


def render_engineering_index(data: dict) -> str:
    site = data["site"]
    identity = data["identity"]
    portfolio = data["portfolio"]
    hero = portfolio["hero"]
    nav_markup = "\n".join(
        f'                <a href="{esc(item["href"])}">{esc(item["label"])}</a>'
        for item in data["navigation"]
    )
    hero_facts = "\n".join(f"                    <li>{esc(fact)}</li>" for fact in hero["facts"])

    return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="{esc(site['meta_description'])}">
    <meta name="theme-color" content="#17201f">
    <meta property="og:title" content="{esc(site['social_title'])}">
    <meta property="og:description" content="{esc(site['social_description'])}">
    <meta property="og:type" content="website">
    <meta property="og:image" content="{esc(site['social_image'])}">
    <title>{esc(site['title'])}</title>
    <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='10' fill='%2317201f'/%3E%3Cpath d='M15 45 28 17h8l13 28h-9l-3-7H26l-3 7h-8Zm14-14h5l-2.5-7-2.5 7Z' fill='%23dd5e31'/%3E%3C/svg%3E">
    <link rel="stylesheet" href="styles.css">
    <script src="script.js" defer></script>
</head>
<body>
    <a class="skip-link" href="#main">Skip to content</a>
    <header class="site-header">
        <nav class="site-nav container" aria-label="Primary navigation">
            <a class="brand" href="#top" aria-label="{esc(identity['name'])}, home"><span>{esc(identity['initials'])}</span><i></i></a>
            <div class="nav-links">
{nav_markup}
            </div>
            <a class="nav-resume" href="{esc(site['resume_path'])}" target="_blank" rel="noreferrer">Résumé PDF <span aria-hidden="true">↗</span></a>
        </nav>
    </header>

    <main id="main">
        <section class="hero" id="top" aria-labelledby="hero-title">
            <div class="container hero-grid">
                <div class="hero-copy">
                    <p class="kicker">{esc(hero['eyebrow'])}</p>
                    <h1 id="hero-title">{esc(hero['title'])}</h1>
                    <p class="hero-intro">{esc(hero['description'])}</p>
                    <div class="hero-actions">
                        <a class="button button-primary" href="#projects">View featured work <span aria-hidden="true">↓</span></a>
                        <a class="button button-quiet" href="{esc(site['resume_path'])}" target="_blank" rel="noreferrer">Open résumé <span aria-hidden="true">↗</span></a>
                    </div>
                    <ul class="hero-facts" aria-label="Current roles and education">
{hero_facts}
                    </ul>
                </div>
                {render_hero_figure(hero['image'])}
            </div>
        </section>

        {render_profile(portfolio['profile'])}
        {render_case_studies(portfolio['case_studies'])}
        {render_experience(portfolio['experience'])}
        {render_skills(portfolio['skills'])}
        {render_documentation(portfolio['documentation'])}
        {render_leadership(portfolio['leadership'])}
        {render_personal_builds(portfolio['personal_builds'])}
        {render_resume(portfolio, site['resume_path'])}
        {render_contact(portfolio['contact'])}
    </main>

    <footer class="site-footer">
        <div class="container footer-content">
            <p>© {esc(site['year'])} {esc(identity['name'])}</p>
            <p>Mechanical engineering · vehicle systems · manufacturing</p>
            <a href="#top">Back to top <span aria-hidden="true">↑</span></a>
        </div>
    </footer>

    <dialog class="lightbox" aria-labelledby="lightbox-caption">
        <form method="dialog"><button class="lightbox-close" aria-label="Close enlarged image">×</button></form>
        <img src="" alt="">
        <p id="lightbox-caption"></p>
    </dialog>
</body>
</html>
"""


def render_hero_figure(image: dict) -> str:
    return f"""                <figure class="hero-figure figure-trigger">
                    <button type="button" data-lightbox-src="{esc(image['src'])}" data-lightbox-alt="{esc(image['alt'])}" data-lightbox-caption="Formula EV work: low-voltage hardware in its vehicle and competition context." aria-label="Open Formula EV low-voltage hardware photo">
                        <img src="{esc(image['src'])}" alt="{esc(image['alt'])}">
                    </button>
                    <figcaption><span>FIG. 01</span> Formula EV low-voltage hardware in competition context.</figcaption>
                </figure>"""


def render_profile(profile: dict) -> str:
    signals = "\n".join(
        f"""                    <article class="profile-signal">
                        <p class="micro-label">{esc(signal['label'])}</p>
                        <p>{esc(signal['text'])}</p>
                    </article>"""
        for signal in profile["signals"]
    )
    return f"""        <section class="section profile-section" id="profile" aria-labelledby="profile-heading">
            <div class="container">
                <div class="section-heading split-heading">
                    <div>
                        <p class="section-label">{esc(profile['number'])}</p>
                        <h2 id="profile-heading">{esc(profile['heading'])}</h2>
                    </div>
                    <div class="section-summary">
                        <p class="lead">{esc(profile['lead'])}</p>
                        <p>{esc(profile['body'])}</p>
                    </div>
                </div>
                <div class="profile-signals">
{signals}
                </div>
            </div>
        </section>"""


def render_case_studies(case_studies: list[dict]) -> str:
    studies = "\n".join(render_case_study(study) for study in case_studies)
    return f"""        <section class="projects-section" id="projects" aria-labelledby="projects-heading">
            <div class="container projects-intro">
                <p class="section-label">FEATURED ENGINEERING PROJECTS</p>
                <h2 id="projects-heading">Evidence of engineering judgement.</h2>
                <p>Each case study tracks the technical objective, contribution, constraints, process, and the evidence available today. Missing artifacts are called out intentionally.</p>
            </div>
{studies}
        </section>"""


def render_case_study(study: dict) -> str:
    metadata = "\n".join(
        f"""                        <div><dt>{esc(item['label'])}</dt><dd>{esc(item['value'])}</dd></div>"""
        for item in study["metadata"]
    )
    constraints = "".join(f"<li>{esc(item)}</li>" for item in study["constraints"])
    process = "\n".join(
        f"                        <li><span>{index:02d}</span>{esc(item)}</li>"
        for index, item in enumerate(study["process"], start=1)
    )
    results = "\n".join(f"                            <li>{esc(result)}</li>" for result in study["results"])
    tools = "".join(f"<span>{esc(tool)}</span>" for tool in study["tools"])
    figures = "\n".join(render_project_figure(figure) for figure in study.get("figures", []))
    placeholders = "\n".join(f"                    <div class=\"asset-needed\">{esc(item)}</div>" for item in study.get("placeholders", []))
    return f"""            <article class="case-study" id="project-{esc(study['id'])}" aria-labelledby="{esc(study['id'])}-title">
                <div class="container">
                    <div class="case-study-header">
                        <div>
                            <p class="section-label">{esc(study['number'])}</p>
                            <p class="project-type">{esc(study['type'])}</p>
                            <h2 id="{esc(study['id'])}-title">{esc(study['title'])}</h2>
                        </div>
                        <p class="case-study-subtitle">{esc(study['subtitle'])}</p>
                    </div>
                    {render_feature_figure(study['image'], study['title'])}
                    <dl class="project-metadata">
{metadata}
                    </dl>
                    <div class="case-study-summary">
                        <div>
                            <p class="micro-label">ENGINEERING OBJECTIVE</p>
                            <p>{esc(study['objective'])}</p>
                        </div>
                        <div>
                            <p class="micro-label">CONTEXT</p>
                            <p>{esc(study['context'])}</p>
                        </div>
                        <div>
                            <p class="micro-label">MY CONTRIBUTION</p>
                            <p>{esc(study['contribution'])}</p>
                        </div>
                    </div>
                    <div class="study-details">
                        <div class="constraint-panel">
                            <p class="micro-label">DESIGN CONSTRAINTS</p>
                            <ul>{constraints}</ul>
                        </div>
                        <div class="process-panel">
                            <p class="micro-label">ENGINEERING PROCESS</p>
                            <ol>
{process}
                            </ol>
                        </div>
                    </div>
                    <aside class="engineering-callout">
                        <p class="micro-label">{esc(study['decision']['label'])}</p>
                        <h3>{esc(study['decision']['title'])}</h3>
                        <p>{esc(study['decision']['text'])}</p>
                    </aside>
                    <div class="results-grid">
                        <div>
                            <p class="micro-label">CURRENT RESULT / OUTCOME</p>
                            <ul>
{results}
                            </ul>
                        </div>
                        <div>
                            <p class="micro-label">METHODS & TOOLS</p>
                            <div class="tool-list">{tools}</div>
                        </div>
                    </div>
                    <div class="case-figures">
{figures}
                    </div>
{placeholders}
                </div>
            </article>"""


def render_feature_figure(image: dict, title: str) -> str:
    return f"""                    <figure class="feature-figure figure-trigger">
                        <button type="button" data-lightbox-src="{esc(image['src'])}" data-lightbox-alt="{esc(image['alt'])}" data-lightbox-caption="{esc(title)}">
                            <img src="{esc(image['src'])}" alt="{esc(image['alt'])}" loading="lazy" decoding="async">
                        </button>
                    </figure>"""


def render_project_figure(figure: dict) -> str:
    return f"""                        <figure class="engineering-figure figure-trigger">
                            <button type="button" data-lightbox-src="{esc(figure['src'])}" data-lightbox-alt="{esc(figure['alt'])}" data-lightbox-caption="{esc(figure['caption'])}">
                                <img src="{esc(figure['src'])}" alt="{esc(figure['alt'])}" loading="lazy" decoding="async">
                            </button>
                            <figcaption>{esc(figure['caption'])}</figcaption>
                        </figure>"""


def render_experience(experience: dict) -> str:
    items = "\n".join(
        f"""                    <article class="experience-row">
                        <p class="experience-date">{esc(item['date'])}</p>
                        <div>
                            <h3>{esc(item['role'])}</h3>
                            <p class="experience-org">{esc(item['organization'])}</p>
                            <p>{esc(item['text'])}</p>
                            <div class="tag-list">{''.join(f'<span>{esc(tag)}</span>' for tag in item['tags'])}</div>
                        </div>
                    </article>"""
        for item in experience["items"]
    )
    return f"""        <section class="section experience-section" id="experience" aria-labelledby="experience-heading">
            <div class="container">
                <div class="section-heading">
                    <p class="section-label">{esc(experience['number'])}</p>
                    <h2 id="experience-heading">{esc(experience['heading'])}</h2>
                </div>
                <div class="experience-list">
{items}
                </div>
            </div>
        </section>"""


def render_skills(skills: dict) -> str:
    groups = "\n".join(
        f"""                    <article class="skill-group">
                        <h3>{esc(group['title'])}</h3>
                        <ul>{''.join(f'<li>{esc(item)}</li>' for item in group['items'])}</ul>
                    </article>"""
        for group in skills["groups"]
    )
    return f"""        <section class="section skills-section" aria-labelledby="skills-heading">
            <div class="container">
                <div class="section-heading split-heading">
                    <div>
                        <p class="section-label">{esc(skills['number'])}</p>
                        <h2 id="skills-heading">{esc(skills['heading'])}</h2>
                    </div>
                    <p class="section-summary">These are working contexts, not percentage bars. Each is supported by the experience and project evidence above.</p>
                </div>
                <div class="skills-grid">
{groups}
                </div>
            </div>
        </section>"""


def render_documentation(documentation: dict) -> str:
    items = "\n".join(
        f"""                    <figure class="documentation-card{' documentation-card-wide' if item.get('wide') else ''} figure-trigger">
                        <button type="button" data-lightbox-src="{esc(item['src'])}" data-lightbox-alt="{esc(item['alt'])}" data-lightbox-caption="{esc(item['figure'])} — {esc(item['title'])}. {esc(item['caption'])}">
                            <img src="{esc(item['src'])}" alt="{esc(item['alt'])}" loading="lazy" decoding="async">
                        </button>
                        <figcaption><span>{esc(item['figure'])}</span><strong>{esc(item['title'])}</strong><p>{esc(item['caption'])}</p></figcaption>
                    </figure>"""
        for item in documentation["items"]
    )
    return f"""        <section class="section documentation-section" id="documentation" aria-labelledby="documentation-heading">
            <div class="container">
                <div class="section-heading split-heading">
                    <div>
                        <p class="section-label">{esc(documentation['number'])}</p>
                        <h2 id="documentation-heading">{esc(documentation['heading'])}</h2>
                    </div>
                    <p class="section-summary">{esc(documentation['intro'])}</p>
                </div>
                <div class="documentation-grid">
{items}
                </div>
            </div>
        </section>"""


def render_leadership(leadership: dict) -> str:
    items = "\n".join(
        f"""                    <article class="leadership-item"><span>{index:02d}</span><div><h3>{esc(item['title'])}</h3><p>{esc(item['text'])}</p></div></article>"""
        for index, item in enumerate(leadership["items"], 1)
    )
    return f"""        <section class="section leadership-section" aria-labelledby="leadership-heading">
            <div class="container">
                <div class="section-heading split-heading">
                    <div>
                        <p class="section-label">{esc(leadership['number'])}</p>
                        <h2 id="leadership-heading">{esc(leadership['heading'])}</h2>
                    </div>
                    <p class="section-summary">Leadership is shown here through responsibilities and engineering communication, not generic labels.</p>
                </div>
                <div class="leadership-list">
{items}
                </div>
            </div>
        </section>"""


def render_personal_builds(personal_builds: dict) -> str:
    items = "\n".join(
        f"""                    <article class="personal-build"><img src="{esc(item['src'])}" alt="{esc(item['alt'])}" loading="lazy" decoding="async"><div><h3>{esc(item['title'])}</h3><p>{esc(item['text'])}</p></div></article>"""
        for item in personal_builds["items"]
    )
    return f"""        <section class="section personal-builds-section" aria-labelledby="builds-heading">
            <div class="container">
                <div class="section-heading">
                    <p class="section-label">{esc(personal_builds['number'])}</p>
                    <h2 id="builds-heading">{esc(personal_builds['heading'])}</h2>
                </div>
                <div class="personal-builds-grid">
{items}
                </div>
            </div>
        </section>"""


def render_resume(portfolio: dict, resume_path: str) -> str:
    return f"""        <section class="resume-section" id="resume" aria-labelledby="resume-heading">
            <div class="container resume-callout">
                <div>
                    <p class="section-label">RÉSUMÉ / SELECTED EXPERIENCE</p>
                    <h2 id="resume-heading">The concise version, ready to share.</h2>
                    <p>Download the résumé for a focused summary of education, engineering experience, selected projects, and technical skills.</p>
                </div>
                <a class="button button-primary" href="{esc(resume_path)}" target="_blank" rel="noreferrer">Download résumé PDF <span aria-hidden="true">↗</span></a>
            </div>
        </section>"""


def render_contact(contact: dict) -> str:
    links = "\n".join(
        f'                    <a href="{esc(link["href"])}"{attrs({"target": "_blank" if link.get("external") else None, "rel": "noreferrer" if link.get("external") else None})}>{esc(link["label"])} <span aria-hidden="true">↗</span></a>'
        for link in contact["links"]
    )
    return f"""        <section class="contact-section" id="contact" aria-labelledby="contact-heading">
            <div class="container contact-content">
                <p class="section-label">{esc(contact['number'])}</p>
                <h2 id="contact-heading">{esc(contact['heading'])}</h2>
                <p class="contact-lead">{esc(contact['lead'])}</p>
                <div class="contact-links">
{links}
                </div>
            </div>
        </section>"""


def render_engineering_styles(design_tokens: dict[str, str]) -> str:
    return r'''/* Generated by scripts/portfolio.py build. Edit content/design-tokens.json for visual foundations, content/details.json for content, and scripts/site_renderer.py for presentation. */
@import url("https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&family=Source+Serif+4:opsz,wght@8..60,600;8..60,700&display=swap");

:root {
__DESIGN_TOKENS__
    --mono: "DM Mono", ui-monospace, SFMono-Regular, Consolas, monospace;
    --sans: "Manrope", Arial, sans-serif;
    --serif: "Source Serif 4", Georgia, serif;
    --max: 1240px;
}

* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body { margin: 0; background: var(--paper); color: var(--ink); font-family: var(--sans); font-size: 16px; line-height: 1.65; }
img { display: block; width: 100%; }
a { color: inherit; }
button { font: inherit; }
.container { width: min(calc(100% - 48px), var(--max)); margin: 0 auto; }
.skip-link { position: fixed; top: 10px; left: 10px; z-index: 200; padding: 10px 14px; background: var(--white); border: 1px solid var(--ink); transform: translateY(-160%); }
.skip-link:focus { transform: translateY(0); }

.site-header { position: sticky; top: 0; z-index: 100; border-bottom: 1px solid color-mix(in srgb, var(--line) 85%, transparent); background: color-mix(in srgb, var(--paper) 92%, transparent); backdrop-filter: blur(12px); }
.site-nav { min-height: 68px; display: flex; align-items: center; gap: 26px; }
.brand { display: inline-flex; align-items: center; gap: 6px; margin-right: auto; font-family: var(--mono); font-size: .92rem; font-weight: 500; text-decoration: none; letter-spacing: -.04em; }
.brand span { display: grid; place-items: center; width: 33px; height: 33px; border: 1px solid var(--ink); background: var(--ink); color: var(--paper); }
.brand i { display: block; width: 6px; height: 6px; background: var(--orange); }
.nav-links { display: flex; align-items: center; gap: 21px; }
.nav-links a, .nav-resume { color: var(--ink-soft); font-size: .73rem; font-weight: 700; letter-spacing: .05em; text-decoration: none; text-transform: uppercase; }
.nav-links a:hover, .nav-resume:hover { color: var(--orange-dark); }
.nav-resume { border-left: 1px solid var(--line); padding-left: 22px; color: var(--ink); }
.nav-resume span { color: var(--orange); }

.hero { overflow: hidden; padding: clamp(50px, 7vw, 104px) 0 74px; background: var(--ink); color: var(--paper); }
.hero-grid { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(350px, .85fr); align-items: end; gap: clamp(40px, 7vw, 118px); }
.kicker, .section-label, .micro-label, .project-type { margin: 0; color: var(--orange); font-family: var(--mono); font-size: .68rem; font-weight: 500; letter-spacing: .095em; line-height: 1.35; text-transform: uppercase; }
.hero h1 { max-width: 760px; margin: 17px 0 25px; color: var(--white); font-family: var(--serif); font-size: clamp(3.4rem, 6.6vw, 6.9rem); font-weight: 600; letter-spacing: -.055em; line-height: .94; }
.hero-intro { max-width: 690px; margin: 0; color: #d9d8d1; font-size: clamp(1.05rem, 1.55vw, 1.25rem); line-height: 1.65; }
.hero-actions { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 34px; }
.button { display: inline-flex; align-items: center; justify-content: center; gap: 12px; min-height: 45px; padding: 10px 17px; border: 1px solid var(--ink); font-size: .8rem; font-weight: 800; letter-spacing: .015em; text-decoration: none; transition: background .16s ease, color .16s ease, border-color .16s ease, transform .16s ease; }
.button:hover { transform: translateY(-2px); }
.button-primary { border-color: var(--orange); background: var(--orange); color: #231612; }
.button-primary:hover { background: #ec7450; border-color: #ec7450; }
.button-quiet { border-color: #8c918b; color: var(--white); }
.button-quiet:hover { border-color: var(--white); background: var(--white); color: var(--ink); }
.hero-facts { display: flex; flex-wrap: wrap; gap: 8px 20px; margin: 38px 0 0; padding: 0; list-style: none; color: #b8bcb6; font-family: var(--mono); font-size: .67rem; }
.hero-facts li { position: relative; padding-left: 12px; }
.hero-facts li::before { position: absolute; left: 0; color: var(--orange); content: "•"; }
.hero-figure { position: relative; max-width: 430px; margin: 0 0 0 auto; }
.hero-figure::before { position: absolute; z-index: 0; top: -18px; right: -18px; width: 64%; height: 53%; border: 1px solid #5f6d65; content: ""; }
.figure-trigger { margin: 0; }
.figure-trigger button { display: block; width: 100%; padding: 0; border: 0; background: none; cursor: zoom-in; }
.hero-figure button { position: relative; z-index: 1; overflow: hidden; }
.hero-figure img { aspect-ratio: .82; object-fit: cover; object-position: center 31%; filter: saturate(.86) contrast(1.03); }
.hero-figure figcaption { position: relative; z-index: 1; margin: 12px 0 0; color: #b8bcb6; font-size: .72rem; }
.hero-figure figcaption span { margin-right: 7px; color: var(--orange); font-family: var(--mono); font-size: .66rem; }

.section { padding: clamp(78px, 10vw, 150px) 0; }
.section-heading { max-width: 830px; margin-bottom: 44px; }
.split-heading { display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(290px, .95fr); gap: 50px; max-width: none; }
h2 { margin: 13px 0 0; color: var(--ink); font-family: var(--serif); font-size: clamp(2.5rem, 4.6vw, 5.1rem); font-weight: 600; letter-spacing: -.055em; line-height: .99; }
h3 { margin: 0; font-family: var(--serif); font-size: 1.55rem; font-weight: 600; letter-spacing: -.03em; line-height: 1.1; }
p { margin: 0; }
.section-summary { align-self: end; color: var(--muted); font-size: 1rem; }
.section-summary .lead, .lead { margin-bottom: 18px; color: var(--ink); font-size: 1.2rem; line-height: 1.55; }
.profile-section { position: relative; background: var(--paper); }
.profile-signals { display: grid; grid-template-columns: repeat(3, 1fr); margin-top: 72px; border-top: 1px solid var(--ink); }
.profile-signal { min-height: 205px; padding: 27px 26px 20px 0; border-right: 1px solid var(--line); }
.profile-signal + .profile-signal { padding-left: 27px; }
.profile-signal:last-child { border-right: 0; }
.profile-signal > p:last-child { max-width: 340px; margin-top: 15px; color: var(--muted); font-size: .93rem; }

.projects-section { border-top: 1px solid var(--line); }
.projects-intro { padding: clamp(78px, 10vw, 140px) 0 clamp(45px, 6vw, 80px); }
.projects-intro h2 { max-width: 680px; }
.projects-intro > p:last-child { max-width: 700px; margin-top: 22px; color: var(--muted); }
.case-study { padding: clamp(65px, 9vw, 120px) 0; border-top: 1px solid var(--line); }
.case-study:nth-of-type(odd) { background: var(--paper-deep); }
.case-study-header { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(290px, .8fr); align-items: end; gap: 50px; margin-bottom: 42px; }
.case-study h2 { max-width: 700px; font-size: clamp(2.8rem, 5.5vw, 5.6rem); }
.project-type { margin-top: 20px; color: var(--green); }
.case-study-subtitle { max-width: 450px; color: var(--muted); font-size: 1.12rem; line-height: 1.58; }
.feature-figure { margin: 0; overflow: hidden; border: 1px solid var(--line-dark); background: var(--ink); }
.feature-figure img { height: min(50vw, 552px); object-fit: cover; transition: transform .35s ease; }
.feature-figure button:hover img, .engineering-figure button:hover img, .documentation-card button:hover img { transform: scale(1.025); }
.project-metadata { display: grid; grid-template-columns: repeat(4, 1fr); margin: 0; border-bottom: 1px solid var(--line); }
.project-metadata div { min-height: 91px; padding: 20px 18px 20px 0; border-right: 1px solid var(--line); }
.project-metadata div + div { padding-left: 19px; }
.project-metadata div:last-child { border-right: 0; }
.project-metadata dt { color: var(--muted); font-family: var(--mono); font-size: .63rem; letter-spacing: .085em; }
.project-metadata dd { margin: 7px 0 0; color: var(--ink); font-size: .82rem; font-weight: 700; line-height: 1.4; }
.case-study-summary { display: grid; grid-template-columns: repeat(3, 1fr); gap: 42px; padding: 48px 0; }
.case-study-summary > div { padding-right: 15px; }
.case-study-summary > div + div { border-left: 1px solid var(--line); padding-left: 41px; }
.case-study-summary p:last-child { margin-top: 12px; color: var(--ink-soft); font-size: .94rem; line-height: 1.7; }
.study-details { display: grid; grid-template-columns: .75fr 1.25fr; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
.constraint-panel, .process-panel { padding: 30px 32px 30px 0; }
.process-panel { border-left: 1px solid var(--line); padding-left: 32px; }
.constraint-panel ul { display: flex; flex-wrap: wrap; gap: 8px; margin: 15px 0 0; padding: 0; list-style: none; }
.constraint-panel li, .tool-list span, .tag-list span { padding: 4px 8px; border: 1px solid var(--line-dark); color: var(--ink-soft); font-family: var(--mono); font-size: .65rem; line-height: 1.4; }
.process-panel ol { display: grid; grid-template-columns: repeat(5, 1fr); gap: 0; margin: 17px 0 0; padding: 0; list-style: none; }
.process-panel li { position: relative; padding-right: 15px; color: var(--ink-soft); font-size: .76rem; line-height: 1.45; }
.process-panel li + li { padding-left: 14px; border-left: 1px solid var(--line); }
.process-panel li span { display: block; margin-bottom: 7px; color: var(--orange); font-family: var(--mono); font-size: .61rem; }
.engineering-callout { margin: 44px 0; padding: 30px 34px; border-left: 4px solid var(--orange); background: color-mix(in srgb, var(--green-light) 55%, transparent); }
.engineering-callout h3 { margin-top: 11px; font-size: clamp(1.55rem, 2.5vw, 2.4rem); }
.engineering-callout p:last-child { max-width: 930px; margin-top: 12px; color: var(--ink-soft); }
.results-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 45px; margin: 45px 0; }
.results-grid > div { min-height: 112px; }
.results-grid > div + div { border-left: 1px solid var(--line); padding-left: 45px; }
.results-grid ul { margin: 13px 0 0; padding-left: 18px; color: var(--ink-soft); font-size: .93rem; }
.results-grid li + li { margin-top: 8px; }
.tool-list { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 14px; }
.tool-list span { background: var(--white); }
.case-figures { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; }
.engineering-figure { margin: 0; }
.engineering-figure button { overflow: hidden; background: var(--ink); }
.engineering-figure img { aspect-ratio: 1.45; object-fit: cover; transition: transform .35s ease; }
.engineering-figure figcaption { margin-top: 11px; color: var(--muted); font-size: .76rem; line-height: 1.52; }
.asset-needed { margin-top: 12px; padding: 12px 14px; border: 1px dashed var(--line-dark); color: var(--muted); font-family: var(--mono); font-size: .66rem; line-height: 1.5; }

.experience-section { background: var(--green); color: var(--paper); }
.experience-section h2 { color: var(--paper); }
.experience-section .section-label { color: #eb8d71; }
.experience-list { border-top: 1px solid #62766c; }
.experience-row { display: grid; grid-template-columns: 190px 1fr; gap: 50px; padding: 36px 0; border-bottom: 1px solid #62766c; }
.experience-date { color: #b9c8bf; font-family: var(--mono); font-size: .72rem; }
.experience-row h3 { font-size: clamp(1.55rem, 2.4vw, 2.25rem); color: var(--white); }
.experience-org { margin: 5px 0 16px; color: #eb8d71; font-family: var(--mono); font-size: .72rem; }
.experience-row p:not(.experience-date):not(.experience-org) { max-width: 770px; color: #d3dbd4; font-size: .95rem; }
.tag-list { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 18px; }
.tag-list span { border-color: #759184; color: #d6e0d9; }

.skills-section { background: var(--white); }
.skills-grid { display: grid; grid-template-columns: repeat(3, 1fr); border-top: 1px solid var(--ink); border-left: 1px solid var(--line); }
.skill-group { min-height: 210px; padding: 25px; border-right: 1px solid var(--line); border-bottom: 1px solid var(--line); }
.skill-group h3 { font-size: 1.2rem; }
.skill-group ul { margin: 18px 0 0; padding: 0; list-style: none; color: var(--muted); font-size: .86rem; }
.skill-group li + li { margin-top: 5px; }
.skill-group li::before { margin-right: 7px; color: var(--orange); content: "—"; }

.documentation-section { background: var(--paper-deep); }
.documentation-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; }
.documentation-card { margin: 0; border: 1px solid var(--line); background: var(--paper); }
.documentation-card-wide { grid-column: span 2; }
.documentation-card button { overflow: hidden; background: var(--ink); }
.documentation-card img { aspect-ratio: 1.25; object-fit: cover; transition: transform .35s ease; }
.documentation-card-wide img { aspect-ratio: 1.95; }
.documentation-card figcaption { padding: 16px 17px 19px; }
.documentation-card figcaption span { display: block; margin-bottom: 6px; color: var(--orange-dark); font-family: var(--mono); font-size: .62rem; }
.documentation-card figcaption strong { font-family: var(--serif); font-size: 1.18rem; font-weight: 600; }
.documentation-card figcaption p { margin-top: 7px; color: var(--muted); font-size: .77rem; line-height: 1.5; }

.leadership-section { background: var(--ink); color: var(--paper); }
.leadership-section h2 { color: var(--paper); }
.leadership-section .section-summary { color: #b5bdb7; }
.leadership-list { border-top: 1px solid #59615c; }
.leadership-item { display: grid; grid-template-columns: 70px 1fr; gap: 28px; padding: 31px 0; border-bottom: 1px solid #59615c; }
.leadership-item > span { color: var(--orange); font-family: var(--mono); font-size: .7rem; }
.leadership-item h3 { color: var(--white); font-size: 1.6rem; }
.leadership-item p { max-width: 780px; margin-top: 8px; color: #c8d0ca; font-size: .95rem; }

.personal-builds-section { background: var(--paper); }
.personal-builds-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
.personal-build { background: var(--white); border: 1px solid var(--line); }
.personal-build img { aspect-ratio: 1.28; object-fit: cover; }
.personal-build > div { padding: 20px; }
.personal-build h3 { font-size: 1.35rem; }
.personal-build p { margin-top: 9px; color: var(--muted); font-size: .86rem; }

.resume-section { padding: clamp(75px, 9vw, 128px) 0; background: var(--orange); }
.resume-callout { display: grid; grid-template-columns: 1.15fr .85fr; align-items: end; gap: 55px; }
.resume-section .section-label { color: #57291c; }
.resume-section h2 { max-width: 720px; color: #271713; font-size: clamp(2.7rem, 4.7vw, 5rem); }
.resume-section p:last-child { max-width: 610px; margin-top: 17px; color: #49271d; }
.resume-section .button { justify-self: end; background: var(--ink); border-color: var(--ink); color: var(--paper); }
.resume-section .button:hover { background: var(--white); color: var(--ink); }

.contact-section { padding: clamp(85px, 11vw, 162px) 0; background: var(--white); }
.contact-content { max-width: 1010px; }
.contact-content h2 { max-width: 980px; font-size: clamp(2.8rem, 5.2vw, 5.7rem); }
.contact-lead { max-width: 720px; margin-top: 28px; color: var(--muted); font-size: 1.12rem; }
.contact-links { display: flex; flex-wrap: wrap; gap: 11px; margin-top: 37px; }
.contact-links a { padding: 9px 12px; border-bottom: 1px solid var(--ink); font-family: var(--mono); font-size: .75rem; text-decoration: none; }
.contact-links a:hover { border-color: var(--orange); color: var(--orange-dark); }
.contact-links span { color: var(--orange); }
.site-footer { padding: 22px 0; border-top: 1px solid var(--line); background: var(--paper); }
.footer-content { display: flex; justify-content: space-between; gap: 24px; color: var(--muted); font-family: var(--mono); font-size: .65rem; }
.footer-content a { text-decoration: none; color: var(--ink); }
.footer-content a span { color: var(--orange); }

.lightbox { width: min(1100px, calc(100% - 32px)); max-height: calc(100vh - 32px); padding: 0; overflow: auto; border: 1px solid #53605a; background: var(--ink); color: var(--white); }
.lightbox::backdrop { background: rgb(5 9 8 / .82); backdrop-filter: blur(4px); }
.lightbox form { position: sticky; z-index: 1; top: 0; display: flex; justify-content: flex-end; height: 0; }
.lightbox-close { display: grid; place-items: center; width: 38px; height: 38px; margin: 10px; border: 1px solid #8c9690; border-radius: 100%; background: var(--ink); color: var(--white); cursor: pointer; font-size: 1.8rem; line-height: 1; }
.lightbox-close:hover { background: var(--orange); color: var(--ink); }
.lightbox img { max-height: calc(100vh - 120px); object-fit: contain; }
.lightbox p { padding: 12px 18px 17px; color: #d0d6d1; font-size: .8rem; }

:focus-visible { outline: 3px solid var(--orange); outline-offset: 3px; }
@media (max-width: 1000px) {
    .nav-links { gap: 13px; }
    .nav-links a { font-size: .65rem; }
    .nav-resume { padding-left: 13px; font-size: .65rem; }
    .case-study-summary { gap: 25px; }
    .case-study-summary > div + div { padding-left: 25px; }
    .skills-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 760px) {
    .container { width: min(calc(100% - 32px), var(--max)); }
    .site-nav { min-height: 59px; }
    .nav-links { display: none; }
    .nav-resume { padding-left: 0; border-left: 0; }
    .hero { padding-bottom: 52px; }
    .hero-grid, .split-heading, .case-study-header, .resume-callout { grid-template-columns: 1fr; gap: 29px; }
    .hero h1 { font-size: clamp(3.05rem, 14vw, 5rem); }
    .hero-figure { max-width: 480px; margin: 10px 0 0; }
    .hero-figure img { aspect-ratio: 1.1; object-position: center 22%; }
    .profile-signals, .case-study-summary, .results-grid, .personal-builds-grid { grid-template-columns: 1fr; }
    .profile-signals { margin-top: 50px; }
    .profile-signal, .profile-signal + .profile-signal { min-height: auto; padding: 23px 0; border-right: 0; border-bottom: 1px solid var(--line); }
    .case-study h2 { font-size: clamp(2.65rem, 12vw, 4.3rem); }
    .feature-figure img { height: min(72vw, 430px); }
    .project-metadata { grid-template-columns: 1fr 1fr; }
    .project-metadata div:nth-child(2) { border-right: 0; }
    .project-metadata div:nth-child(n+3) { border-top: 1px solid var(--line); }
    .case-study-summary > div + div, .results-grid > div + div { padding-left: 0; border-left: 0; border-top: 1px solid var(--line); padding-top: 24px; }
    .case-study-summary { gap: 0; }
    .case-study-summary > div { padding: 25px 0; }
    .study-details { grid-template-columns: 1fr; }
    .process-panel { border-top: 1px solid var(--line); border-left: 0; padding: 27px 0; }
    .constraint-panel { padding: 27px 0; }
    .process-panel ol { grid-template-columns: 1fr; gap: 8px; }
    .process-panel li + li { padding-left: 0; border-left: 0; }
    .process-panel li span { display: inline; margin: 0 7px 0 0; }
    .engineering-callout { margin: 30px 0; padding: 24px; }
    .results-grid { gap: 0; margin: 30px 0; }
    .results-grid > div { padding: 0 0 25px; }
    .case-figures { grid-template-columns: 1fr; gap: 26px; }
    .experience-row { grid-template-columns: 1fr; gap: 9px; }
    .experience-row { padding: 29px 0; }
    .skills-grid { grid-template-columns: 1fr; }
    .documentation-grid { grid-template-columns: 1fr; }
    .documentation-card-wide { grid-column: span 1; }
    .documentation-card-wide img { aspect-ratio: 1.25; }
    .leadership-item { grid-template-columns: 38px 1fr; gap: 12px; }
    .resume-section .button { justify-self: start; }
    .footer-content { flex-direction: column; gap: 4px; }
}
@media print {
    .site-header, .hero-actions, .lightbox, .asset-needed { display: none; }
    body { background: white; font-size: 11pt; }
    .hero { padding: 30px 0; background: white; color: black; }
    .hero h1, .experience-section h2, .leadership-section h2 { color: black; }
    .hero-intro, .hero-facts, .experience-row p:not(.experience-date):not(.experience-org), .leadership-item p { color: #333; }
    .section, .case-study { padding: 32px 0; break-inside: avoid; }
    .experience-section, .leadership-section, .resume-section { background: white; color: black; }
    .documentation-grid, .personal-builds-grid { grid-template-columns: repeat(2, 1fr); }
}
'''.replace("__DESIGN_TOKENS__", render_css_variables(design_tokens))


def render_site_script() -> str:
    return '''/* Image lightbox: intentionally small and dependency-free. */
document.addEventListener("DOMContentLoaded", () => {
  const dialog = document.querySelector(".lightbox");
  if (!dialog) return;
  const image = dialog.querySelector("img");
  const caption = dialog.querySelector("#lightbox-caption");

  document.querySelectorAll("[data-lightbox-src]").forEach((button) => {
    button.addEventListener("click", () => {
      image.src = button.dataset.lightboxSrc;
      image.alt = button.dataset.lightboxAlt || "";
      caption.textContent = button.dataset.lightboxCaption || "";
      dialog.showModal();
    });
  });

  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });

  dialog.addEventListener("close", () => {
    image.src = "";
    image.alt = "";
  });
});
'''
