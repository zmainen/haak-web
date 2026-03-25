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

import json, re, sys, html as html_mod, hashlib, subprocess, time, argparse, shutil, urllib.request
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
import markdown as md_lib

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

QUALITY_TO_ROLE = {
    "principal-investigator": "Principal Investigator",
    "postdoc": "Postdoc", "phd-student": "PhD Student",
    "msc-student": "MSc Student", "bsc-student": "BSc Student", "student": "MSc Student",
    "technician": "Technician", "research-assistant": "Research Assistant",
    "lab-manager": "Lab Manager",
    "visiting-scientist": "Visiting Scientist", "collaborator": "Collaborator",
    "summer-student": "Summer Student",
    "project-lead": "Project Lead", "first-author": "First Author",
    "senior-author": "Senior Author", "corresponding-author": "Corresponding Author",
    "author": "Author", "contributor": "Contributor",
}

def quality_to_role(quality_str):
    return QUALITY_TO_ROLE.get(quality_str, quality_str.replace("-", " ").title())

def read_situation_frontmatter(path):
    idx = Path(path) / "index.md"
    try:
        meta, _ = parse_frontmatter(idx.read_text(errors="replace"))
    except (FileNotFoundError, OSError):
        return []
    if meta.get("type") != "situation" or not meta.get("belongings"):
        return []
    return [
        {k: b.get(k) for k in ("entity", "quality", "since", "until")}
        for b in meta["belongings"] if isinstance(b, dict) and b.get("entity")
    ]

def esc(s):
    return html_mod.escape(str(s)) if s else ""

def _md_link_replace(m):
    text, url = m.group(1), m.group(2)
    if url.startswith('#'):
        return f'<a href="{url}">{text}</a>'
    return f'<a href="{url}" target="_blank" rel="noopener">{text}</a>'

def md_links_to_html(text):
    """Convert markdown [text](url) links to HTML <a> tags.
    In-page anchors (#...) stay same-tab; external links open new tab."""
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', _md_link_replace, text)

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

def normalize_role(raw):
    """Normalize free-text role strings via heuristics, falling through to quality_to_role."""
    r = raw.lower().strip()
    if not r: return "Other"
    if "principal" in r or r == "pi": return "PI"
    if "postdoc" in r: return "Postdoc"
    if "phd" in r: return "PhD Student"
    if "msc" in r or "bsc" in r: return "MSc Student"
    if "technician" in r or "tech" in r or "assistant" in r: return "Technician"
    if "lab manager" in r or "admin" in r: return "Lab Manager"
    return quality_to_role(r)

ROLE_ORDER = ["PI", "Postdoc", "PhD Student", "MSc Student", "Technician", "Lab Manager", "Other"]


# ── Publication-to-person matching ──

def match_pubs_to_people(publications, people):
    result = defaultdict(list)
    last_names = {}
    for p in people:
        parts = p["name"].strip().split()
        if parts:
            last_names[p["slug"]] = parts[-1].lower()
    name_counts = defaultdict(int)
    for ln in last_names.values():
        name_counts[ln] += 1
    for slug, ln in last_names.items():
        if name_counts[ln] > 1:
            continue
        for pub in publications:
            for author in pub["authors"]:
                if re.search(r'\b' + re.escape(ln) + r'\b', author.lower()):
                    result[slug].append(pub["slug"])
                    break
    return dict(result)

def match_pubs_to_people_via_belongings(publications):
    result = defaultdict(list)
    for pub in publications:
        for b in pub.get("belongings") or []:
            if isinstance(b, dict) and b.get("entity"):
                result[b["entity"]].append(pub["slug"])
    return dict(result)

def compute_collab_years(person, matched_pubs, publications):
    pub_by_slug = {p["slug"]: p for p in publications}
    years = [pub_by_slug[s]["year"] for s in matched_pubs if s in pub_by_slug and pub_by_slug[s]["year"]]
    if not years:
        return (None, None)
    ongoing = person.get("status") == "collaborator" and not person.get("end_date")
    last_year = None if ongoing else max(years)
    return (min(years), last_year)

def extract_institution(current_position):
    if not current_position:
        return ""
    if "," in current_position:
        return current_position.split(",", 1)[1].strip()
    return current_position

# ── Loaders ──

def load_people():
    # Build lookup from lab-level situation frontmatter (supports multiple stints per entity)
    sit = read_situation_frontmatter(LAB)
    sit_lookup = {}
    for b in sit:
        sit_lookup.setdefault(b["entity"], []).append(b)

    people = []
    for f in sorted((LAB / "people").glob("*/person.yaml")):
        d = load_yaml(f.read_text(errors="replace")) or {}
        if not d.get("name"): continue
        slug = f.parent.name
        stints = sit_lookup.get(slug)
        if stints:
            # Latest stint determines role and status
            latest = max(stints, key=lambda s: int(str(s.get("since") or 0)[:4]))
            role = quality_to_role(latest["quality"])
            # Full span across all stints for timeline
            all_starts = [int(str(s["since"])[:4]) for s in stints if s.get("since")]
            all_ends = [str(s["until"])[:4] for s in stints if s.get("until")]
            start = str(min(all_starts)) if all_starts else str(d.get("start_date", ""))[:4] or None
            end = max(all_ends) if all_ends and len(all_ends) == len(stints) else str(d.get("end_date", ""))[:4] or None
            if all(s.get("until") for s in stints):
                status = "alumni"
            elif latest["quality"] == "collaborator":
                status = "collaborator"
            else:
                status = "active"
        else:
            role = normalize_role(d.get("role", ""))
            start = str(d.get("start_date", ""))[:4] or None
            end = str(d.get("end_date", ""))[:4] or None
            status = d.get("status", "unknown")
        people.append({
            "slug": slug,
            "name": d["name"],
            "status": status,
            "role": role,
            "start_date": start,
            "end_date": end,
            "current_position": d.get("current_position", ""),
            "email": (d.get("email") or "").split(";")[0].strip(),
            "orcid": d.get("orcid", ""),
            "s2_id": str(d["s2_id"]) if d.get("s2_id") else "",
            "google_scholar": d.get("google_scholar", ""),
            "institutional_url": d.get("institutional_url", ""),
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
            "belongings": meta.get("belongings", []),
        })
    pubs.sort(key=lambda p: (-p["year"], -p["citations"]))
    return pubs

# ── Semantic Scholar cache ──

S2_CACHE_PATH = WEB / ".s2-cache.json"
S2_API = "https://api.semanticscholar.org/graph/v1/author/{}/papers?fields=title,year,venue,externalIds,citationCount,authors&limit=1000"
S2_CACHE_TTL = 7 * 86400  # 7 days

def fetch_s2_publications(people):
    cache = json.loads(S2_CACHE_PATH.read_text()) if S2_CACHE_PATH.exists() else {}
    now = datetime.now(timezone.utc).timestamp()
    result = {}
    fetched = 0
    errors = []
    for person in people:
        s2_id = person.get("s2_id", "")
        if not s2_id:
            continue
        slug = person["slug"]
        cached = cache.get(s2_id)
        if cached and (now - cached.get("retrieved_ts", 0)) < S2_CACHE_TTL:
            result[slug] = cached["papers"]
            continue
        url = S2_API.format(s2_id)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "mainenlab-site-builder/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            papers = []
            for p in data.get("data", []):
                ext = p.get("externalIds") or {}
                authors = [a.get("name", "") for a in (p.get("authors") or [])]
                papers.append({
                    "title": p.get("title", ""),
                    "year": p.get("year"),
                    "venue": p.get("venue", ""),
                    "doi": ext.get("DOI", ""),
                    "citation_count": p.get("citationCount", 0),
                    "authors": authors,
                })
            cache[s2_id] = {"papers": papers, "retrieved_ts": now, "retrieved": datetime.now(timezone.utc).strftime("%Y-%m-%d")}
            result[slug] = papers
            fetched += 1
            print(f"    {slug}: {len(papers)} papers")
        except Exception as e:
            errors.append(f"{slug} ({s2_id}): {e}")
            if cached:
                result[slug] = cached["papers"]
        time.sleep(0.5)
    S2_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":")))
    print(f"  S2: {len(result)} people with data, {fetched} fetched, {len(errors)} errors")
    for err in errors[:5]:
        print(f"    error: {err}")
    return result

# ── Bio loader ──

def load_bios(people_dir):
    bios = {}
    converter = md_lib.Markdown(extensions=["extra"])
    for bio_path in people_dir.glob("*/bio.md"):
        slug = bio_path.parent.name
        text = bio_path.read_text(errors="replace")
        _, body = parse_frontmatter(text)
        if body.strip():
            converter.reset()
            bios[slug] = converter.convert(body.strip())
    return bios

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
        people_roles = {}
        belongings = read_situation_frontmatter(f.parent)
        if belongings:
            for b in belongings:
                people_ids.append(b["entity"])
                if b.get("quality"): people_roles[b["entity"]] = b["quality"]
        else:
            for p in d.get("people", d.get("participants", [])):
                if isinstance(p, dict):
                    pid = p.get("person_id", p.get("id", ""))
                    if pid:
                        people_ids.append(pid)
                        if p.get("role"): people_roles[pid] = p["role"]
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
            "people_roles": people_roles,
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

