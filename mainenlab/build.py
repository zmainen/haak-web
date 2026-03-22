#!/usr/bin/env python3
"""Site generator for mainenlab.org — taxonomy browser with baked JSON data.

Reads:
  - projects/mainen-lab/taxonomy.yaml
  - projects/mainen-lab/projects/*/project.yaml
  - projects/mainen-lab/publications/*/paper.md (YAML frontmatter)
  - projects/mainen-lab/people/*/person.yaml
  - web/mainenlab/research/*.md (hand-written narrative overrides)

Outputs:
  - web/mainenlab/index.html (complete static site, all CSS/JS inline)
"""

import json, re, html as html_mod
from pathlib import Path
from collections import defaultdict

try:
    import yaml
    def load_yaml(text):
        return yaml.safe_load(text) or {}
except ImportError:
    raise SystemExit("PyYAML required: pip install pyyaml")

ROOT = Path(__file__).resolve().parent.parent.parent
LAB = ROOT / "projects" / "mainen-lab"
WEB = ROOT / "web" / "mainenlab"

# ── Helpers ──

def _as_list(v):
    if isinstance(v, list): return v
    if isinstance(v, str): return [v] if v else []
    return []

def _extract_year(val):
    if val is None: return None
    m = re.match(r'(\d{4})', str(val).strip())
    return int(m.group(1)) if m else None

def parse_frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    return load_yaml(text[4:end]) or {}, text[end+4:].strip()

def esc(s):
    return html_mod.escape(str(s)) if s else ""

# ── Taxonomy ──

def load_taxonomy():
    data = load_yaml((LAB / "taxonomy.yaml").read_text())
    taxonomy = {}
    for axis in ("themes", "methods", "scale", "organisms", "settings"):
        items = []
        for entry in data.get(axis, []):
            slug = entry.get("slug", "")
            label = entry.get("label", slug.replace("-", " ").title())
            children = []
            for child in entry.get("children", []):
                cs = child.get("slug", "")
                cl = child.get("label", cs.replace("-", " ").title())
                children.append({"slug": cs, "label": cl})
            items.append({"slug": slug, "label": label, "children": children})
        taxonomy[axis] = items
    return taxonomy

def build_theme_children(taxonomy):
    m = {}
    for t in taxonomy.get("themes", []):
        m[t["slug"]] = {c["slug"] for c in t.get("children", [])}
    return m

def expand_themes(slugs, theme_children):
    expanded = set(slugs)
    for s in list(slugs):
        expanded.update(theme_children.get(s, set()))
    return expanded

# ── Role normalization ──

ROLE_MAP = {
    "principal investigator": "PI", "pi": "PI",
    "postdoc": "Postdoc", "postdoc / visiting scientist": "Postdoc",
    "postdoc / project manager": "Postdoc", "postdoc / student": "Postdoc",
    "technician": "Technician", "research assistant": "Technician",
    "student / ra": "Technician",
    "lab manager": "Lab Manager", "lab manager / admin support": "Lab Manager",
}

def normalize_role(raw):
    r = raw.lower().strip()
    if r in ROLE_MAP: return ROLE_MAP[r]
    if "principal" in r or r == "pi": return "PI"
    if "postdoc" in r: return "Postdoc"
    if "phd" in r: return "PhD Student"
    if "msc" in r or "bsc" in r: return "MSc Student"
    if "technician" in r or "tech" in r or "assistant" in r: return "Technician"
    if "lab manager" in r or "admin" in r: return "Lab Manager"
    return raw or "Other"

ROLE_ORDER = ["PI", "Postdoc", "PhD Student", "MSc Student", "Technician", "Lab Manager", "Other"]

# ── Loaders ──

def load_people():
    people = []
    for f in sorted((LAB / "people").glob("*/person.yaml")):
        d = load_yaml(f.read_text(errors="replace")) or {}
        if not d.get("name"): continue
        people.append({
            "slug": f.parent.name,
            "name": d["name"],
            "status": d.get("status", "unknown"),
            "role": normalize_role(d.get("role", "")),
            "start_date": str(d.get("start_date", ""))[:4] or None,
            "end_date": str(d.get("end_date", ""))[:4] or None,
            "current_position": d.get("current_position", ""),
            "email": (d.get("email") or "").split(";")[0].strip(),
            "orcid": d.get("orcid", ""),
        })
    return people

def load_publications():
    pubs = []
    for f in sorted((LAB / "publications").glob("*/paper.md")):
        meta, _ = parse_frontmatter(f.read_text(errors="replace"))
        if not meta.get("title"): continue
        year = 0
        try: year = int(meta.get("year", 0))
        except (ValueError, TypeError): pass
        citations = 0
        try: citations = int(meta.get("citations", 0))
        except (ValueError, TypeError): pass
        authors = meta.get("authors", [])
        if isinstance(authors, str): authors = [authors]
        pubs.append({
            "slug": f.parent.name,
            "title": meta["title"],
            "year": year,
            "authors": authors,
            "journal": meta.get("journal", ""),
            "doi": meta.get("doi", ""),
            "citations": citations,
            "themes": _as_list(meta.get("themes", [])),
            "methods": _as_list(meta.get("methods", [])),
            "scale": _as_list(meta.get("scale", [])),
            "organisms": _as_list(meta.get("organisms", [])),
            "settings": _as_list(meta.get("settings", [])),
        })
    pubs.sort(key=lambda p: (-p["year"], -p["citations"]))
    return pubs

def load_projects():
    projects = []
    for f in sorted((LAB / "projects").glob("*/project.yaml")):
        d = load_yaml(f.read_text(errors="replace")) or {}
        proj_type = d.get("type", "lab")
        if proj_type == "internal":
            continue
        slug = d.get("slug", f.parent.name)
        start_year = _extract_year(d.get("start_year") or d.get("start_date"))
        end_year = _extract_year(d.get("end_year") or d.get("end_date"))
        paper_ids = []
        for p in d.get("papers", []):
            if isinstance(p, dict):
                pid = p.get("paper_id", p.get("id", ""))
                if pid: paper_ids.append(pid)
            elif isinstance(p, str):
                paper_ids.append(p)
        people_ids = []
        for p in d.get("people", d.get("participants", [])):
            if isinstance(p, dict):
                pid = p.get("person_id", p.get("id", ""))
                if pid: people_ids.append(pid)
            elif isinstance(p, str):
                people_ids.append(p)
        pub_desc = d.get("public_description", "").strip()
        int_desc = d.get("description", "").strip()
        projects.append({
            "slug": slug,
            "name": d.get("name", slug),
            "type": proj_type,
            "status": d.get("status", "unknown"),
            "description": pub_desc if pub_desc else int_desc,
            "start_year": start_year,
            "end_year": end_year,
            "themes": _as_list(d.get("themes", [])),
            "methods": _as_list(d.get("methods", [])),
            "scale": _as_list(d.get("scale", [])),
            "organisms": _as_list(d.get("organisms", [])),
            "settings": _as_list(d.get("settings", [])),
            "people": people_ids,
            "paper_refs": paper_ids,
        })
    return projects

def link_papers_to_projects(projects, pubs, theme_children):
    pub_by_doi = {p["doi"]: p["slug"] for p in pubs if p["doi"]}
    pub_by_slug = {p["slug"]: p for p in pubs}
    for proj in projects:
        matched = set()
        for ref in proj.get("paper_refs", []):
            if ref in pub_by_doi: matched.add(pub_by_doi[ref])
            elif ref in pub_by_slug: matched.add(ref)
        proj["papers"] = sorted(matched)
        proj["paper_count"] = len(matched)

