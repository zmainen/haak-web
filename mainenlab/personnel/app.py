#!/usr/bin/env python3
"""Mainen Lab Personnel Viewer/Editor — internal tool on 127.0.0.1:18830"""

import os, re, datetime, glob as globmod, json
from pathlib import Path
from flask import Flask, request, redirect, url_for, flash, jsonify

# YAML: prefer ruamel (preserves formatting) over PyYAML
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
app.secret_key = 'mainenlab-personnel-internal'

BASE = Path(__file__).resolve().parent.parent.parent.parent.parent.parent  # haak root
PEOPLE_DIR = BASE / 'workspaces/zach/projects/mainen-lab/people'
PROJECTS_DIR = BASE / 'workspaces/zach/projects/mainen-lab/projects'
PUBS_DIR = BASE / 'workspaces/zach/projects/mainen-lab/publications'
TAXONOMY_PATH = BASE / 'workspaces/zach/projects/mainen-lab/taxonomy.yaml'

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_people():
    people = {}
    for d in sorted(PEOPLE_DIR.iterdir()):
        yf = d / 'person.yaml'
        if not yf.exists(): continue
        slug = d.name
        try:
            data = load_yaml(str(yf))
            data['_slug'] = slug
            people[slug] = data
        except Exception:
            pass
    return people

def load_projects():
    projects = {}
    for d in sorted(PROJECTS_DIR.iterdir()):
        yf = d / 'project.yaml'
        if not yf.exists(): continue
        try:
            projects[d.name] = load_yaml(str(yf))
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

def person_projects(slug, projects):
    results = []
    for pname, proj in projects.items():
        parts = proj.get('participants') or proj.get('people') or []
        for p in parts:
            pid = p.get('person_id', '')
            if pid == slug or slug.startswith(pid) or pid.startswith(slug):
                results.append({
                    'name': proj.get('name', pname),
                    'slug': pname,
                    'status': proj.get('status', ''),
                    'role': p.get('role') or p.get('quality', ''),
                    'start': proj.get('start_date', ''),
                    'end': proj.get('end_date', ''),
                })
                break
    return results

def _position_display(p):
    """Context-sensitive position string for roster table."""
    status = (p.get('status') or '').lower()
    if status == 'active':
        role = p.get('role', '')
        start = str(p.get('start_date', ''))[:4]
        return f'{role} (since {start})' if start else role
    elif status == 'alumni':
        return p.get('current_position', '') or '—'
    elif status in ('visiting', 'collaborator'):
        return p.get('institution', '') or '—'
    return p.get('current_position', '') or '—'

def _sorted_slugs(people):
    """Return slugs in roster default order: active first, then alumni, alphabetical within each group."""
    order = {'active': 0, 'visiting': 1, 'collaborator': 2, 'alumni': 3}
    return sorted(people.keys(), key=lambda s: (order.get((people[s].get('status') or '').lower(), 9), people[s].get('name', s).lower()))

def _normalize(s):
    return re.sub(r'[^a-z]', '', s.lower())

def person_publications(person, pubs):
    name = person.get('name', '')
    parts = name.split()
    if not parts: return []
    last = _normalize(parts[-1])
    first_init = _normalize(parts[0])[0] if parts[0] else ''
    results = []
    for pub in pubs:
        authors = pub.get('authors', [])
        if not authors: continue
        for a in authors:
            an = _normalize(a)
            if last in an and first_init in an:
                results.append(pub)
                break
    return sorted(results, key=lambda x: x.get('year', 0), reverse=True)

# ---------------------------------------------------------------------------
# CSS (shared with main site palette)
# ---------------------------------------------------------------------------

CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg: #fafaf8; --bg-card: #ffffff; --text: #1a1a1a; --muted: #6b7280;
  --border: #e5e7eb; --hover: #f3f4f6; --accent: #0d9488;
  --status-active: #16a34a; --status-alumni: #9ca3af;
  --status-visiting: #3b82f6; --status-collaborator: #ea580c;
  --shadow: 0 1px 3px rgba(0,0,0,0.06);
}
[data-theme="dark"] {
  --bg: #111111; --bg-card: #1a1a1a; --text: #e5e5e5; --muted: #9ca3af;
  --border: #2d2d2d; --hover: #222222; --accent: #2dd4bf;
  --status-active: #4ade80; --status-alumni: #6b7280;
  --status-visiting: #60a5fa; --status-collaborator: #fb923c;
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

/* Stats bar */
.stats { padding: 1rem 0 0.5rem; color: var(--muted); font-size: 0.85rem; }

/* Filter bar */
.filters { padding: 0.75rem 0; display: flex; gap: 0.75rem; flex-wrap: wrap; align-items: center; }
.filters input[type="text"] { padding: 0.4rem 0.7rem; border: 1px solid var(--border);
  border-radius: 6px; font-size: 0.85rem; background: var(--bg-card); color: var(--text); width: 220px; }
.filters select { padding: 0.4rem 0.7rem; border: 1px solid var(--border);
  border-radius: 6px; font-size: 0.85rem; background: var(--bg-card); color: var(--text); }
.fbtn { padding: 0.35rem 0.7rem; border: 1px solid var(--border); border-radius: 6px;
  font-size: 0.8rem; cursor: pointer; background: var(--bg-card); color: var(--text); }
.fbtn:hover { background: var(--hover); }
.fbtn.active { background: var(--accent); color: #fff; border-color: var(--accent); }

/* Table */
table { width: 100%; border-collapse: collapse; font-size: 0.85rem; margin-top: 0.5rem; }
th { text-align: left; padding: 0.5rem 0.6rem; border-bottom: 2px solid var(--border);
  color: var(--muted); font-weight: 500; font-size: 0.8rem; cursor: pointer; user-select: none; }
th:hover { color: var(--text); }
td { padding: 0.45rem 0.6rem; border-bottom: 1px solid var(--border); }
tr:hover { background: var(--hover); }
.pill { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 10px; font-size: 0.75rem; font-weight: 500; }
.pill-active { background: var(--status-active); color: #fff; }
.pill-alumni { background: var(--status-alumni); color: #fff; }
.pill-visiting { background: var(--status-visiting); color: #fff; }
.pill-collaborator { background: var(--status-collaborator); color: #fff; }
.num { text-align: center; }

/* Profile nav */
.profile-nav { padding: 0.75rem 0; display: flex; align-items: center; font-size: 0.85rem; border-bottom: 1px solid var(--border); }
.profile-nav .nav-back { margin-right: auto; }
.profile-nav .nav-prev { margin-right: 1rem; }
.profile-nav .nav-next { margin-left: 1rem; }
.profile-nav a { color: var(--muted); }
.profile-nav a:hover { color: var(--text); }

/* Profile */
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
form .field textarea { min-height: 60px; resize: vertical; }
.btn { padding: 0.45rem 1.2rem; background: var(--accent); color: #fff; border: none;
  border-radius: 6px; font-size: 0.85rem; cursor: pointer; font-weight: 500; }
.btn:hover { opacity: 0.9; }
.btn-secondary { background: var(--bg-card); color: var(--text); border: 1px solid var(--border); }
.btn-secondary:hover { background: var(--hover); }
.flash { padding: 0.6rem 1rem; background: #d1fae5; color: #065f46; border-radius: 6px;
  margin: 1rem 0; font-size: 0.85rem; }
[data-theme="dark"] .flash { background: #064e3b; color: #a7f3d0; }

/* View/Edit mode toggle */
.edit-btn { position: absolute; top: 1.5rem; right: 0; }
.profile-container.mode-view .edit-only { display: none; }
.profile-container.mode-edit .view-only { display: none; }
.view-field { font-size: 0.85rem; margin-bottom: 0.5rem; display: flex; gap: 0.5rem; }
.view-field .vf-label { width: 130px; color: var(--muted); flex-shrink: 0; }
.view-field .vf-value { flex: 1; }
.contact-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.4rem 1.5rem; }
.view-notes { font-size: 0.85rem; color: var(--text); white-space: pre-wrap;
  background: var(--hover); padding: 0.6rem 0.8rem; border-radius: 6px; margin-top: 0.25rem; }

/* Linked items */
.linked-list { list-style: none; }
.linked-list li { padding: 0.4rem 0; border-bottom: 1px solid var(--border); font-size: 0.85rem; }
.linked-list li:last-child { border-bottom: none; }
.linked-list .meta { color: var(--muted); font-size: 0.8rem; }

/* Meetings */
.meeting-entry { padding: 0.5rem 0; border-bottom: 1px solid var(--border); font-size: 0.85rem; }
.meeting-entry:last-child { border-bottom: none; }
.meeting-date { color: var(--muted); font-size: 0.8rem; }
.meeting-type { display: inline-block; padding: 0.1rem 0.4rem; border-radius: 8px;
  font-size: 0.72rem; font-weight: 500; background: var(--border); color: var(--text); margin: 0 0.3rem; }
.add-meeting { margin-top: 0.75rem; padding: 0.75rem; background: var(--bg-card);
  border: 1px solid var(--border); border-radius: 8px; }
.add-meeting .field { margin-bottom: 0.5rem; }

/* Alerts */
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
<title>{title} - Mainen Lab Personnel</title>
<style>{CSS}</style></head>
<body>
<div class="{cls}">
<header>
  <h1><a href="/" style="color:var(--text);text-decoration:none">Personnel</a></h1>
  <nav><a href="/">Roster</a> &middot; <a href="http://127.0.0.1:18831">Projects</a> &middot; <a href="/alerts">Alerts</a></nav>
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
def roster():
    people = load_people()
    projects = load_projects()
    pubs = load_publications()

    counts = {'active': 0, 'alumni': 0, 'visiting': 0, 'collaborator': 0}
    roles = set()
    rows = []
    for slug, p in people.items():
        status = (p.get('status') or 'unknown').lower()
        role = p.get('role', '')
        roles.add(role)
        counts[status] = counts.get(status, 0) + 1
        pp = person_projects(slug, projects)
        ppubs = person_publications(p, pubs)
        rows.append({
            'slug': slug, 'name': p.get('name', slug), 'role': role, 'status': status,
            'start': str(p.get('start_date', '')), 'end': str(p.get('end_date', '')),
            'position': _position_display(p), 'email': p.get('email', ''),
            'n_projects': len(pp), 'n_papers': len(ppubs),
        })

    stats = ', '.join(f'{v} {k}' for k, v in counts.items() if v)
    role_opts = ''.join(f'<option value="{r}">{r}</option>' for r in sorted(roles) if r)

    trows = ''
    for r in rows:
        pill = f'pill-{r["status"]}' if r['status'] in ('active','alumni','visiting','collaborator') else ''
        email_icon = f' <a href="mailto:{r["email"]}" title="{r["email"]}" style="color:var(--muted);font-size:0.75rem">&#9993;</a>' if r['email'] else ''
        trows += f"""<tr data-status="{r['status']}" data-name="{r['name'].lower()}" data-role="{r['role'].lower()}">
  <td><a href="/person/{r['slug']}">{r['name']}</a>{email_icon}</td>
  <td>{r['role']}</td>
  <td><span class="pill {pill}">{r['status']}</span></td>
  <td>{r['start']}</td><td>{r['end']}</td>
  <td>{r['position']}</td>
  <td class="num">{r['n_projects']}</td><td class="num">{r['n_papers']}</td>
</tr>"""

    body = f"""
<div class="stats">{stats}</div>
<div class="filters">
  <input type="text" id="search" placeholder="Search by name..." oninput="filterTable()">
  <button class="fbtn active" onclick="setStatus(this,'all')">All</button>
  <button class="fbtn" onclick="setStatus(this,'active')">Active</button>
  <button class="fbtn" onclick="setStatus(this,'alumni')">Alumni</button>
  <button class="fbtn" onclick="setStatus(this,'visiting')">Visiting</button>
  <button class="fbtn" onclick="setStatus(this,'collaborator')">Collaborators</button>
  <select id="role-filter" onchange="filterTable()">
    <option value="">All roles</option>{role_opts}
  </select>
</div>
<table id="roster">
<thead><tr>
  <th onclick="sortTable(0)">Name</th><th onclick="sortTable(1)">Role</th>
  <th onclick="sortTable(2)">Status</th><th onclick="sortTable(3)">Start</th>
  <th onclick="sortTable(4)">End</th><th onclick="sortTable(5)">Position</th>
  <th onclick="sortTable(6)">Projects</th><th onclick="sortTable(7)">Papers</th>
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
  const role = document.getElementById('role-filter').value.toLowerCase();
  document.querySelectorAll('#roster tbody tr').forEach(tr => {{
    const name = tr.dataset.name, st = tr.dataset.status, rl = tr.dataset.role;
    const show = (curStatus === 'all' || st === curStatus)
      && (!q || name.includes(q))
      && (!role || rl === role);
    tr.style.display = show ? '' : 'none';
  }});
}}
function sortTable(col) {{
  if (sortCol === col) sortAsc = !sortAsc; else {{ sortCol = col; sortAsc = true; }}
  const tbody = document.querySelector('#roster tbody');
  const rows = Array.from(tbody.rows);
  rows.sort((a, b) => {{
    let av = a.cells[col].textContent.trim(), bv = b.cells[col].textContent.trim();
    if (col >= 6) {{ av = parseInt(av)||0; bv = parseInt(bv)||0; return sortAsc ? av-bv : bv-av; }}
    return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
  }});
  rows.forEach(r => tbody.appendChild(r));
}}
</script>"""
    return page('Roster', body)


@app.route('/person/<slug>')
def profile(slug):
    people = load_people()
    if slug not in people:
        return page('Not Found', '<p>Person not found.</p>', narrow=True), 404
    p = people[slug]
    # Compute prev/next navigation
    slugs = _sorted_slugs(people)
    idx = slugs.index(slug)
    prev_slug = slugs[(idx - 1) % len(slugs)]
    next_slug = slugs[(idx + 1) % len(slugs)]
    prev_name = people[prev_slug].get('name', prev_slug)
    next_name = people[next_slug].get('name', next_slug)
    projects = load_projects()
    pubs = load_publications()
    pp = person_projects(slug, projects)
    ppubs = person_publications(p, pubs)
    meetings = p.get('meetings') or []
    meetings_sorted = sorted(meetings, key=lambda m: str(m.get('date', '')), reverse=True)

    ROLES = ['PI','Postdoc','PhD Student','MSc Student','Technician','Lab Manager',
             'Visiting Scientist','Collaborator','Researcher']
    STATUSES = ['active','alumni','collaborator','visiting']
    MTYPES = ['1-on-1','thesis-committee','annual-review','milestone','note']

    def opt(vals, cur):
        return ''.join(f'<option value="{v}"{" selected" if v==cur else ""}>{v}</option>' for v in vals)

    proj_items = ''
    for pr in pp:
        proj_items += f'<li><strong>{pr["name"]}</strong> <span class="meta">({pr["status"]}) &mdash; {pr["role"]} &middot; {pr["start"]} - {pr["end"] or "present"}</span></li>'
    if not proj_items:
        proj_items = '<li class="meta">No linked projects found.</li>'

    pub_items = ''
    for pb in ppubs:
        doi = pb.get('doi', '')
        doi_link = f' <a href="https://doi.org/{doi}" target="_blank">DOI</a>' if doi else ''
        pub_items += f'<li><strong>{pb.get("title","")}</strong> <span class="meta">({pb.get("year","")}) {pb.get("journal","")}{doi_link}</span></li>'
    if not pub_items:
        pub_items = '<li class="meta">No linked publications found.</li>'

    meeting_items = ''
    for mt in meetings_sorted:
        meeting_items += f"""<div class="meeting-entry">
  <span class="meeting-date">{mt.get('date','')}</span>
  <span class="meeting-type">{mt.get('type','')}</span>
  {mt.get('text','')}
</div>"""

    today = datetime.date.today().isoformat()
    edit_mode = request.args.get('edit') == '1'
    init_mode = 'mode-edit' if edit_mode else 'mode-view'

    status = (p.get('status') or '').lower()
    # Context-sensitive subtitle
    if status == 'active':
        start_yr = str(p.get('start_date', ''))[:4]
        subtitle = f'{p.get("role","")} (since {start_yr})' if start_yr else p.get('role', '')
    elif status == 'alumni':
        cur_pos = p.get('current_position', '')
        subtitle = f'Now: {cur_pos}' if cur_pos else 'Alumni'
    elif status in ('visiting', 'collaborator'):
        subtitle = p.get('institution', '') or status.title()
    else:
        subtitle = p.get('role', '')

    pill_cls = f'pill-{status}' if status in ('active','alumni','visiting','collaborator') else ''

    # ORCID
    orcid_val = p.get('orcid', '')
    orcid_link = f' <a href="https://orcid.org/{orcid_val}" target="_blank" style="font-size:0.8rem">↗</a>' if orcid_val else ''

    # Helper for view-mode field display
    def vf(label, val, link_prefix=''):
        if not val: return ''
        if link_prefix:
            display = f'<a href="{link_prefix}{val}">{val}</a>'
        else:
            display = val
        return f'<div class="view-field"><span class="vf-label">{label}</span><span class="vf-value">{display}</span></div>'

    # View-mode: Info fields
    view_info = ''
    view_info += vf('Role', p.get('role', ''))
    view_info += vf('Status', f'<span class="pill {pill_cls}">{status}</span>')
    view_info += vf('Start date', str(p.get('start_date', '')))
    if p.get('end_date'):
        view_info += vf('End date', str(p.get('end_date', '')))
    view_info += vf('Institution', p.get('institution', ''))
    if status != 'active' and p.get('current_position'):
        view_info += vf('Current position', p.get('current_position', ''))
    notes = p.get('notes', '')
    if notes:
        view_info += f'<div class="view-field"><span class="vf-label">Notes</span></div><div class="view-notes">{notes}</div>'

    # View-mode: Contact fields
    view_contact = ''
    email = p.get('email', '')
    view_contact += vf('Email', email, 'mailto:') if email else ''
    view_contact += vf('Phone', p.get('phone', ''))
    if orcid_val:
        view_contact += f'<div class="view-field"><span class="vf-label">ORCID</span><span class="vf-value"><a href="https://orcid.org/{orcid_val}" target="_blank">{orcid_val}</a></span></div>'
    website = p.get('website', '')
    view_contact += vf('Website', website, '') if not website else f'<div class="view-field"><span class="vf-label">Website</span><span class="vf-value"><a href="{website}" target="_blank">{website}</a></span></div>'
    scholar = p.get('scholar', '')
    if scholar:
        view_contact += f'<div class="view-field"><span class="vf-label">Google Scholar</span><span class="vf-value"><a href="{scholar}" target="_blank">Profile</a></span></div>'

    body = f"""
<div class="profile-nav">
  <span class="nav-back"><a href="/">&larr; Roster</a></span>
  <span class="nav-prev"><a href="/person/{prev_slug}">&larr; {prev_name}</a></span>
  <span class="nav-next"><a href="/person/{next_slug}">{next_name} &rarr;</a></span>
</div>
<div class="profile-container {init_mode}" id="profile-container">
<div class="profile-header">
  <h2>{p.get('name', slug)}</h2>
  <div style="color:var(--muted);font-size:0.95rem;margin-top:0.25rem">{subtitle} <span class="pill {pill_cls}" style="margin-left:0.4rem">{status}</span></div>
  <button class="btn btn-secondary edit-btn view-only" onclick="toggleEdit(true)">Edit</button>
  <button class="btn btn-secondary edit-btn edit-only" onclick="toggleEdit(false)">Cancel</button>
</div>

<!-- ===== VIEW MODE ===== -->
<div class="view-only">
<div class="section">
  <h3>Info</h3>
  {view_info}
</div>
<div class="section">
  <h3>Contact</h3>
  <div class="contact-grid">{view_contact}</div>
</div>
</div>

<!-- ===== EDIT MODE (form) ===== -->
<form method="POST" action="/person/{slug}/save" class="edit-only">
<div class="section">
  <h3>Info</h3>
  <div class="field"><label>Name</label><input name="name" value="{p.get('name','')}"></div>
  <div class="field"><label>Role</label><select name="role">{opt(ROLES, p.get('role',''))}</select></div>
  <div class="field"><label>Status</label><select name="status">{opt(STATUSES, p.get('status',''))}</select></div>
  <div class="field"><label>Start date</label><input type="date" name="start_date" value="{p.get('start_date','')}"></div>
  <div class="field"><label>End date</label><input type="date" name="end_date" value="{p.get('end_date','')}"></div>
  <div class="field"><label>Institution</label><input name="institution" value="{p.get('institution','')}"></div>
  {"" if status == "active" else f'<div class="field"><label>Current position</label><input name="current_position" value="{p.get("current_position","")}"></div>'}
  <div class="field"><label>Notes</label><textarea name="notes">{p.get('notes','')}</textarea></div>
</div>

<div class="section">
  <h3>Contact</h3>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem 1.5rem">
    <div class="field"><label>Email</label><input name="email" value="{p.get('email','')}"></div>
    <div class="field"><label>Phone</label><input name="phone" value="{p.get('phone','')}"></div>
    <div class="field"><label>ORCID{orcid_link}</label><input name="orcid" value="{orcid_val}" placeholder="0000-0000-0000-0000"></div>
    <div class="field"><label>Website</label><input name="website" value="{p.get('website','')}" placeholder="https://..."></div>
    <div class="field"><label>Google Scholar</label><input name="scholar" value="{p.get('scholar','')}" placeholder="Scholar profile URL"></div>
  </div>
</div>

<div class="section edit-only">
  <h3>Meetings & Milestones — Add New</h3>
  <div class="add-meeting">
    <div class="field"><label>Date</label><input type="date" name="new_meeting_date" value="{today}"></div>
    <div class="field"><label>Type</label><select name="new_meeting_type">{opt(MTYPES, '')}</select></div>
    <div class="field"><label>Text</label><input name="new_meeting_text" placeholder="Meeting notes..."></div>
  </div>
</div>

<div style="padding:1.5rem 0;display:flex;gap:0.75rem">
  <button type="submit" class="btn">Save</button>
  <button type="button" class="btn btn-secondary" onclick="toggleEdit(false)">Cancel</button>
</div>
</form>

<!-- ===== Shared sections (always visible) ===== -->
<div class="section">
  <h3>Linked Projects ({len(pp)})</h3>
  <ul class="linked-list">{proj_items}</ul>
</div>

<div class="section">
  <h3>Publications ({len(ppubs)})</h3>
  <ul class="linked-list">{pub_items}</ul>
</div>

<div class="section">
  <h3>Meetings & Milestones ({len(meetings)})</h3>
  {meeting_items if meeting_items else '<p style="color:var(--muted);font-size:0.85rem">No meetings recorded.</p>'}
</div>

</div><!-- /profile-container -->

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
</script>"""
    return page(p.get('name', slug), body, narrow=True)


@app.route('/person/<slug>/save', methods=['POST'])
def save_person(slug):
    yf = PEOPLE_DIR / slug / 'person.yaml'
    if not yf.exists():
        return 'Not found', 404

    data = load_yaml(str(yf))
    form = request.form

    for field in ('name','role','status','email','orcid','institution','current_position','notes','phone','website','scholar'):
        val = form.get(field, '').strip()
        if val:
            data[field] = val
        elif field in ('notes','current_position','orcid','phone','website','scholar'):
            if field in data and not val:
                data[field] = ''

    for df in ('start_date','end_date'):
        val = form.get(df, '').strip()
        if val:
            data[df] = val
        elif df == 'end_date' and not val and df in data:
            del data[df]

    # Update active flag
    data['active'] = 1 if data.get('status') == 'active' else 0

    # New meeting entry
    mt_text = form.get('new_meeting_text', '').strip()
    if mt_text:
        entry = {
            'date': form.get('new_meeting_date', datetime.date.today().isoformat()),
            'type': form.get('new_meeting_type', 'note'),
            'text': mt_text,
        }
        if 'meetings' not in data:
            data['meetings'] = []
        data['meetings'].append(entry)

    dump_yaml(data, str(yf))
    return redirect(f'/person/{slug}?msg=Saved')


@app.route('/alerts')
def alerts():
    people = load_people()
    projects = load_projects()
    today = datetime.date.today()
    items = []

    for slug, p in people.items():
        status = (p.get('status') or '').lower()
        role = (p.get('role') or '').lower()
        start = p.get('start_date', '')
        link = f'<a href="/person/{slug}">{p.get("name", slug)}</a>'

        if not role:
            items.append(('missing-role', f'{link} has no role assigned'))

        if not p.get('email'):
            items.append(('missing-email', f'{link} has no email'))

        if status == 'alumni' and not p.get('end_date'):
            items.append(('no-end-date', f'{link} is alumni with no end date'))

        if status == 'active' and start:
            try:
                sd = datetime.date.fromisoformat(str(start)[:10])
                years = (today - sd).days / 365.25
                if 'phd' in role and years > 6:
                    items.append(('overdue', f'{link} — PhD student for {years:.1f} years'))
                if 'msc' in role and years > 2:
                    items.append(('overdue', f'{link} — MSc student for {years:.1f} years'))
            except ValueError:
                pass

        # Check if active member is on any active project
        if status == 'active':
            pp = person_projects(slug, projects)
            active_pp = [pr for pr in pp if pr.get('status') == 'active']
            if not active_pp:
                items.append(('no-project', f'{link} ({p.get("role","")}) is active but on no active projects'))

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


@app.route('/api/people')
def api_people():
    people = load_people()
    projects = load_projects()
    pubs = load_publications()
    result = []
    for slug, p in people.items():
        p['_projects'] = len(person_projects(slug, projects))
        p['_papers'] = len(person_publications(p, pubs))
        result.append(p)
    return jsonify(result)


if __name__ == '__main__':
    print(f'YAML engine: {YAML_ENGINE}')
    print(f'People dir: {PEOPLE_DIR} ({len(list(PEOPLE_DIR.iterdir()))} entries)')
    print(f'Projects dir: {PROJECTS_DIR} ({len(list(PROJECTS_DIR.iterdir()))} entries)')
    print(f'Publications dir: {PUBS_DIR} ({len(list(PUBS_DIR.iterdir()))} entries)')
    host = os.environ.get('HAAK_HOST', '127.0.0.1')
    app.run(host=host, port=18830, debug=True)