NARRATIVE_CACHE_PATH = WEB / ".narrative-cache.json"

NARRATIVE_SYSTEM_PROMPT = """You are writing research theme narratives for the Mainen Lab website at Champalimaud Foundation, Lisbon. Each narrative describes a research theme spanning multiple projects and publications.

STRICT RULES:
- Write in FIRST PERSON PLURAL (we/our)
- Active projects: present tense. Completed work: past tense for findings, but keep the question alive.
- NO person names
- NO target journals, grants, or internal references
- NO unexpanded abbreviations on first use
- Expand: DRN->dorsal raphe nucleus, 5-HT->serotonin, PFC->prefrontal cortex, OFC->orbitofrontal cortex, IBL->International Brain Laboratory

STYLE:
- Scholarly but accessible -- like the best lab website prose
- Lead with the motivating scientific question
- Show how the theme evolved through different projects
- Mention key methods and findings naturally
- 2-3 paragraphs, not more

LINKING RULES:
- When citing a published paper, use markdown link format: [Author et al., Year](https://doi.org/DOI)
- When referencing a lab project, link to it: [project name](#project-slug)
- Only link papers that have DOIs (provided in the context below)
- First mention only -- don't re-link the same entity"""

def _get_anthropic_client():
    from anthropic import Anthropic
    result = subprocess.run(
        ['bash', '-c', 'source ~/.secrets && echo $ANTHROPIC_API_KEY'],
        capture_output=True, text=True)
    api_key = result.stdout.strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not found in ~/.secrets")
    return Anthropic(api_key=api_key)

def _narrative_input_hash(theme_projects, theme_pubs):
    blob = json.dumps({
        "projects": [(p["slug"], p["name"], p["description"], p["status"]) for p in theme_projects],
        "pubs": [(p["slug"], p["title"], p["year"]) for p in theme_pubs],
    }, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]

def _load_narrative_cache():
    if NARRATIVE_CACHE_PATH.exists():
        return json.loads(NARRATIVE_CACHE_PATH.read_text())
    return {}

def _save_narrative_cache(cache):
    NARRATIVE_CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False))

def _build_theme_data(slug, taxonomy, projects, pubs, theme_children):
    expanded = {slug}
    expanded.update(theme_children.get(slug, set()))
    for parent, children in theme_children.items():
        if slug in children: expanded.add(parent)
    theme_projects = [p for p in projects if set(p["themes"]) & expanded]
    theme_pubs = sorted(
        [p for p in pubs if set(p["themes"]) & expanded],
        key=lambda p: (-p.get("citations", 0), -p["year"])
    )
    return theme_projects, theme_pubs

def _generate_narrative_via_api(client, slug, label, theme_projects, theme_pubs):
    parts = [f"Write a narrative for this research theme:\n"]
    parts.append(f"Theme: {label}")
    proj_lines = []
    for p in sorted(theme_projects, key=lambda x: x["start_year"] or 9999):
        line = f"- {p['name']} [slug: {p['slug']}] ({p['status']}, {p['start_year'] or '?'})"
        if p.get("description"):
            line += f": {p['description'][:200]}"
        proj_lines.append(line)
    parts.append(f"Projects (link with #project-slug):\n" + "\n".join(proj_lines))
    if theme_pubs:
        pub_lines = []
        for p in theme_pubs[:8]:
            doi = p.get('doi', '')
            doi_str = f" -- DOI: {doi}" if doi else " -- no DOI (unpublished)"
            pub_lines.append(f"- {p['title']} ({p['year']}){doi_str}")
        parts.append(f"Key publications:\n" + "\n".join(pub_lines))
    methods = set()
    organisms = set()
    for p in theme_projects:
        methods.update(p.get("methods", []))
        organisms.update(p.get("organisms", []))
    if methods:
        parts.append(f"Methods used: {', '.join(sorted(methods))}")
    if organisms:
        parts.append(f"Organisms: {', '.join(sorted(organisms))}")
    parts.append("\nGenerate only the narrative text, nothing else.")

    response = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=600,
        system=NARRATIVE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": "\n".join(parts)}],
    )
    return response.content[0].text.strip()

def generate_narratives(taxonomy, projects, pubs, people, theme_children, regenerate=False):
    people_by_slug = {p["slug"]: p for p in people}
    narratives = {}
    all_theme_slugs = set()
    for t in taxonomy.get("themes", []):
        all_theme_slugs.add(t["slug"])
        for c in t.get("children", []):
            all_theme_slugs.add(c["slug"])

    cache = _load_narrative_cache()
    client = None
    api_calls = 0

    for slug in sorted(all_theme_slugs):
        theme_projects, theme_pubs = _build_theme_data(slug, taxonomy, projects, pubs, theme_children)
        if not theme_projects:
            continue

        input_hash = _narrative_input_hash(theme_projects, theme_pubs)
        cached = cache.get(slug, {})

        if not regenerate and cached.get("hash") == input_hash and cached.get("text"):
            narratives[slug] = cached["text"]
            continue

        if not regenerate:
            # Data hasn't changed or no cache — use fallback template
            label = slug.replace("-", " ").title()
            years = [y for p in theme_projects for y in [p["start_year"], p["end_year"]] if y]
            active_any = any(p["status"] == "active" for p in theme_projects)
            span = f"{min(years)}\u2013present" if (years and active_any) else (f"{min(years)}\u2013{max(years)}" if years else "")
            parts = []
            if span: parts.append(f"The lab's {label.lower()} research spans {span}.")
            if theme_projects:
                proj_strs = [f"{p['name']} ({p['start_year'] or '?'})" for p in sorted(theme_projects, key=lambda x: x["start_year"] or 9999)]
                parts.append(f"Projects: {'; '.join(proj_strs)}.")
            active_projects = [p for p in theme_projects if p["status"] == "active"]
            if active_projects:
                parts.append(f"{len(active_projects)} currently active project{'s' if len(active_projects) != 1 else ''}.")
            narratives[slug] = " ".join(parts)
            continue

        # Regenerate via API
        if client is None:
            client = _get_anthropic_client()
        label = slug.replace("-", " ").title()
        for t in taxonomy.get("themes", []):
            if t["slug"] == slug:
                label = t["label"]
                break
            for c in t.get("children", []):
                if c["slug"] == slug:
                    label = c["label"]
                    break

        print(f"    Generating narrative for {slug}...")
        text = _generate_narrative_via_api(client, slug, label, theme_projects, theme_pubs)
        narratives[slug] = text
        cache[slug] = {"hash": input_hash, "text": text}
        api_calls += 1
        time.sleep(1)  # rate limiting

    if api_calls > 0:
        _save_narrative_cache(cache)
        print(f"    {api_calls} narratives generated via API, cache updated")

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

def load_programs():
    programs_dir = LAB / "programs"
    if not programs_dir.exists(): return []
    converter = md_lib.Markdown(extensions=["extra"])
    programs = []
    for f in sorted(programs_dir.glob("*.md")):
        text = f.read_text(errors="replace")
        meta, body = parse_frontmatter(text)
        if not meta.get("title"): continue
        converter.reset()
        body_html = converter.convert(body.strip())
        span = meta.get("span", "")
        start_match = re.match(r'(\d{4})', str(span))
        sort_year = int(start_match.group(1)) if start_match else 9999
        programs.append({
            "slug": meta.get("slug", f.stem),
            "title": meta["title"],
            "span": span,
            "color": meta.get("color", "slate"),
            "status": meta.get("status", "active"),
            "themes": _as_list(meta.get("themes", [])),
            "projects": _as_list(meta.get("projects", [])),
            "repos": meta.get("repos", []),
            "body_html": body_html,
            "_sort_year": sort_year,
        })
    programs.sort(key=lambda p: p["_sort_year"], reverse=True)
    for p in programs: del p["_sort_year"]
    return programs

# ── Lab intro ──

def generate_lab_intro(people, projects, taxonomy):
    site_md = WEB / "site.md"
    if site_md.exists():
        text = site_md.read_text(errors="replace")
        _, body = parse_frontmatter(text)
        if body.strip():
            return body.strip()
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
<title>Mainen Systems Neuroscience Lab</title>
<meta name="description" content="The Mainen Lab at the Champalimaud Foundation studies how brains make decisions, interpret the world, and generate conscious experience.">
<link rel="icon" type="image/svg+xml" href="favicon.svg">
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
.narrative-block a { color: var(--accent); text-decoration: none; }
.narrative-block a:hover { text-decoration: underline; }
.lab-intro a { color: var(--accent); text-decoration: none; }
.lab-intro a:hover { text-decoration: underline; }

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
.card-description a { color: var(--accent); text-decoration: none; }
.card-description a:hover { text-decoration: underline; }
.card-pub-list { list-style: none; padding: 0; }
.card-pub-list li { font-size: 0.8rem; color: var(--muted); margin-bottom: 0.4rem; line-height: 1.5; }
.card-pub-list li a { color: var(--accent); text-decoration: none; }
.card-pub-list li a:hover { text-decoration: underline; }
.card-all-people { font-size: 0.82rem; margin-top: 0.5rem; }
.participant-role { font-size: 0.7rem; color: var(--muted); opacity: 0.7; font-style: italic; }
.expand-icon { color: var(--muted); font-size: 1rem; transition: transform 0.2s; flex-shrink: 0; }
.card-detail.open ~ .card-header .expand-icon,
.project-card.expanded .expand-icon { transform: rotate(180deg); }

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

