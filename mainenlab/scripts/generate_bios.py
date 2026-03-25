#!/usr/bin/env python3
"""Generate short biographical profiles for Mainen Lab people using Claude API.

Reads person.yaml, bio.md, S2 cache, lab publications, and projects.
Caches results in .bio-cache.json keyed by person slug.
Only regenerates if cache miss or --force.

Usage:
    python3 scripts/generate_bios.py           # generate missing bios only
    python3 scripts/generate_bios.py --force   # regenerate all
    python3 scripts/generate_bios.py --dry-run # preview prompts, no API calls
"""

import json, re, sys, time, subprocess, argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent  # home/zach
LAB = ROOT / "projects" / "mainen-lab"
WEB = ROOT / "web" / "mainenlab"
BIO_CACHE_PATH = WEB / ".bio-cache.json"
S2_CACHE_PATH = WEB / ".s2-cache.json"

try:
    import yaml
    def load_yaml(path):
        with open(path) as f:
            return yaml.safe_load(f) or {}
except ImportError:
    raise SystemExit("PyYAML required: pip install pyyaml")


# ── PI CV narrative (loaded once) ──

PI_CV_PATH = Path.home() / "Downloads" / "ZFM - NIH Biosketch - Contributions to science - 2026-01.docx"

def load_pi_cv():
    if not PI_CV_PATH.exists():
        return ""
    try:
        result = subprocess.run(
            ["textutil", "-convert", "txt", "-stdout", str(PI_CV_PATH)],
            capture_output=True, text=True, timeout=10)
        return result.stdout.strip()
    except Exception:
        return ""


# ── Data loading ──

def load_people():
    people = []
    for f in sorted((LAB / "people").glob("*/person.yaml")):
        d = load_yaml(str(f))
        if not d.get("name"):
            continue
        people.append({
            "slug": f.parent.name,
            "name": d["name"],
            "status": d.get("status", "unknown"),
            "role": d.get("role", ""),
            "start_date": str(d.get("start_date", ""))[:4] or None,
            "end_date": str(d.get("end_date", ""))[:4] or None,
            "current_position": d.get("current_position", ""),
            "s2_id": str(d["s2_id"]) if d.get("s2_id") else "",
        })
    return people


def load_s2_cache():
    if S2_CACHE_PATH.exists():
        return json.loads(S2_CACHE_PATH.read_text())
    return {}


def load_publications():
    pubs = []
    for f in sorted((LAB / "publications").glob("*/paper.md")):
        text = f.read_text(errors="replace")
        if not text.startswith("---"):
            continue
        end = text.find("\n---", 3)
        if end < 0:
            continue
        meta = yaml.safe_load(text[4:end]) or {}
        if not meta.get("title"):
            continue
        authors = meta.get("authors", [])
        if isinstance(authors, str):
            authors = [authors]
        pubs.append({
            "slug": f.parent.name,
            "title": meta["title"],
            "year": meta.get("year", 0),
            "authors": authors,
            "journal": meta.get("journal", ""),
        })
    return pubs


def load_projects():
    projects = []
    for f in sorted((LAB / "projects").glob("*/project.yaml")):
        d = load_yaml(str(f))
        if d.get("type") == "internal":
            continue
        people_ids = []
        for p in d.get("people", d.get("participants", [])):
            if isinstance(p, dict):
                pid = p.get("person_id", p.get("id", ""))
                if pid:
                    people_ids.append(pid)
            elif isinstance(p, str):
                people_ids.append(p)
        projects.append({
            "slug": d.get("slug", f.parent.name),
            "name": d.get("name", f.parent.name),
            "people": people_ids,
        })
    return projects


def match_pubs_to_person(person_slug, person_name, publications):
    """Find lab publications involving this person (by slug in authors)."""
    matched = []
    name_parts = person_name.lower().split()
    last_name = name_parts[-1] if name_parts else ""
    for pub in publications:
        for author in pub["authors"]:
            a_lower = author.lower()
            if person_slug.replace("-", ", ") in a_lower:
                matched.append(pub)
                break
            elif last_name and last_name in a_lower.split(",")[0].split():
                # Check first initial too
                first_initial = name_parts[0][0].lower() if name_parts else ""
                parts = a_lower.split(",")
                if len(parts) > 1 and parts[1].strip().startswith(first_initial):
                    matched.append(pub)
                    break
    return matched


def get_s2_summary(person, s2_cache):
    """Get S2 papers summary, h-index, paper count for a person."""
    s2_id = person.get("s2_id", "")
    if not s2_id or s2_id not in s2_cache:
        return [], 0, 0
    papers = s2_cache[s2_id].get("papers", [])
    citations = sorted([p.get("citation_count", 0) for p in papers], reverse=True)
    h = sum(1 for i, c in enumerate(citations) if c >= i + 1)
    return papers, h, len(papers)


# ── API client ──

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


# ── Bio generation ──