# ── Narratives ──

def generate_narratives(taxonomy, projects, pubs, people, theme_children):
    people_by_slug = {p["slug"]: p for p in people}
    narratives = {}
    all_theme_slugs = set()
    for t in taxonomy.get("themes", []):
        all_theme_slugs.add(t["slug"])
        for c in t.get("children", []):
            all_theme_slugs.add(c["slug"])

    for slug in all_theme_slugs:
        expanded = {slug}
        expanded.update(theme_children.get(slug, set()))
        for parent, children in theme_children.items():
            if slug in children: expanded.add(parent)

        theme_projects = [p for p in projects if set(p["themes"]) & expanded]
        if not theme_projects: continue

        years = [y for p in theme_projects for y in [p["start_year"], p["end_year"]] if y]
        if years:
            active_any = any(p["status"] == "active" for p in theme_projects)
            span = f"{min(years)}\u2013present" if active_any else f"{min(years)}\u2013{max(years)}"
        else:
            span = ""

        person_counts = defaultdict(int)
        for p in theme_projects:
            for pid in p["people"]: person_counts[pid] += 1
        top_people = sorted(person_counts, key=lambda x: -person_counts[x])[:5]
        people_names = [people_by_slug[pid]["name"] for pid in top_people if pid in people_by_slug]

        theme_pubs = sorted(
            [p for p in pubs if set(p["themes"]) & expanded],
            key=lambda p: (-p["citations"], -p["year"])
        )

        active_projects = [p for p in theme_projects if p["status"] == "active"]
        label = slug.replace("-", " ").title()

        parts = []
        if span: parts.append(f"The lab's {label.lower()} research spans {span}.")
        if people_names: parts.append(f"Key contributors: {', '.join(people_names)}.")
        if theme_projects:
            proj_strs = [f"{p['name']} ({p['start_year'] or '?'})" for p in sorted(theme_projects, key=lambda x: x["start_year"] or 9999)]
            parts.append(f"Projects: {'; '.join(proj_strs)}.")
        if theme_pubs[:3]:
            paper_strs = [f"{p['authors'][0].split(',')[0] if p['authors'] else 'Unknown'} et al. ({p['year']})" for p in theme_pubs[:3]]
            parts.append(f"Headline papers: {', '.join(paper_strs)}.")
        if active_projects:
            parts.append(f"{len(active_projects)} currently active project{'s' if len(active_projects) != 1 else ''}.")
        narratives[slug] = " ".join(parts)
    return narratives

def load_overrides():
    overrides = {}
    research_dir = WEB / "research"
    if not research_dir.exists(): return overrides
    for f in research_dir.glob("*.md"):
        if f.stem.startswith("publications"): continue
        text = f.read_text(errors="replace")
        _, body = parse_frontmatter(text)
        if body.strip(): overrides[f.stem] = body.strip()
    return overrides

# ── Lab intro ──

def generate_lab_intro(people, projects, taxonomy):
    return (
        "How do brains make decisions, interpret the world, and generate conscious experience? "
        "The Mainen Lab at the Champalimaud Foundation in Lisbon investigates these questions "
        "through the lens of neuromodulation \u2014 particularly serotonin \u2014 using large-scale "
        "electrophysiology, optogenetics, computational modeling, and behavioral analysis in mice "
        "and humans. Our current work centres on how serotonin shapes learning, novelty detection, "
        "and embodied cognition, with growing programmes in psychedelics and consciousness."
    )

# ── HTML Generation ──