/* Programs — mirrors project-card styling */
.programs-section { padding: 1.5rem 0 1rem; }
.program-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 8px; padding: 1rem 1.25rem; margin-bottom: 0.6rem;
  box-shadow: var(--shadow); border-left: 3px solid var(--muted);
  transition: box-shadow 0.15s;
}
.program-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
.program-card-header {
  display: flex; justify-content: space-between; align-items: flex-start;
  cursor: pointer; user-select: none;
}
.program-card-header .card-title { font-weight: 600; font-size: 0.95rem; }
.program-card-header .card-meta { display: flex; align-items: center; gap: 0.6rem; margin-top: 0.3rem; }
.program-card-header .card-span { font-size: 0.78rem; color: var(--muted); }
.program-summary { font-size: 0.82rem; color: var(--muted); line-height: 1.5; margin-top: 0.3rem; }
.program-body {
  max-height: 0; overflow: hidden; transition: max-height 0.35s ease;
}
.program-card.expanded .program-body { max-height: 3000px; }
.program-body-inner {
  padding-top: 0.75rem; border-top: 1px solid var(--border); margin-top: 0.75rem;
  font-size: 0.85rem; line-height: 1.6; color: var(--text);
}
.program-body-inner h1 { font-size: 1.05rem; font-weight: 600; margin: 1rem 0 0.4rem; }
.program-body-inner h2 { font-size: 0.95rem; font-weight: 600; margin: 0.8rem 0 0.35rem; }
.program-body-inner h3 { font-size: 0.88rem; font-weight: 600; margin: 0.6rem 0 0.25rem; }
.program-body-inner p { margin-bottom: 0.6rem; }
.program-body-inner ul, .program-body-inner ol { margin: 0.4rem 0 0.6rem 1.2rem; }
.program-body-inner li { margin-bottom: 0.3rem; }
.program-body-inner em { font-style: italic; }
.program-body-inner strong { font-weight: 600; }
.program-body-inner a { color: var(--accent); text-decoration: none; }
.program-body-inner a:hover { text-decoration: underline; }
.program-card .expand-icon { color: var(--muted); font-size: 1rem; transition: transform 0.2s; flex-shrink: 0; }
.program-card.expanded .expand-icon { transform: rotate(180deg); }

/* Bio modal */
.bio-modal {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0; z-index: 200;
  background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center;
  animation: bioFadeIn 0.15s ease;
}
@keyframes bioFadeIn { from { opacity: 0; } to { opacity: 1; } }
.bio-modal-content {
  background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px;
  padding: 1.5rem 1.75rem; max-width: 700px; width: 90%; max-height: 80vh;
  overflow-y: auto; position: relative; box-shadow: 0 8px 30px rgba(0,0,0,0.2);
  font-size: 0.88rem; line-height: 1.6; color: var(--text);
}
.bio-close {
  position: absolute; top: 0.75rem; right: 0.75rem; background: none; border: none;
  font-size: 1.4rem; cursor: pointer; color: var(--muted); line-height: 1;
}
.bio-close:hover { color: var(--text); }
.bio-modal-content h2 { font-size: 1.1rem; font-weight: 600; margin-bottom: 0.4rem; }
.bio-modal-content .bio-institution { color: var(--muted); font-size: 0.85rem; margin-bottom: 0.6rem; }
.bio-modal-content .bio-institution a { color: var(--accent); text-decoration: none; }
.bio-modal-content .bio-institution a:hover { text-decoration: underline; }
.bio-modal-content .bio-lab-role { font-size: 0.85rem; margin-bottom: 0.6rem; }
.bio-modal-content .bio-section-title { font-size: 0.78rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); margin: 0.8rem 0 0.3rem; }
.bio-modal-content .bio-pub-list { list-style: none; padding: 0; }
.bio-modal-content .bio-pub-list li { font-size: 0.82rem; color: var(--muted); margin-bottom: 0.4rem; line-height: 1.5; }
.bio-modal-content .bio-pub-list li a { color: var(--accent); text-decoration: none; }
.bio-modal-content .bio-pub-list li a:hover { text-decoration: underline; }
.bio-modal-content .bio-project-list { list-style: none; padding: 0; display: flex; flex-wrap: wrap; gap: 0.3rem; }
.bio-modal-content .bio-project-list li {
  font-size: 0.78rem; padding: 0.2rem 0.55rem; border-radius: 999px;
  border: 1px solid var(--border); cursor: pointer; color: var(--accent);
}
.bio-modal-content .bio-project-list li:hover { background: var(--hover); }
.person-link { cursor: pointer; color: var(--accent); text-decoration: none; }
.person-link:hover { text-decoration: underline; }

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
  <h1>Mainen Systems Neuroscience Lab</h1>
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

<div id="bio-modal" class="bio-modal" style="display:none">
  <div class="bio-modal-content">
    <button class="bio-close">&times;</button>
    <div id="bio-content"></div>
  </div>
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

<!-- Research Programs -->
<div class="programs-section" id="programs-section">
  <div class="section-heading">Research Programs</div>
  <div id="programs-container"></div>
</div>

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
    block.innerHTML = '<h4>' + findLabel('themes', slug) + '</h4><p>' + text + '</p>';
    area.appendChild(block);
  });
}

