#!/usr/bin/env python3
"""Mainen Lab Projects Editor — internal tool on 127.0.0.1:18831"""

import os, re, datetime, json, subprocess
from pathlib import Path
from flask import Flask, request, redirect, url_for, flash, jsonify

try:
    from ruamel.yaml import YAML
    _ryaml = YAML()
    _ryaml.preserve_quotes = True
    _ryaml.width = 200
    def load_yaml(p):
        with open(p) as f: return dict(_ryaml.load(f) or {})
    def dump_yaml(data, p):
        with open(p, 'w') as f: _ryaml.dump(data, f)
    YAML_ENGINE = 'ruamel'
except ImportError:
    import yaml
    def load_yaml(p):
        with open(p) as f: return yaml.safe_load(f) or {}
    def dump_yaml(data, p):
        with open(p, 'w') as f: yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    YAML_ENGINE = 'pyyaml'

app = Flask(__name__)
app.secret_key = 'mainenlab-projects-internal'

BASE = Path(__file__).resolve().parent.parent.parent.parent.parent.parent  # haak root
PEOPLE_DIR = BASE / 'workspaces/zach/projects/mainen-lab/people'
PROJECTS_DIR = BASE / 'workspaces/zach/projects/mainen-lab/projects'
PUBS_DIR = BASE / 'workspaces/zach/projects/mainen-lab/publications'
TAXONOMY_PATH = BASE / 'workspaces/zach/projects/mainen-lab/taxonomy.yaml'

PERSONNEL_URL = 'http://127.0.0.1:18830'

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_taxonomy():
    if TAXONOMY_PATH.exists():
        return load_yaml(str(TAXONOMY_PATH))
    return {}

def _flatten_tags(items):
    """Flatten a taxonomy axis (which may have children) into a flat list of slugs."""
    out = []
    for item in (items or []):
        out.append(item.get('slug', ''))
        for child in item.get('children', []):
            out.append(child.get('slug', ''))
    return [s for s in out if s]

def _tag_label(items, slug):
    """Get display label for a taxonomy slug."""
    for item in (items or []):
        if item.get('slug') == slug:
            return item.get('label', slug)
        for child in item.get('children', []):
            if child.get('slug') == slug:
                return child.get('label', slug)
    return slug

def load_people():
    people = {}
    for d in sorted(PEOPLE_DIR.iterdir()):
        yf = d / 'person.yaml'
        if not yf.exists(): continue
        try:
            data = load_yaml(str(yf))
            data['_slug'] = d.name
            people[d.name] = data
        except Exception:
            pass
    return people

def load_projects():
    projects = {}
    for d in sorted(PROJECTS_DIR.iterdir()):
        yf = d / 'project.yaml'
        if not yf.exists(): continue
        try:
            data = load_yaml(str(yf))
            data['_slug'] = d.name
            projects[d.name] = data
        except Exception:
            pass
    return projects

def load_publications():
    pubs = []
    for d in sorted(PUBS_DIR.iterdir()):
        pf = d / 'paper.md'
        if not pf.exists(): continue
        try:
            text = pf.read_text()
            m = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
            if not m: continue
            import yaml as _y
            meta = _y.safe_load(m.group(1)) or {}
            meta['_slug'] = d.name
            pubs.append(meta)
        except Exception:
            pass
    return pubs

def _get_participants(proj):
    """Get participant list from project, handling both 'people' and 'participants' keys."""
    return proj.get('participants') or proj.get('people') or []

def _get_papers(proj):
    raw = proj.get('papers') or []
    out = []
    for p in raw:
        if isinstance(p, str):
            out.append(p)
        elif isinstance(p, dict):
            out.append(p.get('paper_id', p.get('id', str(p))))
        else:
            out.append(str(p))
    return out

def _project_start_year(proj):
    sd = str(proj.get('start_date', ''))
    if sd: return sd[:4]
    return ''

def _project_end_year(proj):
    ed = str(proj.get('end_date', ''))
    if ed: return ed[:4]
    return ''

def _sorted_project_slugs(projects):
    """Active first, then by start_year descending."""
    order = {'active': 0, 'planning': 1, 'dormant': 2, 'completed': 3}
    def key(s):
        p = projects[s]
        st = (p.get('status') or '').lower()
        yr = _project_start_year(p)
        return (order.get(st, 9), -(int(yr) if yr.isdigit() else 0), p.get('name', s).lower())
    return sorted(projects.keys(), key=key)

