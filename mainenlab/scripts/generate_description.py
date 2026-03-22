#!/usr/bin/env python3
"""Generate clean external-facing research descriptions for Mainen Lab projects.

Uses the Claude API (Anthropic SDK) to generate natural, high-quality
descriptions from project metadata and linked publications.

Usage:
    python generate_description.py <project-slug>
    python generate_description.py --all
    python generate_description.py <project-slug> --dry-run
"""

import sys, re, time, subprocess
from pathlib import Path

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

BASE = Path(__file__).resolve().parent.parent.parent.parent  # workspaces/zach
PROJECTS_DIR = BASE / 'projects' / 'mainen-lab' / 'projects'
PUBS_DIR = BASE / 'projects' / 'mainen-lab' / 'publications'
TAXONOMY_PATH = BASE / 'projects' / 'mainen-lab' / 'taxonomy.yaml'

# -- Abbreviation expansions --

ABBREVIATIONS = {
    'DRN': 'dorsal raphe nucleus',
    'drn': 'dorsal raphe nucleus',
    '5-HT': 'serotonin',
    '5-ht': 'serotonin',
    '5HT': 'serotonin',
    '5ht': 'serotonin',
    'PFC': 'prefrontal cortex',
    'pfc': 'prefrontal cortex',
    'OFC': 'orbitofrontal cortex',
    'ofc': 'orbitofrontal cortex',
    'IBL': 'International Brain Laboratory',
    'ibl': 'International Brain Laboratory',
    'SPE': 'state prediction error',
    'spe': 'state prediction error',
    'VR': 'virtual reality',
}

# -- Taxonomy label lookup --

def load_taxonomy():
    if TAXONOMY_PATH.exists():
        return load_yaml(str(TAXONOMY_PATH))
    return {}

def tag_label(taxonomy, axis, slug):
    for item in taxonomy.get(axis, []):
        if item.get('slug') == slug:
            return item.get('label', slug.replace('-', ' '))
        for child in item.get('children', []):
            if child.get('slug') == slug:
                return child.get('label', slug.replace('-', ' '))
    return slug.replace('-', ' ')

# -- Paper loading --

def load_paper_meta(slug):
    pf = PUBS_DIR / slug / 'paper.md'
    if not pf.exists():
        return None
    text = pf.read_text(errors='replace')
    m = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if not m:
        return None
    import yaml as _y
    return _y.safe_load(m.group(1)) or {}

# -- Label maps --

METHOD_LABELS = {
    'ephys': 'electrophysiology',
    'neuropixels': 'Neuropixels recordings',
    'optogenetics': 'optogenetics',
    'imaging': 'imaging',
    'modeling': 'computational modeling',
    'theory': 'theoretical approaches',
    'pharmacology': 'pharmacology',
    'behavior': 'behavioral experiments',
    'eye-tracking': 'eye tracking',
    'phenomenology': 'phenomenological methods',
    'physiology': 'physiology',
}

ORGANISM_LABELS = {
    'mouse': 'mice',
    'rat': 'rats',
    'human': 'humans',
}

SCALE_LABELS = {
    'molecular': 'molecular',
    'cellular': 'cellular',
    'circuit': 'circuit-level',
    'systems': 'brain-wide',
    'individual': 'individual-level',
    'social': 'social',
}

def join_natural(items):
    items = list(items)
    if len(items) <= 2:
        return ' and '.join(items)
    return ', '.join(items[:-1]) + ', and ' + items[-1]

# -- Sanitization (safety net after Claude output) --

def sanitize_description(text):
    """Apply strict rules: expand abbreviations, remove forbidden content."""
    for abbr, expansion in ABBREVIATIONS.items():
        text = re.sub(r'\b' + re.escape(abbr) + r'\b', expansion, text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'(?:projects/|data/|gdrive|google\s*drive)\S*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\b\w+/\w+(?:/\w+)+\b', '', text)
    text = re.sub(r'\b(?:funded by|grant|ERC|FCT|NIH|NSF|HHMI|Simons|funded|funding)\b\s*[^.]*\.?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(?:submitted|in revision|under review|in preparation|preprint|bioRxiv|arXiv)\b\s*[^.]*\.?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(?:HAAK|FiLiX|filix)\b[^.]*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\.{2,}', '.', text)
    text = re.sub(r'\s+\.', '.', text)
    return text

# -- API client --

_client = None

def get_client():
    global _client
    if _client is None:
        from anthropic import Anthropic
        result = subprocess.run(
            ['bash', '-c', 'source ~/.secrets && echo $ANTHROPIC_API_KEY'],
            capture_output=True, text=True)
        api_key = result.stdout.strip()
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not found in ~/.secrets")
        _client = Anthropic(api_key=api_key)
    return _client