function escHTML(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function stripTags(s) {
  const d = document.createElement('div');
  d.innerHTML = s;
  return d.textContent || '';
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
  card.id = 'project-' + p.slug;
  const span = p.start_year ? (p.status === 'active' ? p.start_year + '\u2013present' : p.start_year + (p.end_year ? '\u2013' + p.end_year : '')) : '';
  const peopleBySlug = {};
  DATA.people.forEach(pe => peopleBySlug[pe.slug] = pe);
  const roles = p.participant_roles || {};
  function personLink(s) {
    const pe = peopleBySlug[s];
    if (!pe) return escHTML(s);
    return '<span class="person-link" onclick="event.stopPropagation();showBio(\'' + s + '\')">' + escHTML(pe.name) + '</span>';
  }
  function personWithRole(s) {
    const role = roles[s];
    return personLink(s) + (role ? ' <span class="participant-role">' + escHTML(role) + '</span>' : '');
  }
  const keyPeople = (p.participants || []).slice(0, 3).map(personLink).join(', ');
  const allPeople = (p.participants || []).map(personWithRole).join(', ');

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
        '<div class="card-title">' + escHTML(p.name) + ' <a href="http://127.0.0.1:18832/situation?path=home/zach/projects/mainen-lab/projects/' + p.slug + '/index.md" onclick="event.stopPropagation()" style="font-size:0.75em;color:#999;text-decoration:none" title="Edit in situation editor">&#9998;</a></div>' +
        '<div class="card-meta">' +
          (span ? '<span class="card-span">' + span + '</span>' : '') +
          '<span class="status-pill ' + p.status + '">' + p.status + '</span>' +
        '</div>' +
        (keyPeople ? '<div class="card-people">' + keyPeople + '</div>' : '') +
        (p.description ? '<div class="card-desc-preview">' + escHTML(stripTags(p.description).length > 150 ? stripTags(p.description).slice(0, 150) + '\u2026' : stripTags(p.description)) + '</div>' : '') +
        (p.paper_count ? '<div class="card-papers">' + p.paper_count + ' publication' + (p.paper_count !== 1 ? 's' : '') + '</div>' : '') +
        '<div class="card-tags">' + tags.join('') + '</div>' +
      '</div>' +
      '<span class="expand-icon">&#9662;</span>' +
    '</div>' +
    '<div class="card-detail">' +
      '<div class="card-detail-inner">' +
        (p.description ? '<div class="card-description">' + p.description + '</div>' : '') +
        (pubListHTML ? '<ul class="card-pub-list">' + pubListHTML + '</ul>' : '') +
        (allPeople ? '<div class="card-all-people"><strong>People:</strong> ' + allPeople + '</div>' : '') +
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

function getPersonProgramColor(slug) {
  try {
    if (!DATA.programs || !DATA.projects) return '#9ca3af';
    const themeCounts = {};
    DATA.projects.forEach(p => {
      if ((p.participants || []).indexOf(slug) === -1) return;
      (p.themes || []).forEach(t => { themeCounts[t] = (themeCounts[t] || 0) + 1; });
    });
    let best = null, max = 0;
    DATA.programs.forEach(prog => {
      if (!prog || !prog.themes) return;
      let count = 0;
      prog.themes.forEach(t => { count += themeCounts[t] || 0; });
      if (count > max) { max = count; best = prog; }
    });
    if (!best || !best.color) return '#9ca3af';
    return PROGRAM_COLORS[best.color] || '#9ca3af';
  } catch(e) { return '#9ca3af'; }
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
        const desc = stripTags(p.description || '');
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
    const color = getPersonProgramColor(p.slug);

    const isCollab = p.status === 'collaborator';
    let startYr, endYr;
    if (isCollab && p.collab_years && p.collab_years[0]) {
      startYr = p.collab_years[0];
      endYr = p.collab_years[1] || currentYear;
    } else {
      startYr = parseInt(p.start_date) || minYear;
      endYr = isAlumni ? (parseInt(p.end_date) || currentYear) : currentYear;
    }
    const startPct = Math.max(0, ((startYr - minYear) / totalYears) * 100);
    const endPct = Math.min(100, ((endYr - minYear + 1) / totalYears) * 100);
    const widthPct = Math.max(endPct - startPct, 1.2);

    const subtitle = (p.status === 'active') ? p.role : (p.institution || p.role);
    const labelEl = document.createElement('div');
    labelEl.className = 'tl-label-row';
    labelEl.dataset.person = p.slug;
    if (selectedPerson === p.slug) labelEl.classList.add('selected');
    labelEl.innerHTML = '<div style="text-align:right"><div class="ptl-name person-link" onclick="event.stopPropagation();showBio(\'' + p.slug + '\')">' + escHTML(p.name) + '</div><div class="ptl-role">' + escHTML(subtitle) + '</div></div>';
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

    let themeNames = [];
    try {
      const personProjects = DATA.projects.filter(pr => (pr.participants || []).indexOf(slug) !== -1);
      const themeSlugs = [...new Set(personProjects.flatMap(pr => pr.themes || []))];
      themeNames = themeSlugs.map(t => findLabel('themes', t));
    } catch(e) {}
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
    setTimeout(function() { scrollToProject(projectSlug); }, 50);
  } else {
    const projContainer = document.getElementById('projects-container');
    if (projContainer) projContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

// ── Programs ──
const PROGRAM_COLORS = {
  slate: '#64748b', amber: '#d97706', indigo: '#6366f1',
  teal: '#14b8a6', violet: '#8b5cf6', blue: '#3b82f6'
};

function renderPrograms() {
  const container = document.getElementById('programs-container');
  if (!container || !DATA.programs) return;
  container.innerHTML = '';
  DATA.programs.forEach(prog => {
    const color = PROGRAM_COLORS[prog.color] || '#64748b';
    const card = document.createElement('div');
    card.className = 'program-card';
    card.style.borderLeftColor = color;

    // Extract first paragraph from body_html as summary
    const tmp = document.createElement('div');
    tmp.innerHTML = prog.body_html;
    let summary = '';
    const firstP = tmp.querySelector('p');
    if (firstP) summary = firstP.textContent;
    if (summary.length > 200) summary = summary.slice(0, 200) + '\u2026';

    card.innerHTML =
      '<div class="program-card-header" onclick="this.parentElement.classList.toggle(\'expanded\')">' +
        '<div>' +
          '<div class="card-title">' + escHTML(prog.title) + '</div>' +
          '<div class="card-meta">' +
            '<span class="card-span">' + escHTML(prog.span) + '</span>' +
          '</div>' +
        '</div>' +
        '<span class="expand-icon">&#9662;</span>' +
      '</div>' +
      '<div class="program-summary">' + escHTML(summary) + '</div>' +
      '<div class="program-body"><div class="program-body-inner">' + prog.body_html + '</div></div>';

    container.appendChild(card);
  });
}

// ── Project slug set for anchor resolution ──
const PROJECT_SLUGS = new Set(DATA.projects.map(p => p.slug));

// ── Scroll to project helper ──
function scrollToProject(slug) {
  const card = document.getElementById('project-' + slug);
  if (!card) return;
  // If inside a closed <details>, open it
  const details = card.closest('details');
  if (details && !details.open) details.open = true;
  card.classList.add('expanded');
  const detail = card.querySelector('.card-detail');
  if (detail) detail.classList.add('open');
  card.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// ── Hash-based navigation ──
function handleHash() {
  const hash = window.location.hash.slice(1);
  if (!hash) return;

  // #project-<slug> -> scroll to and expand that card
  const projectMatch = hash.match(/^project-(.+)$/);
  if (projectMatch) {
    setTimeout(function() { scrollToProject(projectMatch[1]); }, 100);
    return;
  }

  // Bare slug that matches a project
  if (PROJECT_SLUGS.has(hash)) {
    setTimeout(function() { scrollToProject(hash); }, 100);
    return;
  }

  // #themes=<slug>,<slug2>&methods=... -> activate filters
  AXES.forEach(function(a) { filters[a].clear(); });
  hash.split('&').forEach(function(part) {
    const eq = part.indexOf('=');
    if (eq === -1) return;
    const axis = part.slice(0, eq), vals = part.slice(eq + 1);
    if (filters[axis] && vals) vals.split(',').forEach(function(v) { filters[axis].add(v); });
  });
  render();
}

// ── Handle in-page link clicks ──
document.addEventListener('click', function(e) {
  const anchor = e.target.closest('a[href^="#"]');
  if (!anchor) return;
  const href = anchor.getAttribute('href');
  const bare = href.slice(1); // strip #

  // #project-<slug>
  const projectMatch = bare.match(/^project-(.+)$/);
  if (projectMatch) {
    e.preventDefault();
    history.pushState(null, '', href);
    scrollToProject(projectMatch[1]);
    return;
  }

  // #themes=<slug>,<slug2>
  const themeMatch = bare.match(/^themes=(.+)$/);
  if (themeMatch) {
    e.preventDefault();
    history.pushState(null, '', href);
    AXES.forEach(function(ax) { filters[ax].clear(); });
    themeMatch[1].split(',').forEach(function(v) { filters.themes.add(v); });
    render();
    renderFullTimeline();
    return;
  }

  // Bare slug that matches a project (e.g. #5ht-neuropixels)
  if (PROJECT_SLUGS.has(bare)) {
    e.preventDefault();
    history.pushState(null, '', '#project-' + bare);
    scrollToProject(bare);
    return;
  }
});

// ── Bio modal ──
function showBio(slug) {
  const p = DATA.people.find(x => x.slug === slug);
  if (!p) return;
  const modal = document.getElementById('bio-modal');
  const content = document.getElementById('bio-content');
  let html = '<h2>' + escHTML(p.name) + '</h2>';
  if (p.current_position) {
    let instHtml = escHTML(p.current_position);
    if (p.institution_url) {
      instHtml = '<a href="' + p.institution_url + '" target="_blank" rel="noopener">' + instHtml + '</a>';
    }
    html += '<div class="bio-institution">' + instHtml + '</div>';
  }
  const startYr = p.start_date || '?';
  const endYr = p.status === 'active' ? 'present' : (p.end_date || '?');
  html += '<div class="bio-lab-role">' + escHTML(p.role) + ', ' + startYr + '\u2013' + endYr + '</div>';
  if (p.papers && p.papers.length) {
    html += '<div class="bio-section-title">Publications with the lab</div>';
    html += '<ul class="bio-pub-list">';
    const sorted = p.papers.slice().sort((a, b) => b.year - a.year);
    sorted.forEach(pub => {
      const full = DATA.publications.find(x => x.slug === pub.slug);
      const authors = full ? full.authors : [];
      const firstAuthor = authors.length ? authors[0].split(',')[0] : '';
      const authorStr = authors.length > 2 ? firstAuthor + ' et al.' : authors.map(a => a.split(',')[0]).join(', ');
      const titleHtml = pub.doi
        ? '<a href="https://doi.org/' + pub.doi + '" target="_blank">' + escHTML(pub.title) + '</a>'
        : escHTML(pub.title);
      html += '<li>' + authorStr + ' (' + pub.year + '). ' + titleHtml + '. <em>' + escHTML(pub.journal) + '</em></li>';
    });
    html += '</ul>';
  }
  if (p.projects && p.projects.length) {
    html += '<div class="bio-section-title">Projects</div>';
    html += '<ul class="bio-project-list">';
    p.projects.forEach(proj => {
      html += '<li onclick="document.getElementById(\'bio-modal\').style.display=\'none\';scrollToProject(\'' + proj.slug + '\')">' + escHTML(proj.name) + '</li>';
    });
    html += '</ul>';
  }
  html += '<div style="margin-top:1rem;font-size:0.85rem"><a href="people/' + slug + '.html" style="color:var(--accent)">Full profile &rarr;</a></div>';
  content.innerHTML = html;
  modal.style.display = 'flex';
}
document.getElementById('bio-modal').addEventListener('click', function(e) {
  if (e.target === this) this.style.display = 'none';
});
document.querySelector('.bio-close').addEventListener('click', function() {
  document.getElementById('bio-modal').style.display = 'none';
});
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') document.getElementById('bio-modal').style.display = 'none';
});

// ── Init ──
buildFilterPills();
renderPrograms();
renderFullTimeline();
handleHash();
render();
scrollTimelineToPresent();
window.addEventListener('hashchange', () => {
  handleHash();
});
</script>
</body>
</html>'''

# ── Citation linking in program bodies ──

def link_citations_in_programs(programs):
    """Post-process program body_html to link in-text citations to bibliography entries."""
    for prog in programs:
        html = prog["body_html"]
        slug = prog["slug"]
        # Extract <ol>...</ol> blocks (key publications are numbered lists)
        ol_pattern = re.compile(r'(<ol>)(.*?)(</ol>)', re.DOTALL)
        ol_match = ol_pattern.search(html)
        if not ol_match:
            continue
        ol_content = ol_match.group(2)
        li_pattern = re.compile(r'<li>(.*?)</li>', re.DOTALL)
        refs = li_pattern.findall(ol_content)
        if not refs:
            continue
        # Build reference index: extract author last name + year from each ref
        ref_entries = []
        for i, ref_text in enumerate(refs):
            plain = re.sub(r'<[^>]+>', '', ref_text)
            m = re.match(r'([A-Z][a-zA-Z\u00e9\u00e8\u00ea\u00eb\u00e0\u00e2\u00e4\u00fc\u00f6\u00ef\u00ee\u00f4\u0171\-]+)\b.*?\((\d{4})\)', plain)
            if m:
                ref_entries.append((m.group(1), m.group(2), i + 1))
        if not ref_entries:
            continue
        # Add id anchors to <li> elements inside <ol> only
        li_count = [0]
        def add_ref_id(m):
            li_count[0] += 1
            return f'<li id="prog-{slug}-ref-{li_count[0]}">{m.group(1)}</li>'
        new_ol = '<ol>' + li_pattern.sub(add_ref_id, ol_content) + '</ol>'
        html = html[:ol_match.start()] + new_ol + html[ol_match.end():]
        # Link in-text citations (before the <ol>) to bibliography anchors
        ol_start = html.find('<ol>')
        body_before = html[:ol_start] if ol_start > 0 else html
        body_after = html[ol_start:] if ol_start > 0 else ''
        for author, year, ref_num in ref_entries:
            anchor = f'#prog-{slug}-ref-{ref_num}'
            # Parenthetical: (Author et al., Year)
            paren_pat = re.compile(
                r'\((' + re.escape(author) + r'[^)]*?,\s*' + re.escape(year) + r')\)'
            )
            body_before = paren_pat.sub(
                lambda m, a=anchor: f'(<a href="{a}">{m.group(1)}</a>)', body_before
            )
            # Narrative: Author et al. (Year) or Author (Year)
            narr_pat = re.compile(
                r'(' + re.escape(author) + r'(?:\s+et\s+al\.?)?)\s+\((' + re.escape(year) + r')\)'
            )
            body_before = narr_pat.sub(
                lambda m, a=anchor: f'<a href="{a}">{m.group(1)} ({m.group(2)})</a>', body_before
            )
        prog["body_html"] = body_before + body_after

def link_people_in_programs(programs, people):
    """Post-process program body_html to link person last names to their person pages."""
    # Build last-name → slug mapping (skip short names and duplicates)
    name_counts = defaultdict(list)
    for p in people:
        parts = p["name"].strip().split()
        if not parts: continue
        last = parts[-1]
        name_counts[last].append(p["slug"])
    ln_to_slug = {}
    for last, slugs in name_counts.items():
        if len(last) < 4: continue  # skip short names (Li, Ott, Poo, etc.)
        if len(slugs) == 1:
            ln_to_slug[last] = slugs[0]
    if not ln_to_slug: return
    total_links = 0
    for prog in programs:
        html = prog["body_html"]
        # Split at <ol> to separate narrative from bibliography
        ol_start = html.find('<ol>')
        if ol_start > 0:
            narrative = html[:ol_start]
            biblio = html[ol_start:]
        else:
            narrative = html
            biblio = ''
        # --- Link in narrative text ---
        for last_name, slug in sorted(ln_to_slug.items(), key=lambda x: -len(x[0])):
            href = f'people/{slug}.html'
            # Skip if already linked in this narrative
            if href in narrative: continue
            # Match whole-word last name, not inside HTML tags or existing <a> links
            # Strategy: split on HTML tags, process only text segments
            pat = re.compile(r'(?<![a-zA-Z\u00C0-\u024F])(' + re.escape(last_name) + r')(?![a-zA-Z\u00C0-\u024F])')
            pieces = re.split(r'(<[^>]+>)', narrative)
            in_a = 0
            in_heading = 0
            linked = False
            for i, piece in enumerate(pieces):
                if linked: break
                if piece.startswith('<'):
                    lower = piece.lower()
                    if re.match(r'<a[\s>]', lower): in_a += 1
                    elif lower.startswith('</a'): in_a = max(0, in_a - 1)
                    if re.match(r'<h[1-3][\s>]', lower): in_heading += 1
                    elif re.match(r'</h[1-3]', lower): in_heading = max(0, in_heading - 1)
                    continue
                if in_a or in_heading: continue
                m = pat.search(piece)
                if m:
                    replacement = f'<a href="{href}" class="person-link">{m.group(1)}</a>'
                    pieces[i] = piece[:m.start()] + replacement + piece[m.end():]
                    linked = True
                    total_links += 1
            narrative = ''.join(pieces)
        # --- Link in bibliography (<ol>) entries ---
        if biblio:
            # Process each <li> inside <ol>
            def link_bib_authors(li_match):
                nonlocal total_links
                li_content = li_match.group(1)
                # Find "LastName AB" or "LastName A" patterns (name + initials)
                for last_name, slug in sorted(ln_to_slug.items(), key=lambda x: -len(x[0])):
                    href = f'people/{slug}.html'
                    if href in li_content: continue
                    # Match LastName followed by space + 1-3 uppercase letters (initials)
                    bib_pat = re.compile(
                        r'(?<![a-zA-Z\u00C0-\u024F])(' + re.escape(last_name) + r'\s+[A-Z]{1,3})(?![a-zA-Z])'
                    )
                    m = bib_pat.search(li_content)
                    if m:
                        # Verify not inside an <a> tag
                        before = li_content[:m.start()]
                        if '<a ' in before and '</a>' not in before[before.rfind('<a '):]:
                            continue
                        replacement = f'<a href="{href}" class="person-link">{m.group(1)}</a>'
                        li_content = li_content[:m.start()] + replacement + li_content[m.end():]
                        total_links += 1
                return f'<li{li_match.group(0)[len("<li"):li_match.group(0).find(">")+1-len("<li")]}{li_content}</li>'
            # Handle <li> with possible id attribute
            biblio = re.sub(r'<li[^>]*>(.*?)</li>', lambda m: '<li' + m.group(0)[len('<li'):m.group(0).find('>')] + '>' + (lambda c: c)(m.group(1)) + '</li>', biblio, flags=re.DOTALL)
            # Simpler approach: process each <li>...</li>
            def process_li(m):
                nonlocal total_links
                full_tag_open = m.group(0)[:m.group(0).find('>')+1]
                content = m.group(1)
                for last_name, slug in sorted(ln_to_slug.items(), key=lambda x: -len(x[0])):
                    href = f'people/{slug}.html'
                    if href in content: continue
                    bib_pat = re.compile(
                        r'(?<![a-zA-Z\u00C0-\u024F])(' + re.escape(last_name) + r'\s+[A-Z]{1,3})(?![a-zA-Z])'
                    )
                    bib_m = bib_pat.search(content)
                    if bib_m:
                        before = content[:bib_m.start()]
                        if '<a ' in before and '</a>' not in before[before.rfind('<a '):]:
                            continue
                        replacement = f'<a href="{href}" class="person-link">{bib_m.group(1)}</a>'
                        content = content[:bib_m.start()] + replacement + content[bib_m.end():]
                        total_links += 1
                return full_tag_open + content + '</li>'
            biblio = re.sub(r'<li[^>]*>(.*?)</li>', process_li, biblio, flags=re.DOTALL)
        prog["body_html"] = narrative + biblio
    print(f"  Linked {total_links} person names in programs")

# ── Person page generation ──

PERSON_PAGE_CSS = r'''
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg: #fafaf8; --bg-card: #ffffff; --text: #1a1a1a; --muted: #6b7280;
  --border: #e5e7eb; --hover: #f3f4f6; --accent: #0d9488; --highlight: #f0fdfa;
}
[data-theme="dark"] {
  --bg: #111111; --bg-card: #1a1a1a; --text: #e5e5e5; --muted: #9ca3af;
  --border: #2d2d2d; --hover: #222222; --accent: #2dd4bf; --highlight: #0d2926;
}
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--bg); color: var(--text); line-height: 1.6;
  transition: background 0.2s, color 0.2s;
}
.page { max-width: 700px; margin: 0 auto; padding: 2rem 1.5rem 3rem; }
.back { font-size: 0.85rem; color: var(--accent); text-decoration: none; display: inline-block; margin-bottom: 1.5rem; }
.back:hover { text-decoration: underline; }
h1 { font-size: 1.5rem; font-weight: 600; letter-spacing: -0.02em; margin-bottom: 0.2rem; }
h2 { font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); margin: 1.8rem 0 0.5rem; }
.position { color: var(--muted); font-size: 0.92rem; margin-bottom: 1rem; }
.position a { color: var(--accent); text-decoration: none; }
.position a:hover { text-decoration: underline; }
.lab-role { font-size: 0.9rem; margin-bottom: 1.5rem; padding-bottom: 1rem; border-bottom: 1px solid var(--border); }
.profile-links { list-style: none; padding: 0; margin: 0; text-align: center; }
.profile-links li { font-size: 0.88rem; margin-bottom: 0.3rem; }
.profile-links li a { color: var(--accent); text-decoration: none; }
.profile-links li a:hover { text-decoration: underline; }
.bio { font-size: 0.92rem; line-height: 1.7; color: var(--text); }
.bio p { margin-bottom: 0.8rem; }
.bio h1, .bio h2, .bio h3 { font-size: 0.95rem; font-weight: 600; text-transform: none; letter-spacing: 0; color: var(--text); margin: 1rem 0 0.4rem; }
.cv-meta { font-size: 0.8rem; color: var(--muted); margin-bottom: 0.8rem; }
.pub-list { list-style: none; padding: 0; }
.pub-list li { font-size: 0.88rem; color: var(--text); margin-bottom: 0.6rem; line-height: 1.55; }
.pub-list li.lab-paper { background: var(--highlight); padding: 0.35rem 0.5rem; border-radius: 4px; margin-left: -0.5rem; margin-right: -0.5rem; }
.pub-list li .journal, .pub-list li .venue { color: var(--muted); }
.pub-list li .cite-count { color: var(--muted); font-size: 0.82rem; }
.pub-list li a { color: var(--accent); text-decoration: none; }
.pub-list li a:hover { text-decoration: underline; }
.project-list { list-style: none; padding: 0; display: flex; flex-wrap: wrap; gap: 0.4rem; }
.project-list li a {
  display: inline-block; font-size: 0.82rem; padding: 0.25rem 0.65rem;
  border-radius: 999px; border: 1px solid var(--border); color: var(--accent);
  text-decoration: none; transition: background 0.15s;
}
.project-list li a:hover { background: var(--hover); }
#theme-toggle {
  position: fixed; top: 1rem; right: 1rem;
  background: none; border: 1px solid var(--border); border-radius: 6px;
  padding: 0.4rem 0.6rem; cursor: pointer; color: var(--text); font-size: 0.85rem;
}
#theme-toggle:hover { background: var(--hover); }
'''

PERSON_PAGE_JS = r'''
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
});
'''

def _normalize_doi(doi):
    if not doi: return ""
    doi = doi.lower().strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi

def _normalize_title(title):
    if not title: return ""
    return re.sub(r'[^a-z0-9\s]', '', title.lower().strip())

def _titles_match(t1, t2):
    w1 = set(_normalize_title(t1).split())
    w2 = set(_normalize_title(t2).split())
    if not w1 or not w2: return False
    smaller, larger = (w1, w2) if len(w1) <= len(w2) else (w2, w1)
    overlap = len(smaller & larger) / len(smaller)
    return overlap > 0.8

def _format_s2_authors(authors, max_show=10, truncate_to=5):
    if not authors: return ""
    def _abbrev(name):
        parts = name.strip().split()
        if len(parts) <= 1: return name.strip()
        last = parts[-1]
        initials = "".join(p[0].upper() for p in parts[:-1] if p)
        return f"{last} {initials}"
    if len(authors) > max_show:
        return ", ".join(_abbrev(a) for a in authors[:truncate_to]) + ", ... et al."
    return ", ".join(_abbrev(a) for a in authors)

def _compute_h_index(papers):
    citations = sorted([p.get("citation_count", 0) for p in papers], reverse=True)
    h = 0
    for i, c in enumerate(citations):
        if c >= i + 1:
            h = i + 1
        else:
            break
    return h

def _build_fallback_bio(person):
    name = person.get("name", "")
    role = person.get("role", "")
    start = person.get("start_date") or ""
    start_y = str(start)[:4] if start else ""
    is_active = person.get("status") == "active"
    if person.get("status") == "collaborator":
        cy = person.get("collab_years", [None, None])
        if cy[0]:
            end_y = "present" if is_active else (str(cy[1]) if cy[1] else "present")
            span = f"from {cy[0]} to {end_y}"
        else:
            span = ""
        role_desc = "a collaborator of"
    else:
        end = person.get("end_date") or ""
        end_y = str(end)[:4] if end and not is_active else ("present" if is_active else "")
        span = f"from {start_y} to {end_y}" if start_y and end_y else (f"since {start_y}" if start_y else "")
        article = "an" if role and role[0].lower() in "aeiou" else "a"
        role_desc = f"{article} {role} in" if role else "a member of"
    parts = []
    if span:
        parts.append(f"{name} {'is' if is_active else 'was'} {role_desc} the Mainen Lab {span}.")
    else:
        parts.append(f"{name} {'is' if is_active else 'was'} {role_desc} the Mainen Lab.")
    projects = person.get("projects", [])
    if projects:
        proj_names = ", ".join(p["name"] for p in projects[:4])
        if len(projects) > 4:
            proj_names += f", and {len(projects) - 4} other project{'s' if len(projects) - 4 > 1 else ''}"
        parts.append(f"{'Their' if is_active else 'Their'} research {'involves' if is_active else 'involved'} {proj_names}.")
    papers = person.get("papers", [])
    if papers:
        n = len(papers)
        first = sorted(papers, key=lambda p: p.get("year", 9999))[0]
        title = first.get("title", "")
        year = first.get("year", "")
        if n == 1:
            parts.append(f"Their work with the lab includes the publication \"{title}\" ({year}).")
        else:
            parts.append(f"Their work with the lab includes {n} publications, including \"{title}\" ({year}).")
    cur = person.get("current_position")
    if cur and not is_active:
        parts.append(f"They are currently {cur}.")
    return " ".join(parts) if len(parts) > 1 or (parts and "member of" not in parts[0] and role) else ""

def generate_person_pages(people, site_data, s2_pubs=None, bios=None):
    s2_pubs = s2_pubs or {}
    bios = bios or {}
    people_dir = WEB / "people"
    people_dir.mkdir(exist_ok=True)
    pub_by_slug = {p["slug"]: p for p in site_data["publications"]}
    # Build set of lab DOIs and normalized titles for highlighting
    lab_dois = {_normalize_doi(p["doi"]) for p in site_data["publications"] if p.get("doi")}
    lab_titles = [p["title"] for p in site_data["publications"] if p.get("title")]
    count = 0
    for person in people:
        has_pubs = bool(person.get("papers"))
        has_s2 = person["slug"] in s2_pubs
        has_bio = person["slug"] in bios
        if not has_pubs and not has_s2 and not has_bio and person.get("status") != "active":
            continue
        slug = person["slug"]
        name = person["name"]
        # Position
        pos_html = ""
        if person.get("current_position"):
            pos_text = esc(person["current_position"])
            if person.get("institution_url"):
                pos_html = f'<a href="{person["institution_url"]}" target="_blank" rel="noopener">{pos_text}</a>'
            else:
                pos_html = pos_text
        # Lab role line
        role = person.get("role", "")
        start = person.get("start_date") or "?"
        if person.get("status") == "collaborator":
            cy = person.get("collab_years", [None, None])
            if cy[0]:
                end = "present" if not person.get("end_date") else (str(cy[1]) if cy[1] else "present")
                role_line = f"Collaborator, {cy[0]}\u2013{end}"
            else:
                role_line = "Collaborator"
        else:
            end = "present" if person.get("status") == "active" else (person.get("end_date") or "?")
            role_line = f"{role}, {start}\u2013{end}"

        sections = []

        # ── Profile links ──
        links = []
        if person.get("institution_url"):
            links.append(f'<li><a href="{person["institution_url"]}" target="_blank" rel="noopener">Institutional page</a></li>')
        if person.get("orcid"):
            links.append(f'<li><a href="https://orcid.org/{person["orcid"]}" target="_blank" rel="noopener">ORCID</a></li>')
        if person.get("s2_id"):
            links.append(f'<li><a href="https://www.semanticscholar.org/author/{person["s2_id"]}" target="_blank" rel="noopener">Semantic Scholar</a></li>')
        if person.get("google_scholar"):
            links.append(f'<li><a href="{esc(person["google_scholar"])}" target="_blank" rel="noopener">Google Scholar</a></li>')
        if links:
            sections.append('<h2>Profile</h2>\n<ul class="profile-links">' + "\n".join(links) + '</ul>')

        # ── About (bio.md or fallback) ──
        bio_html = bios.get(slug, "")
        is_stub = bio_html and ("No Semantic Scholar profile matched" in bio_html or "Profile limited to roster data" in bio_html)
        if has_bio and not is_stub:
            sections.append(f'<h2>About</h2>\n<div class="bio">{bio_html}</div>')
        else:
            fallback = _build_fallback_bio(person)
            if fallback:
                sections.append(f'<h2>About</h2>\n<div class="bio"><p>{esc(fallback)}</p></div>')

        # ── Publications ──
        if slug == "mainen-zf":
            # For Mainen: show only belongings-matched (curated lab) publications, skip S2
            lab_papers = person.get("papers", [])
            if lab_papers:
                sorted_lab = sorted(lab_papers, key=lambda p: -(p.get("year") or 0))
                items = []
                for pub in sorted_lab:
                    title_text = esc(pub.get("title", ""))
                    doi = pub.get("doi", "")
                    year = pub.get("year") or ""
                    journal = esc(pub.get("journal", ""))
                    if doi:
                        title_html = f'<a href="https://doi.org/{esc(doi)}" target="_blank">{title_text}</a>'
                    else:
                        title_html = title_text
                    venue_part = f' <span class="venue">{journal}</span>,' if journal else ''
                    items.append(f'<li>{title_html}.{venue_part} {year}.</li>')
                meta_line = f'{len(sorted_lab)} lab publications'
                sections.append(f'<h2>Selected Publications</h2>\n<div class="cv-meta">{esc(meta_line)}</div>\n<ul class="pub-list">' + "\n".join(items) + '</ul>')
        elif has_s2:
            s2_papers = s2_pubs[slug]
            h_index = _compute_h_index(s2_papers)
            s2_cache = json.loads(S2_CACHE_PATH.read_text()) if S2_CACHE_PATH.exists() else {}
            s2_id = person.get("s2_id", "")
            retrieved = s2_cache.get(s2_id, {}).get("retrieved", "unknown")
            lab_count = sum(1 for p in s2_papers if _normalize_doi(p.get("doi", "")) in lab_dois or any(_titles_match(p.get("title", ""), lt) for lt in lab_titles) or any(a.lower() == "zachary mainen" or a.lower() == "zach mainen" or "mainen" in a.lower().split() for a in p.get("authors", [])))
            meta_line = f'h-index: {h_index} | Total papers: {len(s2_papers)} | Lab papers: {lab_count} | Retrieved: {retrieved}'
            sorted_s2 = sorted(s2_papers, key=lambda p: (-(p.get("year") or 0), -(p.get("citation_count") or 0)))
            items = []
            for pub in sorted_s2:
                title_text = esc(pub.get("title", ""))
                doi = pub.get("doi", "")
                year = pub.get("year") or ""
                venue = esc(pub.get("venue", ""))
                cites = pub.get("citation_count", 0)
                is_lab = False
                ndoi = _normalize_doi(doi)
                if ndoi and ndoi in lab_dois:
                    is_lab = True
                elif any(_titles_match(pub.get("title", ""), lt) for lt in lab_titles):
                    is_lab = True
                elif any(a.lower() == "zachary mainen" or a.lower() == "zach mainen" or "mainen" in a.lower().split() for a in pub.get("authors", [])):
                    is_lab = True
                li_class = ' class="lab-paper"' if is_lab else ''
                authors_str = _format_s2_authors(pub.get("authors", []))
                authors_html = esc(authors_str) + ". " if authors_str else ""
                if doi:
                    title_html = f'<a href="https://doi.org/{esc(doi)}" target="_blank">{title_text}</a>'
                else:
                    title_html = title_text
                venue_part = f' <span class="venue">{venue}</span>,' if venue else ''
                cite_part = f' <span class="cite-count">Citations: {cites}</span>' if cites else ''
                lab_badge = ' <span style="display:inline-block;background:#0d9488;color:white;font-size:0.7em;padding:0.1em 0.45em;border-radius:3px;margin-left:0.4em;vertical-align:middle;font-weight:600;">lab</span>' if is_lab else ''
                items.append(f'<li{li_class}>{authors_html}{title_html}{lab_badge}.{venue_part} {year}.{cite_part}</li>')
            sections.append(f'<h2>Complete Publications</h2>\n<div class="cv-meta">{esc(meta_line)}</div>\n<ul class="pub-list">' + "\n".join(items) + '</ul>')

        # ── At the Mainen Lab ──
        lab_parts = [f'<div class="lab-role">{esc(role_line)}</div>']
        projects = person.get("projects", [])
        if projects:
            items = [f'<li><a href="../index.html#project-{proj["slug"]}">{esc(proj["name"])}</a></li>' for proj in projects]
            lab_parts.append('<h2>Projects</h2>\n<ul class="project-list">' + "\n".join(items) + '</ul>')
        if projects:
            sections.append('<h2>At the Mainen Lab</h2>\n' + "\n".join(lab_parts))

        body_html = "\n".join(sections)
        person_path = f"home/zach/projects/mainen-lab/people/{slug}"
        edit_url = f"http://127.0.0.1:18832/situation?path={person_path}/index.md" if read_situation_frontmatter(LAB / "people" / slug) else "http://127.0.0.1:18832/situation?path=home/zach/projects/mainen-lab/index.md"
        page_html = f'''<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(name)} &mdash; Mainen Lab</title>