def _find_related(slug, proj, all_projects):
    """Find projects sharing themes with the given project."""
    my_themes = set(proj.get('themes') or [])
    if not my_themes: return []
    related = []
    for s, p in all_projects.items():
        if s == slug: continue
        overlap = my_themes & set(p.get('themes') or [])
        if overlap:
            related.append({'slug': s, 'name': p.get('name', s), 'status': p.get('status', ''), 'shared': sorted(overlap)})
    return sorted(related, key=lambda r: (-len(r['shared']), r['name'].lower()))[:10]

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg: #fafaf8; --bg-card: #ffffff; --text: #1a1a1a; --muted: #6b7280;
  --border: #e5e7eb; --hover: #f3f4f6; --accent: #0d9488;
  --status-active: #16a34a; --status-completed: #9ca3af;
  --status-planning: #eab308; --status-dormant: #dc2626;
  --status-internal: #ea580c;
  --shadow: 0 1px 3px rgba(0,0,0,0.06);
}
[data-theme="dark"] {
  --bg: #111111; --bg-card: #1a1a1a; --text: #e5e5e5; --muted: #9ca3af;
  --border: #2d2d2d; --hover: #222222; --accent: #2dd4bf;
  --status-active: #4ade80; --status-completed: #6b7280;
  --status-planning: #facc15; --status-dormant: #f87171;
  --status-internal: #fb923c;
  --shadow: 0 1px 3px rgba(0,0,0,0.3);
}
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--bg); color: var(--text); line-height: 1.6; transition: background 0.2s, color 0.2s; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.container { max-width: 1100px; margin: 0 auto; padding: 0 1.25rem; }
.container.narrow { max-width: 800px; }
header { padding: 1.5rem 0 1rem; border-bottom: 1px solid var(--border); position: relative;
  display: flex; align-items: baseline; gap: 1.5rem; }
header h1 { font-size: 1.4rem; font-weight: 600; letter-spacing: -0.02em; }
header nav a { font-size: 0.85rem; color: var(--muted); }
header nav a:hover { color: var(--text); }
#theme-toggle { position: absolute; top: 1.5rem; right: 0; background: none;
  border: 1px solid var(--border); border-radius: 6px; padding: 0.3rem 0.5rem;
  cursor: pointer; color: var(--text); font-size: 0.8rem; }
#theme-toggle:hover { background: var(--hover); }

.stats { padding: 1rem 0 0.5rem; color: var(--muted); font-size: 0.85rem; }

.filters { padding: 0.75rem 0; display: flex; gap: 0.75rem; flex-wrap: wrap; align-items: center; }
.filters input[type="text"] { padding: 0.4rem 0.7rem; border: 1px solid var(--border);
  border-radius: 6px; font-size: 0.85rem; background: var(--bg-card); color: var(--text); width: 220px; }
.fbtn { padding: 0.35rem 0.7rem; border: 1px solid var(--border); border-radius: 6px;
  font-size: 0.8rem; cursor: pointer; background: var(--bg-card); color: var(--text); }