HTML_TEMPLATE = r'''<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mainen Lab &mdash; Systems Neuroscience</title>
<meta name="description" content="The Mainen Lab at the Champalimaud Foundation studies how brains make decisions, interpret the world, and generate conscious experience.">
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #fafaf8;
  --bg-card: #ffffff;
  --text: #1a1a1a;
  --muted: #6b7280;
  --border: #e5e7eb;
  --hover: #f3f4f6;
  --accent: #0d9488;
  --pill-themes: #0d9488;
  --pill-methods: #ea580c;
  --pill-scale: #7c3aed;
  --pill-organisms: #16a34a;
  --pill-settings: #475569;
  --status-active: #16a34a;
  --status-completed: #9ca3af;
  --shadow: 0 1px 3px rgba(0,0,0,0.06);
}

[data-theme="dark"] {
  --bg: #111111;
  --bg-card: #1a1a1a;
  --text: #e5e5e5;
  --muted: #9ca3af;
  --border: #2d2d2d;
  --hover: #222222;
  --accent: #2dd4bf;
  --pill-themes: #2dd4bf;
  --pill-methods: #fb923c;
  --pill-scale: #a78bfa;
  --pill-organisms: #4ade80;
  --pill-settings: #94a3b8;
  --status-active: #4ade80;
  --status-completed: #6b7280;
  --shadow: 0 1px 3px rgba(0,0,0,0.3);
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.6;
  transition: background 0.2s, color 0.2s;
}

.container { max-width: 920px; margin: 0 auto; padding: 0 1.25rem; }

/* Header */
header {
  padding: 2.5rem 0 1.5rem;
  border-bottom: 1px solid var(--border);
  position: relative;
}
header h1 { font-size: 1.6rem; font-weight: 600; letter-spacing: -0.02em; }
header .subtitle { color: var(--muted); font-size: 0.95rem; margin-top: 0.2rem; }
#theme-toggle {
  position: absolute; top: 2.5rem; right: 0;
  background: none; border: 1px solid var(--border); border-radius: 6px;
  padding: 0.4rem 0.6rem; cursor: pointer; color: var(--text); font-size: 0.85rem;
}
#theme-toggle:hover { background: var(--hover); }

/* Lab intro */
.lab-intro {
  padding: 1.25rem 0 0.5rem;
  font-size: 0.92rem; line-height: 1.7; color: var(--muted);
}

/* Filter bar */
.filter-section { padding: 1.5rem 0 0.5rem; }
.filter-section h3 {
  font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--muted); margin-bottom: 0.5rem; font-weight: 600;
}
.filter-row { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-bottom: 0.75rem; }
.filter-pill {
  display: inline-block; padding: 0.25rem 0.65rem; border-radius: 999px;
  font-size: 0.78rem; cursor: pointer; transition: all 0.15s;
  border: 1px solid; user-select: none; white-space: nowrap;
}
.filter-pill.axis-themes { border-color: var(--pill-themes); color: var(--pill-themes); }
.filter-pill.axis-themes.active { background: var(--pill-themes); color: #fff; }
.filter-pill.axis-methods { border-color: var(--pill-methods); color: var(--pill-methods); }
.filter-pill.axis-methods.active { background: var(--pill-methods); color: #fff; }
.filter-pill.axis-scale { border-color: var(--pill-scale); color: var(--pill-scale); }
.filter-pill.axis-scale.active { background: var(--pill-scale); color: #fff; }
.filter-pill.axis-organisms { border-color: var(--pill-organisms); color: var(--pill-organisms); }
.filter-pill.axis-organisms.active { background: var(--pill-organisms); color: #fff; }
.filter-pill.axis-settings { border-color: var(--pill-settings); color: var(--pill-settings); }
.filter-pill.axis-settings.active { background: var(--pill-settings); color: #fff; }
.filter-pill.child { font-size: 0.72rem; padding: 0.2rem 0.55rem; }

.tertiary-filters { display: block; }

/* Active filters */
.active-filters { padding: 0.5rem 0; display: none; align-items: center; flex-wrap: wrap; gap: 0.35rem; }
.active-filters.has-filters { display: flex; }
.active-pill {
  display: inline-flex; align-items: center; gap: 0.3rem;
  padding: 0.2rem 0.5rem; border-radius: 999px; font-size: 0.75rem;
  background: var(--hover); border: 1px solid var(--border); color: var(--text);
}
.active-pill .remove { cursor: pointer; font-weight: bold; opacity: 0.5; }
.active-pill .remove:hover { opacity: 1; }
.clear-all {
  font-size: 0.72rem; color: var(--muted); cursor: pointer; border: none;
  background: none; text-decoration: underline; margin-left: 0.5rem;
}

/* Narrative */
.narrative-area { padding: 0.75rem 0 0.5rem; }
.narrative-block {
  padding: 1rem 1.25rem; margin-bottom: 0.75rem;
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 8px; border-left: 3px solid var(--pill-themes);
}
.narrative-block h4 { font-size: 0.9rem; font-weight: 600; margin-bottom: 0.4rem; }
.narrative-block p { font-size: 0.88rem; color: var(--muted); line-height: 1.65; }

/* Stats bar */
.stats-bar {
  font-size: 0.78rem; color: var(--muted); padding: 0.5rem 0 1rem;
  border-bottom: 1px solid var(--border);
}

/* Section headings */
.section-heading {
  font-size: 1rem; font-weight: 600; padding: 1.25rem 0 0.75rem;
  color: var(--text);
}

/* Completed toggle */
.completed-toggle {
  cursor: pointer; list-style: none; user-select: none;
}
.completed-toggle::-webkit-details-marker { display: none; }
.completed-toggle::before {
  content: '\25b6'; display: inline-block; margin-right: 0.5rem;
  font-size: 0.7rem; transition: transform 0.2s; vertical-align: middle;
}
details[open] > .completed-toggle::before { transform: rotate(90deg); }

/* Project cards */
.project-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 8px; padding: 1rem 1.25rem; margin-bottom: 0.6rem;
  box-shadow: var(--shadow); transition: box-shadow 0.15s;
}
.project-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
.project-card.hidden { display: none; }

.card-header { display: flex; justify-content: space-between; align-items: flex-start; cursor: pointer; }
.card-title { font-weight: 600; font-size: 0.95rem; }
.card-meta { display: flex; align-items: center; gap: 0.6rem; margin-top: 0.3rem; }
.card-span { font-size: 0.78rem; color: var(--muted); }
.status-pill {
  font-size: 0.65rem; padding: 0.1rem 0.45rem; border-radius: 999px;
  font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em;
}
.status-pill.active { background: var(--status-active); color: #fff; }
.status-pill.completed { background: var(--status-completed); color: #fff; }
.status-pill.dormant { background: #eab308; color: #fff; }

.card-people { font-size: 0.8rem; color: var(--muted); margin-top: 0.3rem; }
.card-papers { font-size: 0.78rem; color: var(--muted); }
.card-desc-preview { font-size: 0.82rem; color: var(--muted); margin-top: 0.3rem; line-height: 1.5; }
.card-tags { display: flex; flex-wrap: wrap; gap: 0.25rem; margin-top: 0.4rem; }
.card-tag {
  font-size: 0.65rem; padding: 0.1rem 0.4rem; border-radius: 999px;
  border: 1px solid; opacity: 0.7;
}

.card-detail {
  max-height: 0; overflow: hidden; transition: max-height 0.35s ease;
}
.card-detail.open { max-height: 3000px; }
.card-detail-inner { padding-top: 0.75rem; border-top: 1px solid var(--border); margin-top: 0.75rem; }
.card-description { font-size: 0.85rem; line-height: 1.6; margin-bottom: 0.75rem; }
.card-pub-list { list-style: none; padding: 0; }
.card-pub-list li { font-size: 0.8rem; color: var(--muted); margin-bottom: 0.4rem; line-height: 1.5; }
.card-pub-list li a { color: var(--accent); text-decoration: none; }
.card-pub-list li a:hover { text-decoration: underline; }
.card-all-people { font-size: 0.82rem; margin-top: 0.5rem; }
.expand-icon { color: var(--muted); font-size: 1rem; transition: transform 0.2s; flex-shrink: 0; }
.card-detail.open ~ .card-header .expand-icon,
.project-card.expanded .expand-icon { transform: rotate(180deg); }

/* Section titles */
.section-title { font-size: 1.15rem; font-weight: 600; margin-bottom: 1rem; }

/* Unified timeline */
.unified-timeline { position: relative; display: flex; }
.unified-timeline-labels { width: 170px; min-width: 170px; flex-shrink: 0; }
.unified-timeline-scroll { flex: 1; overflow-x: auto; min-width: 0; }
.unified-timeline-scroll-inner { min-width: 1200px; }
.timeline-divider {
  padding: 0.4rem 0 0.2rem;
  border-top: 1px solid var(--border);
}
.timeline-divider-label-only {
  padding: 0.4rem 0 0.2rem;
  border-top: 1px solid var(--border);
}
.divider-label {
  font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--muted); font-weight: 600;
}

/* People timeline — mirrors research timeline */
.people-timeline-container { position: relative; }
.tl-label-row {
  height: 28px; display: flex; align-items: center; justify-content: flex-end;
  padding-right: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  cursor: pointer; transition: background 0.15s; border-radius: 4px 0 0 4px;
}
.tl-label-row:hover { background: var(--hover); }
.tl-label-row.selected { background: var(--hover); }
.tl-track-row {
  height: 28px; position: relative; cursor: pointer;
  transition: background 0.15s; border-radius: 0 4px 4px 0;
}
.tl-track-row:hover { background: var(--hover); }
.tl-track-row.selected { background: var(--hover); }
.ptl-name { font-size: 0.8rem; font-weight: 500; color: var(--text); line-height: 1.2; }
.ptl-role { font-size: 0.62rem; color: var(--muted); line-height: 1.1; }
.people-timeline-bar {
  position: absolute; height: 16px; border-radius: 3px; top: 6px;
  cursor: pointer; transition: opacity 0.15s, box-shadow 0.15s;
}
.people-timeline-bar:hover { box-shadow: 0 0 6px rgba(0,0,0,0.3); }
.people-timeline-bar.alumni-bar { opacity: 0.5; }

/* Alumni collapsible — people timeline */
.alumni-toggle-label {
  height: 28px; display: flex; align-items: center; justify-content: flex-end;
  padding-right: 12px; font-size: 0.8rem; font-weight: 500; color: var(--accent);
  cursor: pointer; user-select: none;
}
.alumni-toggle-label::before {
  content: '\25b6'; display: inline-block; margin-right: 0.4rem;
  font-size: 0.6rem; transition: transform 0.2s; vertical-align: middle;
}
.alumni-toggle-label.open::before { transform: rotate(90deg); }

/* Footer */
footer {
  padding: 2rem 0; border-top: 1px solid var(--border);
  text-align: center; color: var(--muted); font-size: 0.8rem;
}
footer a { color: var(--accent); text-decoration: none; }
footer a:hover { text-decoration: underline; }
footer .sep { margin: 0 0.5rem; opacity: 0.4; }

/* Timeline */
.timeline-section { padding: 1.5rem 0 1rem; }
.timeline-container { position: relative; }
.tl-research-label {
  height: 28px; display: flex; align-items: center; justify-content: flex-end;
  padding-right: 12px; font-size: 0.8rem; font-weight: 500;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  cursor: pointer; transition: background 0.15s; border-radius: 4px 0 0 4px;
}
.tl-research-label:hover { background: var(--hover); }
.tl-research-label.selected { background: var(--hover); }
.tl-research-track {
  height: 28px; position: relative; cursor: pointer;
  transition: background 0.15s; border-radius: 0 4px 4px 0;
}
.tl-research-track:hover { background: var(--hover); }
.tl-research-track.selected { background: var(--hover); }
.timeline-seg {
  position: absolute; height: 18px; border-radius: 3px; top: 5px;
  cursor: pointer; transition: opacity 0.15s, box-shadow 0.15s;
}
.timeline-seg:hover { box-shadow: 0 0 6px rgba(0,0,0,0.3); }
.timeline-seg.completed { opacity: 0.55; }
.timeline-seg.active { opacity: 1; }
.timeline-years {
  position: relative; height: 18px; margin-bottom: 2px;
}
.timeline-year-label {
  position: absolute; font-size: 0.65rem; color: var(--muted);
  transform: translateX(-50%); top: 0; user-select: none;
}
.timeline-gridlines { position: absolute; top: 0; left: 0; right: 0; bottom: 0; pointer-events: none; }
.timeline-gridline {
  position: absolute; top: 0; bottom: 0; width: 1px;
  background: var(--border); opacity: 0.3;
}
.timeline-now-line {
  position: absolute; top: 0; bottom: 0; width: 1px;
  border-left: 1px dotted var(--text); opacity: 0.3;
  pointer-events: none; z-index: 5;
}
.timeline-tooltip {
  position: fixed; pointer-events: none; opacity: 0; transition: opacity 0.15s;
  background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px;
  padding: 0.5rem 0.75rem; font-size: 0.78rem; color: var(--text);
  max-width: 350px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); z-index: 100;
}
.timeline-tooltip.visible { opacity: 1; }
.timeline-tooltip .tt-name { font-weight: 600; margin-bottom: 0.2rem; }
.timeline-tooltip .tt-span { color: var(--muted); font-size: 0.72rem; margin-bottom: 0.2rem; }
.timeline-tooltip .tt-desc { color: var(--muted); line-height: 1.4; }

/* Responsive */
@media (max-width: 640px) {
  header h1 { font-size: 1.3rem; }
  .card-header { flex-direction: column; }
  .unified-timeline-labels { width: 110px; min-width: 110px; }
}
</style>
</head>
<body>
<div class="container">

<header>
  <h1>Mainen Lab &mdash; Systems Neuroscience</h1>
  <div class="subtitle">Champalimaud Foundation, Lisbon</div>
  <button id="theme-toggle" aria-label="Toggle dark mode">&#9790;</button>
</header>

<div class="lab-intro" id="lab-intro">__LAB_INTRO_PLACEHOLDER__</div>

<!-- Unified Timeline -->
<div class="timeline-section" id="unified-timeline-section">
  <div class="unified-timeline" id="unified-timeline">
    <div class="unified-timeline-labels" id="tl-labels"></div>
    <div class="unified-timeline-scroll" id="tl-scroll">
      <div class="unified-timeline-scroll-inner" id="tl-tracks"></div>
    </div>
  </div>
</div>
<div class="timeline-tooltip" id="timeline-tooltip">
  <div class="tt-name"></div>
  <div class="tt-span"></div>
  <div class="tt-desc"></div>
</div>

<!-- Filter bar -->
<div class="filter-section">
  <h3>Themes</h3>
  <div class="filter-row" id="filter-themes"></div>
  <h3>Methods</h3>
  <div class="filter-row" id="filter-methods"></div>
  <div class="tertiary-filters" id="tertiary-filters">
    <h3>Scale</h3>
    <div class="filter-row" id="filter-scale"></div>
    <h3>Organisms</h3>
    <div class="filter-row" id="filter-organisms"></div>
    <h3>Settings</h3>
    <div class="filter-row" id="filter-settings"></div>
  </div>
</div>

<div class="active-filters" id="active-filters"></div>
<div class="narrative-area" id="narrative-area"></div>
<div class="stats-bar" id="stats-bar"></div>

<div id="projects-container"></div>

</div><!-- .container -->

<footer>
  <div class="container">
    <a href="https://zmainen.org">zmainen.org</a>
    <span class="sep">&middot;</span>
    <a href="https://latentstates.org">latentstates.org</a>
    <span class="sep">&middot;</span>
    <a href="https://haak.world">haak.world</a>
  </div>
</footer>

<script>
const DATA = __SITE_DATA_PLACEHOLDER__;

// ── State ──
const filters = { themes: new Set(), methods: new Set(), scale: new Set(), organisms: new Set(), settings: new Set() };
const themeChildren = {};
DATA.taxonomy.themes.forEach(t => {
  if (t.children && t.children.length) themeChildren[t.slug] = t.children.map(c => c.slug);
});

// ── Theme toggle ──
const toggle = document.getElementById('theme-toggle');
const root = document.documentElement;
const stored = localStorage.getItem('ml-theme');
if (stored) root.setAttribute('data-theme', stored);
else if (window.matchMedia('(prefers-color-scheme: dark)').matches) root.setAttribute('data-theme', 'dark');
toggle.textContent = root.getAttribute('data-theme') === 'dark' ? '\u2600' : '\u263E';
toggle.addEventListener('click', () => {
  const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  root.setAttribute('data-theme', next);
  localStorage.setItem('ml-theme', next);
  toggle.textContent = next === 'dark' ? '\u2600' : '\u263E';
  renderFullTimeline();
});

// ── Tooltip positioning (viewport-aware) ──
function positionTooltip(e) {
  const tt = document.getElementById('timeline-tooltip');
  const pad = 12;
  const ttW = tt.offsetWidth || 350;
  const ttH = tt.offsetHeight || 80;
  let x = e.clientX + pad;
  let y = e.clientY - pad;
  if (x + ttW > window.innerWidth - pad) x = e.clientX - ttW - pad;
  if (x < pad) x = pad;
  if (y + ttH > window.innerHeight - pad) y = window.innerHeight - pad - ttH;
  if (y < pad) y = pad;
  tt.style.left = x + 'px';
  tt.style.top = y + 'px';
}

// ── Build filter pills ──
const AXES = ['themes', 'methods', 'scale', 'organisms', 'settings'];

function buildFilterPills() {
  AXES.forEach(axis => {
    const container = document.getElementById('filter-' + axis);
    if (!container) return;
    DATA.taxonomy[axis].forEach(item => {
      container.appendChild(makePill(item.slug, item.label, axis, false));
      if (item.children) {
        item.children.forEach(child => {
          container.appendChild(makePill(child.slug, child.label, axis, true));
        });
      }
    });
  });
}

function makePill(slug, label, axis, isChild) {
  const el = document.createElement('span');
  el.className = 'filter-pill axis-' + axis + (isChild ? ' child' : '');
  el.textContent = label;
  el.dataset.slug = slug;
  el.dataset.axis = axis;
  el.addEventListener('click', () => toggleFilter(axis, slug));
  return el;
}


// ── Filter logic ──
function toggleFilter(axis, slug) {
  if (filters[axis].has(slug)) filters[axis].delete(slug);
  else filters[axis].add(slug);
  updateURL();
  render();
}

function clearFilters() {
  AXES.forEach(a => filters[a].clear());
  updateURL();
  render();
}

function expandThemeSet(slugs) {
  const expanded = new Set(slugs);
  slugs.forEach(s => {
    if (themeChildren[s]) themeChildren[s].forEach(c => expanded.add(c));
  });
  return expanded;
}

function projectMatches(proj) {
  // Person filter
  if (selectedPerson) {
    if ((proj.participants || []).indexOf(selectedPerson) === -1) return false;
  }
  const activeAxes = AXES.filter(a => filters[a].size > 0);
  if (activeAxes.length === 0) return true;
  return activeAxes.every(axis => {
    const selected = filters[axis];
    const projTags = new Set(proj[axis] || []);
    if (axis === 'themes') {
      const expanded = expandThemeSet(selected);
      return [...expanded].some(s => projTags.has(s));
    }
    return [...selected].some(s => projTags.has(s));
  });
}

// ── URL hash ──
function updateURL() {
  const parts = [];
  AXES.forEach(a => {
    if (filters[a].size > 0) parts.push(a + '=' + [...filters[a]].join(','));
  });
  window.location.hash = parts.length ? parts.join('&') : '';
}

function readURL() {
  const hash = window.location.hash.slice(1);
  if (!hash) return;
  hash.split('&').forEach(part => {
    const [axis, vals] = part.split('=');
    if (filters[axis] && vals) vals.split(',').forEach(v => filters[axis].add(v));
  });
}

// ── Render ──
function render() {
  renderFilterPills();
  renderActiveFilters();
  renderNarratives();
  renderProjects();
  renderStats();
  // Sync timeline selection with theme filter
  if (filters.themes.size === 1) {
    selectedTimelineTheme = [...filters.themes][0];
  } else if (filters.themes.size === 0) {
    selectedTimelineTheme = null;
  }
  document.querySelectorAll('.tl-research-label[data-theme]').forEach(el => {
    el.classList.toggle('selected', el.dataset.theme === selectedTimelineTheme);
  });
  document.querySelectorAll('.tl-research-track[data-theme]').forEach(el => {
    el.classList.toggle('selected', el.dataset.theme === selectedTimelineTheme);
  });
}

function renderFilterPills() {
  document.querySelectorAll('.filter-pill').forEach(el => {
    el.classList.toggle('active', filters[el.dataset.axis].has(el.dataset.slug));
  });
}

function renderActiveFilters() {
  const container = document.getElementById('active-filters');
  container.innerHTML = '';
  let hasAny = false;
  AXES.forEach(axis => {
    filters[axis].forEach(slug => {
      hasAny = true;
      const pill = document.createElement('span');
      pill.className = 'active-pill';
      const label = findLabel(axis, slug);
      pill.innerHTML = label + ' <span class="remove" data-axis="' + axis + '" data-slug="' + slug + '">&times;</span>';
      container.appendChild(pill);
    });
  });
  if (hasAny) {
    const btn = document.createElement('button');
    btn.className = 'clear-all';
    btn.textContent = 'Clear all';
    btn.addEventListener('click', clearFilters);
    container.appendChild(btn);
  }
  container.classList.toggle('has-filters', hasAny);
  container.querySelectorAll('.remove').forEach(el => {
    el.addEventListener('click', e => {
      e.stopPropagation();
      toggleFilter(el.dataset.axis, el.dataset.slug);
    });
  });
}

function findLabel(axis, slug) {
  for (const item of DATA.taxonomy[axis] || []) {
    if (item.slug === slug) return item.label;
    if (item.children) for (const c of item.children) if (c.slug === slug) return c.label;
  }
  return slug;
}

function renderNarratives() {
  const area = document.getElementById('narrative-area');
  area.innerHTML = '';
  if (filters.themes.size === 0) return;
  filters.themes.forEach(slug => {
    const text = DATA.narratives[slug];
    if (!text) return;
    const block = document.createElement('div');
    block.className = 'narrative-block';
    block.innerHTML = '<h4>' + findLabel('themes', slug) + '</h4><p>' + escHTML(text) + '</p>';
    area.appendChild(block);
  });
}

function escHTML(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function renderProjects() {
  const container = document.getElementById('projects-container');
  container.innerHTML = '';
  const visible = DATA.projects.filter(projectMatches);
  const active = visible.filter(p => p.status === 'active').sort(sortProjects);
  const completed = visible.filter(p => p.status !== 'active').sort(sortProjects);

  if (active.length) {
    container.innerHTML += '<div class="section-heading">Active Research</div>';
    active.forEach(p => container.appendChild(makeProjectCard(p)));
  }
  if (completed.length) {
    const details = document.createElement('details');
    const summary = document.createElement('summary');
    summary.className = 'section-heading completed-toggle';
    summary.textContent = 'Completed Research (' + completed.length + ' projects)';
    details.appendChild(summary);
    completed.forEach(p => details.appendChild(makeProjectCard(p)));
    container.appendChild(details);
  }
  if (!visible.length) {
    container.innerHTML = '<div class="section-heading" style="color:var(--muted)">No projects match the current filters.</div>';
  }
}

function sortProjects(a, b) {
  const ya = a.end_year || a.start_year || 0;
  const yb = b.end_year || b.start_year || 0;
  return yb - ya || (b.paper_count - a.paper_count);
}

function makeProjectCard(p) {
  const card = document.createElement('div');
  card.className = 'project-card';
  const span = p.start_year ? (p.status === 'active' ? p.start_year + '\u2013present' : p.start_year + (p.end_year ? '\u2013' + p.end_year : '')) : '';
  const peopleBySlug = {};
  DATA.people.forEach(pe => peopleBySlug[pe.slug] = pe);
  const keyPeople = (p.participants || []).slice(0, 3).map(s => peopleBySlug[s] ? peopleBySlug[s].name : s).join(', ');
  const allPeople = (p.participants || []).map(s => peopleBySlug[s] ? peopleBySlug[s].name : s).join(', ');

  const tags = [];
  ['themes','methods','scale','organisms','settings'].forEach(axis => {
    (p[axis] || []).forEach(slug => {
      tags.push('<span class="card-tag axis-' + axis + '">' + findLabel(axis, slug) + '</span>');
    });
  });

  const pubs = (p.papers || []).map(slug => DATA.publications.find(pub => pub.slug === slug)).filter(Boolean);
  pubs.sort((a, b) => b.year - a.year || b.citations - a.citations);
  const pubListHTML = pubs.map(pub => {
    const firstAuthor = pub.authors && pub.authors.length ? pub.authors[0].split(',')[0] : '';
    const nAuthors = pub.authors ? pub.authors.length : 0;
    const authorStr = nAuthors > 2 ? firstAuthor + ' et al.' : (pub.authors || []).map(a => a.split(',')[0]).join(', ');
    const link = pub.doi ? '<a href="https://doi.org/' + pub.doi + '" target="_blank">' + escHTML(pub.title) + '</a>' : escHTML(pub.title);
    return '<li>' + authorStr + ' (' + pub.year + '). ' + link + '. <em>' + escHTML(pub.journal) + '</em></li>';
  }).join('');

  card.innerHTML =
    '<div class="card-header" onclick="this.parentElement.classList.toggle(\'expanded\');this.parentElement.querySelector(\'.card-detail\').classList.toggle(\'open\')">' +
      '<div>' +
        '<div class="card-title">' + escHTML(p.name) + '</div>' +
        '<div class="card-meta">' +
          (span ? '<span class="card-span">' + span + '</span>' : '') +
          '<span class="status-pill ' + p.status + '">' + p.status + '</span>' +
        '</div>' +
        (keyPeople ? '<div class="card-people">' + escHTML(keyPeople) + '</div>' : '') +
        (p.description ? '<div class="card-desc-preview">' + escHTML(p.description.length > 150 ? p.description.slice(0, 150) + '\u2026' : p.description) + '</div>' : '') +
        (p.paper_count ? '<div class="card-papers">' + p.paper_count + ' publication' + (p.paper_count !== 1 ? 's' : '') + '</div>' : '') +
        '<div class="card-tags">' + tags.join('') + '</div>' +
      '</div>' +
      '<span class="expand-icon">&#9662;</span>' +
    '</div>' +
    '<div class="card-detail">' +
      '<div class="card-detail-inner">' +
        (p.description ? '<div class="card-description">' + escHTML(p.description) + '</div>' : '') +
        (pubListHTML ? '<ul class="card-pub-list">' + pubListHTML + '</ul>' : '') +
        (allPeople ? '<div class="card-all-people"><strong>People:</strong> ' + escHTML(allPeople) + '</div>' : '') +
      '</div>' +
    '</div>';
  return card;
}

function renderStats() {
  const visible = DATA.projects.filter(projectMatches);
  const pubSlugs = new Set();
  visible.forEach(p => (p.papers || []).forEach(s => pubSlugs.add(s)));
  document.getElementById('stats-bar').textContent =
    visible.length + ' projects \u00b7 ' + pubSlugs.size + ' publications';
}

// ── People ──
let selectedPerson = null;

function getPersonThemes(slug) {
  const themes = {};
  DATA.projects.forEach(p => {
    if ((p.participants || []).indexOf(slug) !== -1) {
      (p.themes || []).forEach(t => { themes[t] = (themes[t] || 0) + 1; });
    }
  });
  return themes;
}

function getPrimaryTheme(themeMap) {
  let best = null, max = 0;
  for (const [slug, count] of Object.entries(themeMap)) {
    if (count > max) { max = count; best = slug; }
  }
  return best;
}

function selectPerson(slug) {
  if (selectedPerson === slug) { selectedPerson = null; }
  else { selectedPerson = slug; }
  document.querySelectorAll('.tl-label-row[data-person]').forEach(r => {
    r.classList.toggle('selected', r.dataset.person === selectedPerson);
  });
  document.querySelectorAll('.tl-track-row[data-person]').forEach(r => {
    r.classList.toggle('selected', r.dataset.person === selectedPerson);
  });
  renderProjects();
  renderStats();
  highlightPersonOnTimeline(selectedPerson);
}

function highlightPersonOnTimeline(slug) {
  if (!slug) {
    document.querySelectorAll('.timeline-seg').forEach(s => { s.style.opacity = ''; });
    return;
  }
  const personProjects = new Set();
  DATA.projects.forEach(p => {
    if ((p.participants || []).indexOf(slug) !== -1) personProjects.add(p.slug);
  });
  document.querySelectorAll('.timeline-seg').forEach(s => {
    s.style.opacity = personProjects.has(s.dataset.slug) ? '1' : '0.15';
  });
}

// ── Timeline (theme-based) ──
const THEME_COLORS = {
  'serotonin': '#2a9d8f', 'olfaction': '#e9c46a', 'decision': '#e76f51',
  'synaptic': '#7b2d8e', 'dendritic': '#9b59b6', 'spike': '#6c3483',
  'consciousness': '#8e44ad', 'volition': '#a569bd', 'embodiment': '#c0835d',
  'perception': '#5d6d7e', 'learning': '#27ae60', 'space': '#3498db',
  'vision': '#f39c12'
};

function getThemeColor(slug) {
  for (const [key, color] of Object.entries(THEME_COLORS)) {
    if (slug.indexOf(key) !== -1) return color;
  }
  return '#9ca3af';
}

let selectedTimelineTheme = null;

// Shared timeline constants
const TL_MIN_YEAR = 1990, TL_MAX_YEAR = 2060;
const TL_TOTAL_YEARS = TL_MAX_YEAR - TL_MIN_YEAR;
const TL_CURRENT_YEAR = new Date().getFullYear();

function addGridlines(container) {
  const gridDiv = document.createElement('div');
  gridDiv.className = 'timeline-gridlines';
  for (let y = TL_MIN_YEAR; y <= TL_MAX_YEAR; y += 5) {
    const pct = ((y - TL_MIN_YEAR) / TL_TOTAL_YEARS) * 100;
    const line = document.createElement('div');
    line.className = 'timeline-gridline';
    line.style.left = pct + '%';
    gridDiv.appendChild(line);
  }
  container.appendChild(gridDiv);
}

function addNowLine(container) {
  const pct = ((TL_CURRENT_YEAR - TL_MIN_YEAR) / TL_TOTAL_YEARS) * 100;
  const line = document.createElement('div');
  line.className = 'timeline-now-line';
  line.style.left = pct + '%';
  container.appendChild(line);
}

function renderFullTimeline() {
  const labelsCol = document.getElementById('tl-labels');
  const tracksCol = document.getElementById('tl-tracks');
  labelsCol.innerHTML = '';
  tracksCol.innerHTML = '';

  const currentYear = TL_CURRENT_YEAR;
  const minYear = TL_MIN_YEAR, maxYear = TL_MAX_YEAR;
  const totalYears = TL_TOTAL_YEARS;
  const tooltip = document.getElementById('timeline-tooltip');

  // ── Research section ──
  const projects = DATA.projects.filter(p => p.start_year);
  const allThemeSlugs = new Set();
  DATA.taxonomy.themes.forEach(t => {
    allThemeSlugs.add(t.slug);
    (t.children || []).forEach(c => allThemeSlugs.add(c.slug));
  });
  const themeProjects = {};
  allThemeSlugs.forEach(slug => {
    const matching = projects.filter(p => (p.themes || []).indexOf(slug) !== -1);
    if (matching.length) themeProjects[slug] = matching;
  });
  const themeSlugs = Object.keys(themeProjects).sort((a, b) => {
    return Math.min(...themeProjects[a].map(p => p.start_year)) - Math.min(...themeProjects[b].map(p => p.start_year));
  });

  // Research divider
  const researchDivL = document.createElement('div');
  researchDivL.className = 'timeline-divider-label-only';
  researchDivL.style.borderTop = 'none';
  researchDivL.innerHTML = '<span class="divider-label">Research</span>';
  labelsCol.appendChild(researchDivL);

  const yearRow = document.createElement('div');
  yearRow.className = 'timeline-years';
  for (let y = minYear; y <= maxYear; y += 5) {
    const pct = ((y - minYear) / totalYears) * 100;
    const lbl = document.createElement('span');
    lbl.className = 'timeline-year-label';
    lbl.style.left = pct + '%';
    lbl.textContent = y;
    yearRow.appendChild(lbl);
  }
  // Spacer in label col for year row
  const yearSpacer = document.createElement('div');
  yearSpacer.style.height = '20px';
  labelsCol.appendChild(yearSpacer);

  // Matching spacer in tracks col for the "Research" divider label
  const researchDivR = document.createElement('div');
  researchDivR.className = 'timeline-divider-label-only';
  researchDivR.style.borderTop = 'none';
  researchDivR.innerHTML = '&nbsp;';
  tracksCol.appendChild(researchDivR);

  tracksCol.appendChild(yearRow);

  // Research rows wrapper
  const researchTracksWrap = document.createElement('div');
  researchTracksWrap.style.position = 'relative';
  addGridlines(researchTracksWrap);
  addNowLine(researchTracksWrap);

  themeSlugs.forEach(slug => {
    // Label
    const labelRow = document.createElement('div');
    labelRow.className = 'tl-research-label';
    labelRow.textContent = findLabel('themes', slug);
    labelRow.style.color = getThemeColor(slug);
    labelRow.dataset.theme = slug;
    if (selectedTimelineTheme === slug) labelRow.classList.add('selected');
    labelRow.addEventListener('click', function() { selectTimelineTheme(slug, null); });
    labelsCol.appendChild(labelRow);

    // Track
    const trackRow = document.createElement('div');
    trackRow.className = 'tl-research-track';
    trackRow.dataset.theme = slug;
    if (selectedTimelineTheme === slug) trackRow.classList.add('selected');

    const projs = themeProjects[slug].sort((a, b) => a.start_year - b.start_year);
    projs.forEach(p => {
      const startPct = ((p.start_year - minYear) / totalYears) * 100;
      const endYr = p.status === 'active' ? currentYear : (p.end_year || p.start_year);
      const endPct = ((endYr - minYear + 1) / totalYears) * 100;
      const widthPct = Math.max(endPct - startPct, 1.2);

      const seg = document.createElement('div');
      seg.className = 'timeline-seg ' + (p.status === 'active' ? 'active' : 'completed');
      seg.style.left = startPct + '%';
      seg.style.width = widthPct + '%';
      seg.style.backgroundColor = getThemeColor(slug);
      seg.dataset.slug = p.slug;

      seg.addEventListener('mouseenter', function() {
        tooltip.querySelector('.tt-name').textContent = p.name;
        tooltip.querySelector('.tt-span').textContent = p.start_year + '\u2013' + (p.status === 'active' ? 'present' : (p.end_year || '?'));
        const desc = p.description || '';
        tooltip.querySelector('.tt-desc').textContent = desc.length > 120 ? desc.slice(0, 120) + '\u2026' : desc;
        tooltip.classList.add('visible');
      });
      seg.addEventListener('mousemove', positionTooltip);
      seg.addEventListener('mouseleave', function() { tooltip.classList.remove('visible'); });
      seg.addEventListener('click', function(e) { e.stopPropagation(); selectTimelineTheme(slug, p.slug); });

      trackRow.appendChild(seg);
    });

    trackRow.addEventListener('click', function() { selectTimelineTheme(slug, null); });
    researchTracksWrap.appendChild(trackRow);
  });

  tracksCol.appendChild(researchTracksWrap);

  // ── People section ──
  function addPersonSection(title, people, isAlumni, collapsible) {
    if (!people.length) return;

    if (collapsible) {
      const yearRange = people.reduce((acc, p) => {
        const s = parseInt(p.start_date) || 9999, e = parseInt(p.end_date) || 0;
        return { min: Math.min(acc.min, s), max: Math.max(acc.max, e) };
      }, { min: 9999, max: 0 });
      const rangeStr = (yearRange.min < 9999 ? yearRange.min : '?') + '\u2013' + (yearRange.max > 0 ? yearRange.max : '?');

      const toggleLabel = document.createElement('div');
      toggleLabel.className = 'alumni-toggle-label';
      toggleLabel.style.marginTop = '24px';
      toggleLabel.textContent = title + ' (' + people.length + ', ' + rangeStr + ')';
      labelsCol.appendChild(toggleLabel);

      const toggleTrack = document.createElement('div');
      toggleTrack.style.height = '28px';
      toggleTrack.style.marginTop = '24px';
      tracksCol.appendChild(toggleTrack);

      const alumniLabelContainer = document.createElement('div');
      alumniLabelContainer.style.display = 'none';
      labelsCol.appendChild(alumniLabelContainer);

      const alumniTrackContainer = document.createElement('div');
      alumniTrackContainer.style.display = 'none';
      tracksCol.appendChild(alumniTrackContainer);

      toggleLabel.addEventListener('click', function() {
        const open = alumniLabelContainer.style.display !== 'none';
        alumniLabelContainer.style.display = open ? 'none' : 'block';
        alumniTrackContainer.style.display = open ? 'none' : 'block';
        toggleLabel.classList.toggle('open', !open);
      });

      const innerTrackWrap = document.createElement('div');
      innerTrackWrap.style.position = 'relative';
      addGridlines(innerTrackWrap);
      addNowLine(innerTrackWrap);

      people.forEach(p => {
        const { labelEl, trackEl } = makePersonElements(p, isAlumni);
        alumniLabelContainer.appendChild(labelEl);
        innerTrackWrap.appendChild(trackEl);
      });
      alumniTrackContainer.appendChild(innerTrackWrap);
      return;
    }

    // Non-collapsible: divider + rows
    const divL = document.createElement('div');
    divL.className = 'timeline-divider';
    divL.innerHTML = '<span class="divider-label">' + title + '</span>';
    labelsCol.appendChild(divL);

    const divR = document.createElement('div');
    divR.className = 'timeline-divider';
    divR.innerHTML = '&nbsp;';
    tracksCol.appendChild(divR);

    const trackWrap = document.createElement('div');
    trackWrap.style.position = 'relative';
    addGridlines(trackWrap);
    addNowLine(trackWrap);

    people.forEach(p => {
      const { labelEl, trackEl } = makePersonElements(p, isAlumni);
      labelsCol.appendChild(labelEl);
      trackWrap.appendChild(trackEl);
    });
    tracksCol.appendChild(trackWrap);
  }

  function makePersonElements(p, isAlumni) {
    const themes = getPersonThemes(p.slug);
    const primary = getPrimaryTheme(themes);
    const color = primary ? getThemeColor(primary) : '#9ca3af';

    const startYr = parseInt(p.start_date) || minYear;
    const endYr = isAlumni ? (parseInt(p.end_date) || currentYear) : currentYear;
    const startPct = Math.max(0, ((startYr - minYear) / totalYears) * 100);
    const endPct = Math.min(100, ((endYr - minYear + 1) / totalYears) * 100);
    const widthPct = Math.max(endPct - startPct, 1.2);

    const labelEl = document.createElement('div');
    labelEl.className = 'tl-label-row';
    labelEl.dataset.person = p.slug;
    if (selectedPerson === p.slug) labelEl.classList.add('selected');
    labelEl.innerHTML = '<div style="text-align:right"><div class="ptl-name">' + escHTML(p.name) + '</div><div class="ptl-role">' + escHTML(p.role) + '</div></div>';
    labelEl.addEventListener('click', function() { selectPerson(p.slug); });

    const trackEl = document.createElement('div');
    trackEl.className = 'tl-track-row';
    trackEl.dataset.person = p.slug;
    if (selectedPerson === p.slug) trackEl.classList.add('selected');

    const bar = document.createElement('div');
    bar.className = 'people-timeline-bar' + (isAlumni ? ' alumni-bar' : '');
    bar.style.left = startPct + '%';
    bar.style.width = widthPct + '%';
    bar.style.backgroundColor = color;

    const themeNames = Object.keys(themes).map(t => findLabel('themes', t));
    bar.addEventListener('mouseenter', function() {
      tooltip.querySelector('.tt-name').textContent = p.name;
      tooltip.querySelector('.tt-span').textContent = p.role + ' \u00b7 ' + (p.start_date || '?') + '\u2013' + (isAlumni ? (p.end_date || '?') : 'present');
      const descParts = [];
      if (themeNames.length) descParts.push('Research: ' + themeNames.join(', '));
      if (isAlumni && p.current_position) descParts.push('Now: ' + p.current_position);
      tooltip.querySelector('.tt-desc').textContent = descParts.join('. ');
      tooltip.classList.add('visible');
    });
    bar.addEventListener('mousemove', positionTooltip);
    bar.addEventListener('mouseleave', function() { tooltip.classList.remove('visible'); });

    trackEl.appendChild(bar);
    trackEl.addEventListener('click', function() { selectPerson(p.slug); });

    return { labelEl, trackEl };
  }

  // Sort and render people sections
  const ROLE_SORT = ['PI', 'Postdoc', 'PhD Student', 'MSc Student', 'Technician', 'Lab Manager', 'Other'];
  function sortByRole(arr) {
    arr.sort((a, b) => {
      const ra = ROLE_SORT.indexOf(a.role), rb = ROLE_SORT.indexOf(b.role);
      if (ra !== rb) return (ra === -1 ? 99 : ra) - (rb === -1 ? 99 : rb);
      return (parseInt(a.start_date) || 9999) - (parseInt(b.start_date) || 9999);
    });
  }

  const activePeople = DATA.people.filter(p => p.status === 'active');
  const collaborators = DATA.people.filter(p => p.status === 'collaborator');
  const alumni = DATA.people.filter(p => p.status === 'alumni');

  sortByRole(activePeople);
  sortByRole(collaborators);
  alumni.sort((a, b) => {
    const ya = parseInt(a.end_date) || 0, yb = parseInt(b.end_date) || 0;
    if (yb !== ya) return yb - ya;
    return a.name.localeCompare(b.name);
  });

  addPersonSection('People', activePeople, false, false);
  if (collaborators.length) addPersonSection('Collaborators', collaborators, false, true);
  if (alumni.length) addPersonSection('Alumni', alumni, true, true);

}

function scrollTimelineToPresent() {
  const scrollEl = document.getElementById('tl-scroll');
  if (!scrollEl) return;
  const nowPct = (TL_CURRENT_YEAR - TL_MIN_YEAR) / TL_TOTAL_YEARS;
  const targetX = scrollEl.scrollWidth * nowPct - scrollEl.clientWidth * 0.5;
  scrollEl.scrollLeft = Math.max(0, targetX);
}

function selectTimelineTheme(slug, projectSlug) {
  if (selectedTimelineTheme === slug && !projectSlug) {
    // Deselect
    selectedTimelineTheme = null;
    filters.themes.clear();
  } else {
    selectedTimelineTheme = slug;
    AXES.forEach(a => filters[a].clear());
    filters.themes.add(slug);
  }
  updateURL();
  render();
  renderFullTimeline();

  if (projectSlug) {
    // Scroll to projects and expand the target card
    setTimeout(function() {
      const cards = document.querySelectorAll('.project-card');
      for (const card of cards) {
        const title = card.querySelector('.card-title');
        const proj = DATA.projects.find(p => p.slug === projectSlug);
        if (proj && title && title.textContent === proj.name) {
          card.classList.add('expanded');
          const detail = card.querySelector('.card-detail');
          if (detail) detail.classList.add('open');
          card.scrollIntoView({ behavior: 'smooth', block: 'center' });
          break;
        }
      }
    }, 50);
  } else {
    const projContainer = document.getElementById('projects-container');
    if (projContainer) projContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

// ── Init ──
buildFilterPills();
readURL();
renderFullTimeline();
render();
scrollTimelineToPresent();
window.addEventListener('hashchange', () => {
  AXES.forEach(a => filters[a].clear());
  readURL();
  render();
});
</script>
</body>
</html>'''