<link rel="icon" type="image/svg+xml" href="../favicon.svg">
<style>{PERSON_PAGE_CSS}</style>
</head>
<body>
<div class="page">
<a href="../index.html" class="back">&larr; Mainen Lab</a>
<button id="theme-toggle" aria-label="Toggle dark mode">&#9790;</button>
<h1>{esc(name)} <a href="{edit_url}" style="font-size:0.5em;color:#999;text-decoration:none;vertical-align:middle" title="Edit in situation editor">&#9998;</a></h1>
{f'<div class="position">{pos_html}</div>' if pos_html else ""}
{body_html}
</div>
<script>{PERSON_PAGE_JS}</script>
</body>
</html>'''
        (people_dir / f"{slug}.html").write_text(page_html)
        count += 1
    print(f"  {count} person pages generated in {people_dir}")

# ── Build ──

def build(regenerate=False):
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

    print("Enriching people with publications and projects...")
    belonging_matches = match_pubs_to_people_via_belongings(pubs)
    pubs_without_belongings = [p for p in pubs if not p.get("belongings")]
    fallback_matches = match_pubs_to_people(pubs_without_belongings, people)
    pub_matches = defaultdict(list, fallback_matches)
    for person_slug, pub_slugs in belonging_matches.items():
        pub_matches[person_slug].extend(s for s in pub_slugs if s not in pub_matches[person_slug])
    pub_matches = dict(pub_matches)
    pub_by_slug = {p["slug"]: p for p in pubs}
    proj_by_slug = {p["slug"]: p for p in projects}
    for person in people:
        ps = person["slug"]
        matched = pub_matches.get(ps, [])
        person["papers"] = sorted(
            [{"slug": s, "title": pub_by_slug[s]["title"], "year": pub_by_slug[s]["year"],
              "doi": pub_by_slug[s]["doi"], "journal": pub_by_slug[s]["journal"]}
             for s in matched if s in pub_by_slug],
            key=lambda x: x["year"]
        )
        person["projects"] = [
            {"slug": p["slug"], "name": p["name"]}
            for p in projects if ps in p.get("people", [])
        ]
        if matched:
            first_yr, last_yr = compute_collab_years(person, matched, pubs)
            person["collab_years"] = [first_yr, last_yr]
        else:
            person["collab_years"] = [None, None]
        person["institution"] = extract_institution(person.get("current_position", ""))
        if not person.get("institution_url"):
            person["institution_url"] = ""
    matched_count = sum(1 for p in people if pub_matches.get(p["slug"]))
    print(f"  {matched_count} people matched to publications")

    print("Loading programs...")
    programs = load_programs()
    link_citations_in_programs(programs)
    link_people_in_programs(programs, people)
    print(f"  {len(programs)} programs")

    print("Generating narratives...")
    narratives = generate_narratives(taxonomy, projects, pubs, people, theme_children, regenerate=regenerate)
    overrides = load_overrides()
    generated_count = len(narratives)
    for slug, body in overrides.items():
        narratives[slug] = body
    print(f"  {len(narratives)} narratives ({generated_count - len(overrides)} generated, {len(overrides)} hand-written overrides)")

    # Fields allowed in public JSON (no internal IDs, paths, or type)
    # Convert markdown links in text fields that render on the site
    for p in projects:
        if p.get("description"):
            p["description"] = md_links_to_html(esc(p["description"]))
    for slug in list(narratives):
        narratives[slug] = md_links_to_html(esc(narratives[slug]))

    site_data = {
        "taxonomy": taxonomy,
        "projects": [{
            "slug": p["slug"], "name": p["name"], "status": p["status"],
            "description": p["description"],
            "start_year": p["start_year"], "end_year": p["end_year"],
            "themes": p["themes"], "methods": p["methods"], "scale": p["scale"],
            "organisms": p["organisms"], "settings": p["settings"],
            "participants": p["people"], "participant_roles": p.get("people_roles", {}),
            "papers": p["papers"], "paper_count": p["paper_count"],
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
            "papers": p.get("papers", []), "projects": p.get("projects", []),
            "collab_years": p.get("collab_years", [None, None]),
            "institution": p.get("institution", ""),
            "institution_url": p.get("institution_url"),
            "orcid": p.get("orcid", ""),
            "s2_id": p.get("s2_id", ""),
            "google_scholar": p.get("google_scholar", ""),
        } for p in people],
        "narratives": narratives,
        "programs": [{
            "slug": p["slug"], "title": p["title"], "span": p["span"],
            "color": p["color"], "status": p["status"], "themes": p["themes"],
            "projects": p["projects"], "repos": p["repos"], "body_html": p["body_html"],
        } for p in programs],
    }

    print("Generating lab intro...")
    lab_intro = generate_lab_intro(people, projects, taxonomy)
    print(f"  {lab_intro}")

    json_blob = json.dumps(site_data, ensure_ascii=False, separators=(",", ":"))
    print(f"  JSON blob: {len(json_blob):,} bytes")

    html = HTML_TEMPLATE.replace("__SITE_DATA_PLACEHOLDER__", json_blob)
    html = html.replace("__LAB_INTRO_PLACEHOLDER__", md_links_to_html(esc(lab_intro)))
    out_path = WEB / "index.html"
    out_path.write_text(html)
    print(f"  {len(html):,} bytes written to {out_path}")

    print("Loading bios...")
    bios = load_bios(LAB / "people")
    # Merge cached AI-generated bios (override bio.md content)
    bio_cache_path = WEB / ".bio-cache.json"
    if bio_cache_path.exists():
        ai_bios = json.loads(bio_cache_path.read_text())
        converter = md_lib.Markdown(extensions=["extra"])
        for slug, text in ai_bios.items():
            converter.reset()
            bios[slug] = converter.convert(text)
        print(f"  {len(bios)} bios loaded ({len(ai_bios)} from AI cache)")
    else:
        print(f"  {len(bios)} bios loaded (no AI cache; run scripts/generate_bios.py)")

    print("Fetching Semantic Scholar publications...")
    s2_pubs = fetch_s2_publications(people)

    print("Generating person pages...")
    generate_person_pages(people, site_data, s2_pubs=s2_pubs, bios=bios)

    print("Checking migration regressions...")
    migration_warnings(people, pubs, projects)

    print(f"\nDone.")

DEPLOY_REPO = "mainenlab/mainenlab.github.io"
DEPLOY_CACHE = Path("/tmp/mainenlab.github.io")
DEPLOY_FILES = ["index.html", "favicon.svg", "CNAME"]

def deploy():
    if DEPLOY_CACHE.exists() and (DEPLOY_CACHE / ".git").exists():
        print("Pulling latest deployment repo...")
        subprocess.run(["git", "pull", "--ff-only"], cwd=DEPLOY_CACHE, check=True)
    else:
        print("Cloning deployment repo...")
        if DEPLOY_CACHE.exists():
            shutil.rmtree(DEPLOY_CACHE)
        subprocess.run(["gh", "repo", "clone", DEPLOY_REPO, str(DEPLOY_CACHE)], check=True)

    for name in DEPLOY_FILES:
        src = WEB / name
        if src.exists():
            shutil.copy2(src, DEPLOY_CACHE / name)
        else:
            print(f"  warning: {name} not found in {WEB}, skipping")

    # Copy people/ directory
    people_src = WEB / "people"
    people_dst = DEPLOY_CACHE / "people"
    if people_src.exists():
        if people_dst.exists():
            shutil.rmtree(people_dst)
        shutil.copytree(people_src, people_dst)
        print(f"  Copied {len(list(people_src.glob('*.html')))} person pages")

    msg = f"build: deploy {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    subprocess.run(["git", "add", "-A"], cwd=DEPLOY_CACHE, check=True)
    result = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=DEPLOY_CACHE)
    if result.returncode == 0:
        print("No changes to deploy.")
        return
    subprocess.run(["git", "commit", "-m", msg], cwd=DEPLOY_CACHE, check=True)
    subprocess.run(["git", "push"], cwd=DEPLOY_CACHE, check=True)
    print(f"Deployed: {msg}")

def migration_warnings(people, pubs, projects):
    """Lightweight regression checks — runs every build, prints to stderr."""
    warn = lambda msg: print(f"⚠️ MIGRATION: {msg}", file=sys.stderr)
    warnings = 0

    # 1. Project regression: project.yaml has people: but index.md lacks belongings
    for f in (LAB / "projects").glob("*/project.yaml"):
        d = load_yaml(f.read_text(errors="replace")) or {}
        if d.get("people") or d.get("participants"):
            if not read_situation_frontmatter(f.parent):
                warn(f"project {f.parent.name}: has people in project.yaml but no belongings in index.md")
                warnings += 1

    # 2. Publication regression: paper.md has authors with lab member names but no belongings
    people_last = {}
    for p in people:
        parts = p["name"].strip().split()
        if parts:
            people_last[parts[-1].lower()] = p["slug"]
    for f in (LAB / "publications").glob("*/paper.md"):
        try:
            meta, _ = parse_frontmatter(f.read_text(errors="replace"))
        except (FileNotFoundError, OSError):
            continue
        if meta.get("belongings"):
            continue
        authors = meta.get("authors", [])
        if isinstance(authors, str):
            authors = [authors]
        for author in authors:
            for ln in people_last:
                if re.search(r'\b' + re.escape(ln) + r'\b', author.lower()):
                    warn(f"publication {f.parent.name}: author '{author}' matches lab member {people_last[ln]} but no belongings")
                    warnings += 1
                    break

    # 3. Person regression: person.yaml role/start_date disagrees with lab situation frontmatter
    sit = read_situation_frontmatter(LAB)
    sit_multi = {}
    for b in sit:
        sit_multi.setdefault(b["entity"], []).append(b)
    for f in (LAB / "people").glob("*/person.yaml"):
        d = load_yaml(f.read_text(errors="replace")) or {}
        slug = f.parent.name
        stints = sit_multi.get(slug)
        if not stints:
            continue
        sb = max(stints, key=lambda s: int(str(s.get("since") or 0)[:4]))
        yaml_role = (d.get("role") or "").lower().strip()
        sit_quality = sb.get("quality", "")
        if yaml_role and sit_quality:
            norm_sit = quality_to_role(sit_quality).lower()
            norm_yaml = normalize_role(yaml_role).lower()
            if norm_yaml != norm_sit:
                warn(f"person {slug}: person.yaml role '{yaml_role}' != situation quality '{sit_quality}'")
                warnings += 1
        all_starts = [int(str(s["since"])[:4]) for s in stints if s.get("since")]
        yaml_start = str(d.get("start_date", ""))[:4]
        sit_start = str(min(all_starts)) if all_starts else ""
        if yaml_start and sit_start and yaml_start != sit_start:
            warn(f"person {slug}: person.yaml start_date '{yaml_start}' != situation since '{sit_start}'")
            warnings += 1

    # 4. Phase 5 complete: ROLE_MAP, INSTITUTION_URLS, ONGOING_COLLABORATORS deleted.
    #    institutional_url now lives in person.yaml; ongoing status derived from situation belongings.

    if warnings:
        print(f"  {warnings} migration warnings (see stderr)", file=sys.stderr)

def migration_report():
    err = lambda *a, **kw: print(*a, file=sys.stderr, **kw)
    err("\n=== Situation Frontmatter Migration Report ===\n")

    proj_dirs = sorted((LAB / "projects").glob("*/project.yaml"))
    proj_slugs = [f.parent.name for f in proj_dirs]
    with_fm = [s for s in proj_slugs if read_situation_frontmatter(LAB / "projects" / s)]
    without_fm = [s for s in proj_slugs if s not in set(with_fm)]
    err(f"Projects: {len(with_fm)}/{len(proj_slugs)} have situation frontmatter")
    if without_fm:
        for s in without_fm:
            err(f"  MISSING  {s}")

    pub_papers = sorted((LAB / "publications").glob("*/paper.md"))
    pub_with, pub_without = [], []
    for p in pub_papers:
        try:
            meta, _ = parse_frontmatter(p.read_text(errors="replace"))
        except (FileNotFoundError, OSError):
            meta = {}
        (pub_with if meta.get("belongings") else pub_without).append(p.parent.name)
    err(f"\nPublications: {len(pub_with)}/{len(pub_papers)} have belongings in paper.md")
    if pub_without:
        for s in pub_without[:10]:
            err(f"  MISSING  {s}")
        if len(pub_without) > 10:
            err(f"  ... and {len(pub_without) - 10} more")

    lab_belongings = read_situation_frontmatter(LAB)
    lab_entities = {b["entity"] for b in lab_belongings}
    people = load_people()
    declared = [p for p in people if p["slug"] in lab_entities or any(
        p["slug"] == e.replace("-", "") for e in lab_entities)]
    err(f"\nPeople: {len(lab_entities)} declared in lab situation frontmatter / {len(people)} in person.yaml files")

    web_programs = sorted((WEB / "research" / "programs").glob("*.md")) if (WEB / "research" / "programs").exists() else []
    web_slugs = {f.stem for f in web_programs}
    fs_slugs = {f.parent.name for f in proj_dirs}
    err(f"\nPrograms: {len(web_slugs)} in web/mainenlab/research/programs, {len(fs_slugs)} project dirs in projects/mainen-lab/")
    err("")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build mainenlab.org static site")
    parser.add_argument("--regenerate", action="store_true",
                        help="Regenerate all theme narratives (and project descriptions) via Claude API")
    parser.add_argument("--deploy", action="store_true",
                        help="Push built site to mainenlab.github.io after building")
    parser.add_argument("--generate-bios", action="store_true",
                        help="Generate AI bios before building (runs scripts/generate_bios.py)")
    parser.add_argument("--migration-report", action="store_true",
                        help="Print situation frontmatter coverage report to stderr")
    args = parser.parse_args()
    if args.generate_bios:
        subprocess.run([sys.executable, str(WEB / "scripts" / "generate_bios.py")], check=True)
    build(regenerate=args.regenerate)
    if args.migration_report:
        migration_report()
    if args.deploy:
        deploy()