.fbtn:hover { background: var(--hover); }
.fbtn.active { background: var(--accent); color: #fff; border-color: var(--accent); }

table { width: 100%; border-collapse: collapse; font-size: 0.85rem; margin-top: 0.5rem; }
th { text-align: left; padding: 0.5rem 0.6rem; border-bottom: 2px solid var(--border);
  color: var(--muted); font-weight: 500; font-size: 0.8rem; cursor: pointer; user-select: none; }
th:hover { color: var(--text); }
td { padding: 0.45rem 0.6rem; border-bottom: 1px solid var(--border); }
tr:hover { background: var(--hover); }
.pill { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 10px; font-size: 0.75rem; font-weight: 500; }
.pill-active { background: var(--status-active); color: #fff; }
.pill-completed { background: var(--status-completed); color: #fff; }
.pill-planning { background: var(--status-planning); color: #000; }
.pill-dormant { background: var(--status-dormant); color: #fff; }
.pill-internal { background: var(--status-internal); color: #fff; }
.pill-tag { background: var(--border); color: var(--text); font-size: 0.7rem; margin: 1px; }
.num { text-align: center; }

.profile-nav { padding: 0.75rem 0; display: flex; align-items: center; font-size: 0.85rem; border-bottom: 1px solid var(--border); }
.profile-nav .nav-back { margin-right: auto; }
.profile-nav .nav-prev { margin-right: 1rem; }
.profile-nav .nav-next { margin-left: 1rem; }
.profile-nav a { color: var(--muted); }
.profile-nav a:hover { color: var(--text); }

.profile-header { padding: 1.5rem 0 1rem; position: relative; }
.profile-header h2 { font-size: 1.3rem; font-weight: 600; }
.section { margin: 1.5rem 0; }
.section h3 { font-size: 1rem; font-weight: 600; margin-bottom: 0.75rem;
  padding-bottom: 0.3rem; border-bottom: 1px solid var(--border); }
form .field { margin-bottom: 0.75rem; display: flex; align-items: center; gap: 0.5rem; }
form .field label { width: 130px; font-size: 0.85rem; color: var(--muted); flex-shrink: 0; }
form .field input, form .field select, form .field textarea {
  flex: 1; padding: 0.4rem 0.6rem; border: 1px solid var(--border); border-radius: 6px;
  font-size: 0.85rem; background: var(--bg-card); color: var(--text); font-family: inherit; }
form .field textarea { min-height: 80px; resize: vertical; }
.btn { padding: 0.45rem 1.2rem; background: var(--accent); color: #fff; border: none;
  border-radius: 6px; font-size: 0.85rem; cursor: pointer; font-weight: 500; }
.btn:hover { opacity: 0.9; }
.btn-secondary { background: var(--bg-card); color: var(--text); border: 1px solid var(--border); }
.btn-secondary:hover { background: var(--hover); }
.btn-danger { background: #dc2626; }
.flash { padding: 0.6rem 1rem; background: #d1fae5; color: #065f46; border-radius: 6px;
  margin: 1rem 0; font-size: 0.85rem; }
[data-theme="dark"] .flash { background: #064e3b; color: #a7f3d0; }

.edit-btn { position: absolute; top: 1.5rem; right: 0; }
.profile-container.mode-view .edit-only { display: none; }
.profile-container.mode-edit .view-only { display: none; }
.view-field { font-size: 0.85rem; margin-bottom: 0.5rem; display: flex; gap: 0.5rem; }
.view-field .vf-label { width: 130px; color: var(--muted); flex-shrink: 0; }
.view-field .vf-value { flex: 1; }
.view-notes { font-size: 0.85rem; color: var(--text); white-space: pre-wrap;
  background: var(--hover); padding: 0.6rem 0.8rem; border-radius: 6px; margin-top: 0.25rem; }

.linked-list { list-style: none; }
.linked-list li { padding: 0.4rem 0; border-bottom: 1px solid var(--border); font-size: 0.85rem; }
.linked-list li:last-child { border-bottom: none; }
.linked-list .meta { color: var(--muted); font-size: 0.8rem; }

.tag-group { margin-bottom: 0.75rem; }
.tag-group-label { font-size: 0.8rem; color: var(--muted); margin-bottom: 0.3rem; text-transform: capitalize; }
.tag-grid { display: flex; flex-wrap: wrap; gap: 0.4rem; }
.tag-grid label { font-size: 0.8rem; padding: 0.2rem 0.5rem; border: 1px solid var(--border);
  border-radius: 10px; cursor: pointer; user-select: none; }
.tag-grid label:hover { background: var(--hover); }
.tag-grid input[type="checkbox"] { display: none; }
.tag-grid input[type="checkbox"]:checked + span { background: var(--accent); color: #fff;
  padding: 0.2rem 0.5rem; border-radius: 10px; margin: -0.2rem -0.5rem; }

.participant-row { display: flex; gap: 0.5rem; align-items: center; margin-bottom: 0.4rem; font-size: 0.85rem; }
.participant-row input, .participant-row select { padding: 0.3rem 0.5rem; border: 1px solid var(--border);
  border-radius: 6px; font-size: 0.8rem; background: var(--bg-card); color: var(--text); }
.participant-row .rm-btn { background: none; border: none; color: var(--muted); cursor: pointer; font-size: 1rem; }
.participant-row .rm-btn:hover { color: var(--status-dormant); }

.paper-row { display: flex; gap: 0.5rem; align-items: center; margin-bottom: 0.4rem; font-size: 0.85rem; }
.paper-row input { flex: 1; padding: 0.3rem 0.5rem; border: 1px solid var(--border);
  border-radius: 6px; font-size: 0.8rem; background: var(--bg-card); color: var(--text); }
.paper-row .rm-btn { background: none; border: none; color: var(--muted); cursor: pointer; font-size: 1rem; }
.paper-row .rm-btn:hover { color: var(--status-dormant); }

.alert-item { padding: 0.5rem 0; border-bottom: 1px solid var(--border); font-size: 0.85rem; }
.alert-tag { display: inline-block; padding: 0.1rem 0.4rem; border-radius: 8px;
  font-size: 0.72rem; font-weight: 500; background: #fef2f2; color: #991b1b; margin-right: 0.3rem; }
[data-theme="dark"] .alert-tag { background: #450a0a; color: #fca5a5; }
"""

THEME_JS = """
<script>
(function(){
  const t = localStorage.getItem('theme') || 'light';
  document.documentElement.setAttribute('data-theme', t);
  document.getElementById('theme-toggle').textContent = t === 'dark' ? 'Light' : 'Dark';
})();
document.getElementById('theme-toggle').addEventListener('click', function(){
  const cur = document.documentElement.getAttribute('data-theme');
  const nxt = cur === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', nxt);
  localStorage.setItem('theme', nxt);
  this.textContent = nxt === 'dark' ? 'Light' : 'Dark';
});
</script>
"""

def page(title, body, narrow=False):
    cls = 'container narrow' if narrow else 'container'
    flashes = ''.join(f'<div class="flash">{m}</div>' for m in (request.args.getlist('msg') or []))
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title} - Mainen Lab Projects</title>
<style>{CSS}</style></head>
<body>
<div class="{cls}">
<header>
  <h1><a href="/" style="color:var(--text);text-decoration:none">Projects</a></h1>
  <nav><a href="/">Projects</a> &middot; <a href="{PERSONNEL_URL}">Personnel</a> &middot; <a href="/alerts">Alerts</a></nav>
  <button id="theme-toggle">Dark</button>
</header>
{flashes}
{body}
</div>
{THEME_JS}
</body></html>"""

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def project_list():
    projects = load_projects()
    taxonomy = load_taxonomy()
    pubs_all = load_publications()
    pub_slugs = {p['_slug'] for p in pubs_all}

    counts = {'active': 0, 'completed': 0, 'planning': 0, 'dormant': 0, 'internal': 0}
    rows = []
    for slug in _sorted_project_slugs(projects):
        proj = projects[slug]
        status = (proj.get('status') or 'unknown').lower()
        ptype = (proj.get('type') or '').lower()
        counts[status] = counts.get(status, 0) + 1
        if ptype == 'internal':
            counts['internal'] += 1

        parts = _get_participants(proj)
        papers = _get_papers(proj)
        themes = proj.get('themes') or []
        theme_pills = ''.join(f'<span class="pill pill-tag">{_tag_label(taxonomy.get("themes", []), t)}</span>' for t in themes)

        rows.append({
            'slug': slug,
            'name': proj.get('name', slug),
            'status': status,
            'type': ptype,
            'start': _project_start_year(proj),
            'end': _project_end_year(proj),
            'n_papers': len(papers),
            'n_people': len(parts),
            'theme_pills': theme_pills,
        })

    stats = ', '.join(f'{v} {k}' for k, v in counts.items() if v)

    trows = ''
    for r in rows:
        pill = f'pill-{r["status"]}' if r['status'] in ('active', 'completed', 'planning', 'dormant') else ''
        type_pill = '<span class="pill pill-internal">internal</span>' if r['type'] == 'internal' else ''
        trows += f"""<tr data-status="{r['status']}" data-type="{r['type']}" data-name="{r['name'].lower()}">
  <td><a href="/project/{r['slug']}">{r['name']}</a></td>
  <td><span class="pill {pill}">{r['status']}</span></td>
  <td>{type_pill}</td>
  <td>{r['start']}</td><td>{r['end']}</td>
  <td class="num">{r['n_papers']}</td><td class="num">{r['n_people']}</td>
  <td>{r['theme_pills']}</td>
</tr>"""

    body = f"""
<div class="stats">{stats}</div>
<div class="filters">
  <input type="text" id="search" placeholder="Search projects..." oninput="filterTable()">
  <button class="fbtn active" onclick="setStatus(this,'all')">All</button>
  <button class="fbtn" onclick="setStatus(this,'active')">Active</button>
  <button class="fbtn" onclick="setStatus(this,'completed')">Completed</button>
  <button class="fbtn" onclick="setStatus(this,'internal')">Internal</button>
</div>
<table id="roster">
<thead><tr>
  <th onclick="sortTable(0)">Name</th><th onclick="sortTable(1)">Status</th>
  <th>Type</th><th onclick="sortTable(3)">Start</th>
  <th onclick="sortTable(4)">End</th><th onclick="sortTable(5)">Papers</th>
  <th onclick="sortTable(6)">People</th><th>Themes</th>
</tr></thead>
<tbody>{trows}</tbody>
</table>
<script>
let curStatus = 'all', sortCol = -1, sortAsc = true;
function setStatus(btn, s) {{
  curStatus = s;
  document.querySelectorAll('.fbtn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  filterTable();
}}
function filterTable() {{
  const q = document.getElementById('search').value.toLowerCase();
  document.querySelectorAll('#roster tbody tr').forEach(tr => {{
    const name = tr.dataset.name, st = tr.dataset.status, tp = tr.dataset.type;
    let show = true;
    if (curStatus === 'internal') show = tp === 'internal';
    else if (curStatus !== 'all') show = st === curStatus;
    if (q && !name.includes(q)) show = false;
    tr.style.display = show ? '' : 'none';
  }});
}}
function sortTable(col) {{
  if (sortCol === col) sortAsc = !sortAsc; else {{ sortCol = col; sortAsc = true; }}
  const tbody = document.querySelector('#roster tbody');
  const rows = Array.from(tbody.rows);
  rows.sort((a, b) => {{
    let av = a.cells[col].textContent.trim(), bv = b.cells[col].textContent.trim();
    if (col >= 5 && col <= 6) {{ av = parseInt(av)||0; bv = parseInt(bv)||0; return sortAsc ? av-bv : bv-av; }}
    return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
  }});
  rows.forEach(r => tbody.appendChild(r));
}}
</script>"""
    return page('Projects', body)


@app.route('/project/<slug>')
def project_view(slug):
    projects = load_projects()
    if slug not in projects:
        return page('Not Found', '<p>Project not found.</p>', narrow=True), 404

    proj = projects[slug]
    taxonomy = load_taxonomy()
    people = load_people()
    pubs_all = load_publications()
    pub_index = {p['_slug']: p for p in pubs_all}

    slugs = _sorted_project_slugs(projects)
    idx = slugs.index(slug)
    prev_slug = slugs[(idx - 1) % len(slugs)]
    next_slug = slugs[(idx + 1) % len(slugs)]

    status = (proj.get('status') or '').lower()
    ptype = (proj.get('type') or '').lower()
    participants = _get_participants(proj)
    papers = _get_papers(proj)
    related = _find_related(slug, proj, projects)

    edit_mode = request.args.get('edit') == '1'
    init_mode = 'mode-edit' if edit_mode else 'mode-view'
    pill_cls = f'pill-{status}' if status in ('active', 'completed', 'planning', 'dormant') else ''

    # --- View-mode sections ---
    def vf(label, val):
        if not val: return ''
        return f'<div class="view-field"><span class="vf-label">{label}</span><span class="vf-value">{val}</span></div>'

    view_info = ''
    view_info += vf('Status', f'<span class="pill {pill_cls}">{status}</span>')
    if ptype == 'internal':
        view_info += vf('Type', '<span class="pill pill-internal">internal</span>')
    pub_desc = proj.get('public_description', '')
    desc = proj.get('description', '')
    if pub_desc:
        view_info += f'<div style="margin-bottom:0.75rem"><div style="font-size:0.8rem;color:var(--muted);margin-bottom:0.25rem">Public Description</div><div class="view-notes">{pub_desc}</div></div>'
    if desc:
        collapsed = ' style="display:none"' if pub_desc else ''
        toggle_text = 'Show internal notes' if pub_desc else ''
        if pub_desc:
            view_info += f'<details style="margin-bottom:0.75rem"><summary style="font-size:0.8rem;color:var(--muted);cursor:pointer">Internal notes</summary><div class="view-notes" style="margin-top:0.25rem">{desc}</div></details>'
        else:
            view_info += f'<div class="view-notes" style="margin-bottom:0.75rem">{desc}</div>'
    view_info += vf('Start', _project_start_year(proj))
    ey = _project_end_year(proj)
    if ey:
        view_info += vf('End', ey)

    # Taxonomy tags view
    axes = ['themes', 'methods', 'scale', 'organisms', 'settings']
    tag_view = ''
    for axis in axes:
        tags = proj.get(axis) or []
        if not tags: continue
        axis_items = taxonomy.get(axis, [])
        pills = ' '.join(f'<span class="pill pill-tag">{_tag_label(axis_items, t)}</span>' for t in tags)
        tag_view += f'<div style="margin-bottom:0.4rem"><span class="vf-label" style="display:inline-block;width:90px;font-size:0.8rem;color:var(--muted)">{axis.title()}</span> {pills}</div>'

    # Participants view
    part_items = ''
    for p in participants:
        pid = p.get('person_id', '')
        role = p.get('role') or p.get('quality', '')
        pname = people.get(pid, {}).get('name', pid)
        part_items += f'<li><a href="{PERSONNEL_URL}/person/{pid}">{pname}</a> <span class="meta">({role})</span></li>'
    if not part_items:
        part_items = '<li class="meta">No participants linked.</li>'

    # Papers view
    pub_items = ''
    for ps in papers:
        pub = pub_index.get(ps)
        if pub:
            doi = pub.get('doi', '')
            doi_link = f' <a href="https://doi.org/{doi}" target="_blank">DOI</a>' if doi else ''
            pub_items += f'<li><strong>{pub.get("title","")}</strong> <span class="meta">({pub.get("year","")}) {pub.get("journal","")}{doi_link}</span></li>'
        else:
            pub_items += f'<li class="meta">{ps} (not found)</li>'
    if not pub_items:
        pub_items = '<li class="meta">No papers linked.</li>'

    # Related projects
    related_items = ''
    for r in related:
        rpill = f'pill-{r["status"]}' if r['status'] in ('active', 'completed', 'planning', 'dormant') else ''
        shared = ', '.join(r['shared'])
        related_items += f'<li><a href="/project/{r["slug"]}">{r["name"]}</a> <span class="pill {rpill}" style="margin-left:0.3rem">{r["status"]}</span> <span class="meta">({shared})</span></li>'

    # --- Edit-mode sections ---
    STATUSES = ['active', 'completed', 'planning', 'dormant']
    TYPES = ['', 'internal']

    def opt(vals, cur, labels=None):
        labels = labels or {v: v for v in vals}
        return ''.join(f'<option value="{v}"{" selected" if v == cur else ""}>{labels.get(v, v) or "(none)"}</option>' for v in vals)

    # Taxonomy checkboxes
    tag_edit = ''
    for axis in axes:
        axis_items = taxonomy.get(axis, [])
        all_slugs = _flatten_tags(axis_items)
        current = set(proj.get(axis) or [])
        checks = ''
        for ts in all_slugs:
            lbl = _tag_label(axis_items, ts)
            chk = ' checked' if ts in current else ''
            checks += f'<label><input type="checkbox" name="tax_{axis}" value="{ts}"{chk}><span>{lbl}</span></label> '
        tag_edit += f'<div class="tag-group"><div class="tag-group-label">{axis.title()}</div><div class="tag-grid">{checks}</div></div>'

    # People slugs for autocomplete
    people_slugs = sorted(people.keys())
    people_datalist = ''.join(f'<option value="{s}">{people[s].get("name", s)}</option>' for s in people_slugs)
    pub_slugs_all = sorted(pub_index.keys())
    pub_datalist = ''.join(f'<option value="{s}">' for s in pub_slugs_all)

    # Participant edit rows
    part_edit = ''
    for i, p in enumerate(participants):
        pid = p.get('person_id', '')
        role = p.get('role') or p.get('quality', '')
        part_edit += f"""<div class="participant-row" id="part-{i}">
  <input name="part_person[]" value="{pid}" list="people-list" placeholder="person slug" style="flex:1">
  <input name="part_role[]" value="{role}" placeholder="role" style="width:120px">
  <button type="button" class="rm-btn" onclick="this.parentElement.remove()">&times;</button>
</div>"""

    # Paper edit rows
    paper_edit = ''
    for i, ps in enumerate(papers):
        paper_edit += f"""<div class="paper-row" id="paper-{i}">
  <input name="paper_slug[]" value="{ps}" list="pub-list" placeholder="publication slug">
  <button type="button" class="rm-btn" onclick="this.parentElement.remove()">&times;</button>
</div>"""

    body = f"""
<datalist id="people-list">{people_datalist}</datalist>
<datalist id="pub-list">{pub_datalist}</datalist>
<div class="profile-nav">
  <span class="nav-back"><a href="/">&larr; All Projects</a></span>
  <span class="nav-prev"><a href="/project/{prev_slug}">&larr; {projects[prev_slug].get('name', prev_slug)}</a></span>
  <span class="nav-next"><a href="/project/{next_slug}">{projects[next_slug].get('name', next_slug)} &rarr;</a></span>
</div>
<div class="profile-container {init_mode}" id="profile-container">
<div class="profile-header">
  <h2>{proj.get('name', slug)}</h2>
  <div style="color:var(--muted);font-size:0.95rem;margin-top:0.25rem">
    <span class="pill {pill_cls}">{status}</span>
    {' <span class="pill pill-internal">internal</span>' if ptype == 'internal' else ''}
    <span style="margin-left:0.5rem">{_project_start_year(proj)}{' - ' + ey if ey else ''}</span>
  </div>
  <button class="btn btn-secondary edit-btn view-only" onclick="toggleEdit(true)">Edit</button>
  <button class="btn btn-secondary edit-btn edit-only" onclick="toggleEdit(false)">Cancel</button>
</div>

<!-- VIEW MODE -->
<div class="view-only">
<div class="section">
  <h3>Info</h3>
  {view_info}
</div>
{f'<div class="section"><h3>Taxonomy</h3>{tag_view}</div>' if tag_view else ''}
</div>

<!-- EDIT MODE -->
<form method="POST" action="/project/{slug}/save" class="edit-only">
<div class="section">
  <h3>Info</h3>
  <div class="field"><label>Name</label><input name="name" value="{proj.get('name', '')}"></div>
  <div class="field"><label>Status</label><select name="status">{opt(STATUSES, status)}</select></div>
  <div class="field"><label>Type</label><select name="type">{opt(TYPES, ptype)}</select></div>
  <div class="field"><label>Internal Description</label><textarea name="description">{desc}</textarea></div>
  <div class="field"><label>Public Description</label>
    <div style="flex:1;display:flex;flex-direction:column;gap:0.4rem">
      <textarea name="public_description" id="public_description" style="min-height:80px">{pub_desc}</textarea>
      <button type="button" class="btn btn-secondary" style="align-self:flex-start;font-size:0.8rem" onclick="generateDescription()">&#10024; Generate Description</button>
    </div>
  </div>
  <div class="field"><label>Start year</label><input type="number" name="start_year" value="{_project_start_year(proj)}" min="1990" max="2040"></div>
  <div class="field"><label>End year</label><input type="number" name="end_year" value="{_project_end_year(proj)}" min="1990" max="2040"></div>
</div>

<div class="section">
  <h3>Taxonomy Tags</h3>
  {tag_edit}
</div>

<div class="section">
  <h3>Participants</h3>
  <div id="participants-container">{part_edit}</div>
  <button type="button" class="btn btn-secondary" style="margin-top:0.5rem" onclick="addParticipant()">+ Add participant</button>
</div>

<div class="section">
  <h3>Papers</h3>
  <div id="papers-container">{paper_edit}</div>
  <button type="button" class="btn btn-secondary" style="margin-top:0.5rem" onclick="addPaper()">+ Add paper</button>
</div>

<div style="padding:1.5rem 0;display:flex;gap:0.75rem">
  <button type="submit" class="btn">Save</button>
  <button type="button" class="btn btn-secondary" onclick="toggleEdit(false)">Cancel</button>
</div>
</form>

<!-- SHARED SECTIONS -->
<div class="section">
  <h3>Participants ({len(participants)})</h3>
  <ul class="linked-list">{part_items}</ul>
</div>

<div class="section">
  <h3>Papers ({len(papers)})</h3>
  <ul class="linked-list">{pub_items}</ul>
</div>

{f'<div class="section"><h3>Related Projects ({len(related)})</h3><ul class="linked-list">{related_items}</ul></div>' if related_items else ''}

</div>

<script>
function toggleEdit(on) {{
  const c = document.getElementById('profile-container');
  c.classList.toggle('mode-view', !on);
  c.classList.toggle('mode-edit', on);
  const url = new URL(window.location);
  if (on) url.searchParams.set('edit', '1');
  else url.searchParams.delete('edit');
  history.replaceState(null, '', url);
}}
let partIdx = {len(participants)};
function addParticipant() {{
  const div = document.createElement('div');
  div.className = 'participant-row';
  div.innerHTML = '<input name="part_person[]" list="people-list" placeholder="person slug" style="flex:1">'
    + '<input name="part_role[]" placeholder="role" style="width:120px">'
    + '<button type="button" class="rm-btn" onclick="this.parentElement.remove()">&times;</button>';
  document.getElementById('participants-container').appendChild(div);
}}
function generateDescription() {{
  const btn = event.target;
  btn.disabled = true;
  btn.textContent = 'Generating...';
  fetch('/project/{slug}/generate-description', {{ method: 'POST' }})
    .then(r => r.json())
    .then(data => {{
      if (data.description) {{
        document.getElementById('public_description').value = data.description;
      }} else if (data.error) {{
        alert('Error: ' + data.error);
      }}
    }})
    .catch(e => alert('Error: ' + e))
    .finally(() => {{ btn.disabled = false; btn.textContent = '\\u2728 Generate Description'; }});
}}
let paperIdx = {len(papers)};
function addPaper() {{
  const div = document.createElement('div');
  div.className = 'paper-row';
  div.innerHTML = '<input name="paper_slug[]" list="pub-list" placeholder="publication slug">'
    + '<button type="button" class="rm-btn" onclick="this.parentElement.remove()">&times;</button>';
  document.getElementById('papers-container').appendChild(div);
}}
</script>"""
    return page(proj.get('name', slug), body, narrow=True)


@app.route('/project/<slug>/save', methods=['POST'])
def save_project(slug):
    yf = PROJECTS_DIR / slug / 'project.yaml'
    if not yf.exists():
        return 'Not found', 404

    data = load_yaml(str(yf))
    form = request.form

    # Simple fields
    for field in ('name', 'description', 'public_description'):
        val = form.get(field, '').strip()
        if val:
            data[field] = val
        elif field in ('description', 'public_description'):
            data[field] = ''

    data['status'] = form.get('status', 'active').strip()

    ptype = form.get('type', '').strip()
    if ptype:
        data['type'] = ptype
    elif 'type' in data:
        del data['type']

    # Dates
    sy = form.get('start_year', '').strip()
    if sy:
        data['start_date'] = f'{sy}-01-01'
    ey = form.get('end_year', '').strip()
    if ey:
        data['end_date'] = f'{ey}-12-31'
    elif 'end_date' in data:
        del data['end_date']

    # Taxonomy axes
    for axis in ('themes', 'methods', 'scale', 'organisms', 'settings'):
        vals = form.getlist(f'tax_{axis}')
        data[axis] = vals

    # Participants — determine which key the project uses
    part_key = 'participants' if 'participants' in data else 'people'
    persons = form.getlist('part_person[]')
    roles = form.getlist('part_role[]')
    new_parts = []
    for pid, role in zip(persons, roles):
        pid = pid.strip()
        role = role.strip()
        if not pid: continue
        entry = {'person_id': pid}
        if role:
            if part_key == 'participants':
                entry['quality'] = role
            else:
                entry['role'] = role
        new_parts.append(entry)
    data[part_key] = new_parts

    # Papers
    paper_slugs = form.getlist('paper_slug[]')
    data['papers'] = [s.strip() for s in paper_slugs if s.strip()]

    dump_yaml(data, str(yf))
    return redirect(f'/project/{slug}?msg=Saved')


GENERATE_SCRIPT = BASE / 'workspaces/zach/web/mainenlab/scripts/generate_description.py'

@app.route('/project/<slug>/generate-description', methods=['POST'])
def generate_description_endpoint(slug):
    yf = PROJECTS_DIR / slug / 'project.yaml'
    if not yf.exists():
        return jsonify({'error': 'Not found'}), 404
    try:
        # Import the generation function directly
        import importlib.util
        spec = importlib.util.spec_from_file_location("generate_description", str(GENERATE_SCRIPT))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        taxonomy = mod.load_taxonomy()
        desc = mod.generate_description(slug, taxonomy)
        if not desc:
            return jsonify({'error': 'Could not generate description'}), 500
        return jsonify({'description': desc})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/alerts')
def alerts():
    projects = load_projects()
    items = []

    for slug, proj in projects.items():
        status = (proj.get('status') or '').lower()
        ptype = (proj.get('type') or '').lower()
        link = f'<a href="/project/{slug}">{proj.get("name", slug)}</a>'
        parts = _get_participants(proj)
        papers = _get_papers(proj)
        themes = proj.get('themes') or []
        desc = proj.get('description', '')

        if status == 'active' and not papers and ptype != 'internal':
            items.append(('no-papers', f'{link} is active with 0 linked papers'))
        if not parts:
            items.append(('no-people', f'{link} has no participants'))
        if status == 'active' and not desc:
            items.append(('no-description', f'{link} is active with no description'))
        if not themes and not any(proj.get(a) for a in ('methods', 'scale', 'organisms', 'settings')):
            items.append(('no-tags', f'{link} has no taxonomy tags'))

    alert_html = ''
    for tag, text in items:
        alert_html += f'<div class="alert-item"><span class="alert-tag">{tag}</span> {text}</div>'
    if not alert_html:
        alert_html = '<p style="color:var(--muted);font-size:0.85rem;padding:1rem 0">No alerts. Everything looks good.</p>'

    body = f"""
<div class="section" style="margin-top:1.5rem">
  <h3>Data Quality Alerts ({len(items)})</h3>
  {alert_html}
</div>"""
    return page('Alerts', body, narrow=True)


@app.route('/api/projects')
def api_projects():
    projects = load_projects()
    result = []
    for slug in _sorted_project_slugs(projects):
        proj = projects[slug]
        proj['_slug'] = slug
        proj['_n_papers'] = len(_get_papers(proj))
        proj['_n_people'] = len(_get_participants(proj))
        result.append(proj)
    return jsonify(result)


if __name__ == '__main__':
    print(f'YAML engine: {YAML_ENGINE}')
    print(f'Projects dir: {PROJECTS_DIR} ({len(list(PROJECTS_DIR.iterdir()))} entries)')
    print(f'People dir: {PEOPLE_DIR} ({len(list(PEOPLE_DIR.iterdir()))} entries)')
    print(f'Publications dir: {PUBS_DIR} ({len(list(PUBS_DIR.iterdir()))} entries)')
    host = os.environ.get('HAAK_HOST', '127.0.0.1')
    app.run(host=host, port=18831, debug=True)