# ── Build ──

def build():
    print("Loading taxonomy...")
    taxonomy = load_taxonomy()
    theme_children = build_theme_children(taxonomy)
    for axis, items in taxonomy.items():
        total = sum(1 + len(i.get("children", [])) for i in items)
        print(f"  {axis}: {total} tags")

    print("Loading people...")
    people = load_people()
    active = [p for p in people if p["status"] == "active"]
    alumni = [p for p in people if p["status"] == "alumni"]
    collabs = [p for p in people if p["status"] == "collaborator"]
    print(f"  {len(active)} active, {len(collabs)} collaborators, {len(alumni)} alumni ({len(people)} total)")

    print("Loading publications...")
    pubs = load_publications()
    print(f"  {len(pubs)} publications")

    print("Loading projects...")
    projects = load_projects()
    print(f"  {len(projects)} projects")

    print("Linking papers to projects...")
    link_papers_to_projects(projects, pubs, theme_children)
    active_proj = [p for p in projects if p["status"] == "active"]
    completed_proj = [p for p in projects if p["status"] != "active"]
    print(f"  {len(active_proj)} active, {len(completed_proj)} completed/other")

    print("Generating narratives...")
    narratives = generate_narratives(taxonomy, projects, pubs, people, theme_children)
    overrides = load_overrides()
    generated_count = len(narratives)
    for slug, body in overrides.items():
        narratives[slug] = body
    print(f"  {len(narratives)} narratives ({generated_count - len(overrides)} generated, {len(overrides)} hand-written overrides)")

    # Fields allowed in public JSON (no internal IDs, paths, or type)
    site_data = {
        "taxonomy": taxonomy,
        "projects": [{
            "slug": p["slug"], "name": p["name"], "status": p["status"],
            "description": p["description"],
            "start_year": p["start_year"], "end_year": p["end_year"],
            "themes": p["themes"], "methods": p["methods"], "scale": p["scale"],
            "organisms": p["organisms"], "settings": p["settings"],
            "participants": p["people"], "papers": p["papers"], "paper_count": p["paper_count"],
        } for p in projects],
        "publications": [{
            "slug": p["slug"], "title": p["title"], "year": p["year"],
            "authors": p["authors"], "journal": p["journal"],
            "doi": p["doi"], "citations": p["citations"],
            "themes": p["themes"], "methods": p["methods"],
        } for p in pubs],
        "people": [{
            "slug": p["slug"], "name": p["name"], "status": p["status"],
            "role": p["role"], "current_position": p["current_position"],
            "start_date": p["start_date"], "end_date": p["end_date"],
        } for p in people],
        "narratives": narratives,
    }

    print("Generating lab intro...")
    lab_intro = generate_lab_intro(people, projects, taxonomy)
    print(f"  {lab_intro}")

    json_blob = json.dumps(site_data, ensure_ascii=False, separators=(",", ":"))
    print(f"  JSON blob: {len(json_blob):,} bytes")

    html = HTML_TEMPLATE.replace("__SITE_DATA_PLACEHOLDER__", json_blob)
    html = html.replace("__LAB_INTRO_PLACEHOLDER__", esc(lab_intro))
    out_path = WEB / "index.html"
    out_path.write_text(html)
    print(f"\nDone. {len(html):,} bytes written to {out_path}")

if __name__ == "__main__":
    build()