SYSTEM_PROMPT = """You are writing research project descriptions for the Mainen Lab website at Champalimaud Foundation, Lisbon. Each description should be 2-3 sentences that convey the scientific question and approach.

STRICT RULES -- violations are unacceptable:
- NO person names (never mention researchers by name)
- NO target journals or publication venues
- NO grant names, funding sources, or application status
- NO internal project references, sibling projects, parent projects
- NO manuscript status (submitted, in revision, etc.)
- NO repository URLs, data paths, or file references
- NO unexpanded abbreviations on first use (expand DRN->dorsal raphe nucleus, 5-HT->serotonin, PFC->prefrontal cortex, OFC->orbitofrontal cortex, SPE->state prediction error; LSD can stay as LSD)
- NO internal jargon

STYLE:
- Write in FIRST PERSON PLURAL ("we investigate", "we use", "our work")
- For active/ongoing projects: use PRESENT TENSE, frame as questions being pursued, NOT results being declared. "We are investigating..." or "We track..." not "researchers discovered..."
- For completed projects: past tense is fine for established findings, but keep the question alive
- Lead with the motivating scientific question in accessible language
- Anchor claims in specific methods and approaches (Neuropixels, optogenetics, machine vision)
- Connect to fundamental questions (What is decision-making? How is perception constructed? What is consciousness?)
- Never start with "This project..." or "This research..." or "Researchers..."
- Tone: scholarly but accessible — like the best lab website prose, not popular science journalism
- Ground in concrete tools and data, not abstractions
- 2-3 sentences maximum

ADDITIONAL RULES:
- Always use first person plural (we/our), never third person (researchers/the team/scientists)"""

# -- Description generation --

def generate_description(slug, taxonomy):
    yf = PROJECTS_DIR / slug / 'project.yaml'
    if not yf.exists():
        return None
    proj = load_yaml(str(yf))

    name = proj.get('name', slug.replace('-', ' ').title())
    themes = proj.get('themes') or []
    methods = proj.get('methods') or []
    scale = proj.get('scale') or []
    organisms = proj.get('organisms') or []
    papers = proj.get('papers') or []
    desc = proj.get('description', '')

    # Gather paper titles
    paper_info = []
    for p in papers:
        ref = p.get('paper_id', p) if isinstance(p, dict) else p
        meta = load_paper_meta(ref)
        if meta:
            title = meta.get('title', '')
            year = meta.get('year', '')
            if title:
                paper_info.append(f"{title} ({year})" if year else title)

    # Readable labels
    theme_labels = [tag_label(taxonomy, 'themes', t) for t in themes]
    method_labels = [METHOD_LABELS.get(m, m.replace('-', ' ')) for m in methods]
    organism_labels = [ORGANISM_LABELS.get(o, o) for o in organisms]
    scale_labels = [SCALE_LABELS.get(s, s) for s in scale]

    # Build user prompt
    parts = [f"Write a public-facing description for this research project:\n"]
    parts.append(f"Project: {name}")
    if desc:
        parts.append(f"Internal description: {desc}")
    if theme_labels:
        parts.append(f"Themes: {join_natural(theme_labels)}")
    if method_labels:
        parts.append(f"Methods: {join_natural(method_labels)}")
    if scale_labels:
        parts.append(f"Scale: {join_natural(scale_labels)}")
    if organism_labels:
        parts.append(f"Organisms: {join_natural(organism_labels)}")
    if paper_info:
        parts.append(f"Key publications: {'; '.join(paper_info)}")
    parts.append("\nGenerate only the description text, nothing else.")

    user_prompt = '\n'.join(parts)

    client = get_client()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    text = response.content[0].text.strip()
    text = sanitize_description(text)
    return text

# -- CLI --

def process_one(slug, taxonomy, write=True):
    yf = PROJECTS_DIR / slug / 'project.yaml'
    if not yf.exists():
        print(f"  [skip] {slug}: project.yaml not found")
        return None

    desc = generate_description(slug, taxonomy)
    if not desc:
        print(f"  [skip] {slug}: could not generate description")
        return None

    print(f"  {slug}: {desc[:80]}...")

    if write:
        data = load_yaml(str(yf))
        data['public_description'] = desc
        dump_yaml(data, str(yf))

    return desc


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Generate external-facing research descriptions')
    parser.add_argument('slug', nargs='?', help='Project slug to process')
    parser.add_argument('--all', action='store_true', help='Process all non-internal projects')
    parser.add_argument('--dry-run', action='store_true', help='Print descriptions without writing')
    args = parser.parse_args()

    if not args.slug and not args.all:
        parser.error('Provide a project slug or --all')

    taxonomy = load_taxonomy()
    print(f"YAML engine: {YAML_ENGINE}")

    if args.all:
        count = 0
        for d in sorted(PROJECTS_DIR.iterdir()):
            yf = d / 'project.yaml'
            if not yf.exists():
                continue
            data = load_yaml(str(yf))
            if (data.get('type') or '').lower() == 'internal':
                continue
            process_one(d.name, taxonomy, write=not args.dry_run)
            count += 1
            time.sleep(1)  # rate limiting between API calls
        print(f"\nProcessed {count} projects")
    else:
        result = process_one(args.slug, taxonomy, write=not args.dry_run)
        if result:
            print(f"\nFull description:\n{result}")


if __name__ == '__main__':
    main()