def build_prompt(person, pi_cv, lab_pubs, s2_papers, h_index, paper_count, project_names):
    name = person["name"]
    role = person["role"] or "Member"
    start = person.get("start_date") or "?"
    end = person.get("end_date") or ("present" if person["status"] == "active" else "?")
    current = person.get("current_position") or ""

    lab_paper_lines = []
    for p in sorted(lab_pubs, key=lambda x: x.get("year", 0), reverse=True):
        lab_paper_lines.append(f"  - {p['title']} ({p.get('year', '?')}, {p.get('journal', '')})")

    s2_lines = []
    for p in sorted(s2_papers, key=lambda x: x.get("year") or 0, reverse=True)[:30]:
        s2_lines.append(f"  - {p.get('title', '?')} ({p.get('year', '?')})")
    if len(s2_papers) > 30:
        s2_lines.append(f"  ... and {len(s2_papers) - 30} more papers")

    prompt = f"""You are writing a short biographical profile for {name} for the Mainen Lab website (mainenlab.org).

Context about the Mainen Lab:
{pi_cv[:3000]}

Available data about {name}:
- Role at Mainen Lab: {role}, {start}-{end}
- Current position: {current}
- Projects in the lab: {', '.join(project_names) if project_names else 'none listed'}
- Publications with the lab:
{chr(10).join(lab_paper_lines) if lab_paper_lines else '  none matched'}
- Full publication record ({paper_count} papers, h-index {h_index}):
{chr(10).join(s2_lines) if s2_lines else '  no Semantic Scholar profile'}

Write 2-3 sentences about this person. Include:
- Their research focus (inferred from their publications and projects)
- Their role and contribution at the Mainen Lab
- Where they are now (if alumni)

Style: factual, concise, no hype. Written as if by a senior colleague who knows their work.
Do NOT invent facts. Only state what is supported by the data above.
Do NOT use phrases like "cutting-edge", "groundbreaking", "pioneering".
Do NOT include publication counts or h-index in the text.
Return ONLY the bio text, no heading or label."""

    return prompt


def generate_bio(person, pi_cv, lab_pubs, s2_papers, h_index, paper_count, project_names, dry_run=False):
    prompt = build_prompt(person, pi_cv, lab_pubs, s2_papers, h_index, paper_count, project_names)
    if dry_run:
        print(f"\n--- PROMPT for {person['slug']} ---")
        print(prompt[:500] + "...")
        return None

    client = get_client()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()


def main():
    parser = argparse.ArgumentParser(description="Generate bios for Mainen Lab people")
    parser.add_argument("--force", action="store_true", help="Regenerate all bios")
    parser.add_argument("--dry-run", action="store_true", help="Preview prompts only")
    parser.add_argument("--slug", help="Generate for one person only")
    args = parser.parse_args()

    print("Loading PI CV narrative...")
    pi_cv = load_pi_cv()
    print(f"  {len(pi_cv)} chars" if pi_cv else "  not found (proceeding without)")

    print("Loading people...")
    people = load_people()
    print(f"  {len(people)} people")

    print("Loading publications...")
    publications = load_publications()
    print(f"  {len(publications)} lab publications")

    print("Loading projects...")
    projects = load_projects()
    print(f"  {len(projects)} projects")

    print("Loading S2 cache...")
    s2_cache = load_s2_cache()
    print(f"  {len(s2_cache)} authors cached")

    # Load existing bio cache
    cache = {}
    if BIO_CACHE_PATH.exists():
        cache = json.loads(BIO_CACHE_PATH.read_text())
    print(f"  {len(cache)} bios in cache")

    generated = 0
    skipped = 0
    errors = []

    targets = people
    if args.slug:
        targets = [p for p in people if p["slug"] == args.slug]
        if not targets:
            print(f"Person '{args.slug}' not found")
            sys.exit(1)

    for person in targets:
        slug = person["slug"]

        if not args.force and slug in cache and not args.slug:
            skipped += 1
            continue

        # Gather context
        lab_pubs = match_pubs_to_person(slug, person["name"], publications)
        s2_papers, h_index, paper_count = get_s2_summary(person, s2_cache)
        project_names = [p["name"] for p in projects if slug in p.get("people", [])]

        try:
            bio = generate_bio(
                person, pi_cv, lab_pubs, s2_papers, h_index, paper_count,
                project_names, dry_run=args.dry_run)
            if bio:
                cache[slug] = bio
                generated += 1
                print(f"  [{generated}] {slug}: {bio[:80]}...")
                # Save after each to preserve progress
                BIO_CACHE_PATH.write_text(
                    json.dumps(cache, ensure_ascii=False, indent=2))
            elif args.dry_run:
                generated += 1
        except Exception as e:
            errors.append(f"{slug}: {e}")
            print(f"  [error] {slug}: {e}")

        if not args.dry_run:
            time.sleep(1)

    # Final save
    if not args.dry_run:
        BIO_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2))

    print(f"\nDone: {generated} generated, {skipped} cached, {len(errors)} errors")
    if errors:
        print("Errors:")
        for e in errors:
            print(f"  {e}")


if __name__ == "__main__":
    main()
