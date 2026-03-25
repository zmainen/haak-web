# Design Reference: Marshmallow Laser Feast (marshmallowlaserfeast.com)

Crawled 2026-03-25. Source of design inspiration for the Latent States site.

---

## 1. Site Structure and Navigation

**Three-section architecture.** The entire site reduces to three top-level navigation items:

- **Work** — full project portfolio (22 projects as of crawl date)
- **Exhibitions** — time-organized: Upcoming, Current, Past
- **Information** — studio description, contact, representation

No dropdowns, no mega-menus. The nav is flat and always visible. Breadcrumbs appear on project pages (Home > Project Title) but navigation is otherwise minimal — the site trusts its structure to be self-evident.

**Homepage as curated gateway.** The homepage is labeled "Features" and shows a subset of 8 works (not the full portfolio). This editorial layer separates "what we want you to see first" from "everything we've done." Pagination uses "Less -" / "More +" controls rather than numbered pages.

**Project URL pattern:** `/project/<slug>/` — clean, no dates or categories in the path.

### Takeaway for Latent States
The three-section model maps well: **Research** (= Work), **Team/Lab** (= Information), **News/Events** (= Exhibitions). A curated homepage that highlights 4-6 key projects rather than dumping the full list.

---

## 2. Visual Design Patterns

### Color Palette
Dark, immersive aesthetic. The site uses deep backgrounds (blacks, very dark grays) to let project imagery dominate. Text is light on dark. This creates a gallery/cinema feel — the work is the color, the chrome disappears.

### Typography
- **Project titles:** Large sans-serif, clean weight
- **Category labels:** Smaller, uppercase or lighter weight, positioned above titles
- **Body text:** Consistent serif or sans-serif (readable, not decorative)
- **Section headers** (e.g., "Artist statement"): Smaller emphasis styling, not competing with project titles
- Clear hierarchy: title >> category label >> body >> caption

### Spacing
Generous whitespace. Content breathes. The site is not dense — it uses vertical space liberally between sections on project pages. Images get room.

### Image Treatment
- **Base resolution:** 3000x2000px or 3000x1500px (2:1 and 3:2 aspect ratios)
- **Responsive serving:** Full-width on large screens, scaled down proportionally
- **No visible borders, rounded corners, or drop shadows** — images sit flush against the dark background
- **Image labels:** Sequential notation "[IMG. - 001]" through "[IMG. - 016]" with descriptive captions below
- **No lightbox or modal viewer apparent** — images are inline in the page flow

### Takeaway for Latent States
The dark-background, image-dominant approach suits a neuroscience lab with strong visual outputs (brain imaging, data visualization). Typography hierarchy is clean and worth emulating: project name dominates, metadata is subordinate.

---

## 3. Project/Work Presentation

### Work Index Page (Portfolio Grid)

Projects listed in a grid with:
- **Thumbnail image** (large, high-resolution)
- **Category label** above the title (e.g., "Immersive video installation," "Kinetic light installation," "Mixed Reality Performance," "Virtual Reality")
- **Project title** below the image

No descriptions on the index page — just image + category + title. This forces the click. The grid is responsive with contained image sizing.

### Categories Used
MLF uses medium/format as their primary taxonomy:
- Immersive video installation
- Video installation
- Kinetic light installation
- Mixed Reality Performance
- Virtual Reality
- Documentary Short
- Immersive Experience
- Multisensory XR Installation
- 360-degree audiovisual world

### Takeaway for Latent States
For a research lab, the equivalent taxonomy would be research themes or methods: "Electrophysiology," "Computational modeling," "Behavior," "Neural circuits." The pattern of image + category + title without description is worth adopting — it keeps the grid scannable.

---

## 4. Individual Project Pages

### Page Structure (consistent across projects)

1. **Hero image** — full-width, immediately below navigation
2. **Project title** — large heading
3. **Metadata sidebar/block:**
   - Release Date (year)
   - Type (category)
   - Specifications (technical: resolution, channels, format)
   - Editions (if applicable)
   - Commissioner
4. **Description** — 2-6 paragraphs, varying length (100-400 words typical)
5. **Image gallery** — inline, sequential, captioned with venue/date
6. **Artist statement** (some projects) — separate from description
7. **Credits** — hierarchical by role
8. **Exhibition history** — reverse chronological
9. **Press mentions** — hyperlinked quotes (some projects)
10. **Enquiry link** — "Enquire" for presenting the work
11. **Previous/Next navigation** — links to adjacent projects in portfolio

### Description Writing Style

**Tone:** Poetic but grounded. Opens with a concrete statement of what the work is, then expands into philosophical territory. Never purely technical, never purely lyrical — the balance is "here's what it does, here's why it matters."

**Examples of opening lines:**
- "Of The Oak is an immersive installation celebrating the oak tree as a network of relationships."
- "Sanctuary of the Unseen Forest is a large-scale video installation that creates a moment of awe, felt when we embrace the presence of a majestic being."
- "A collective virtual reality experience which drops audiences deep inside the landscape of the body, following the flow of oxygen through our branching ecosystem, to a single 'breathing' cell."

**Structure pattern:** Concrete description (what) -> Experiential narrative (how it feels) -> Scientific/philosophical framing (why it matters). Some projects add a "The Science Behind the Experience" section with more technical detail.

**Length:** 100-300 words for the main description. Some projects have additional sections (artist statement, science explanation) that extend to 500+ words total.

### Takeaway for Latent States
Research project pages should follow this pattern: concrete statement of the question, then the approach, then the significance. The metadata block (year, type, specifications) maps to: year, research area, methods, funding source. The exhibition history maps to publications and presentations.

---

## 5. Credits and Team

### Project-Level Credits

Credits are **hierarchical by role**, not alphabetical. Pattern:

1. **Lead artists / Core team** (named first, 2-3 people)
2. **Executive producers** (if applicable)
3. **Named talent** (voice, narration, music)
4. **Producers and technologists**
5. **Scientific advisors** (separate section)
6. **External consultants** (specialists)
7. **Commissioners / Funders**

Credit counts range from minimal (5-6 people) to extensive (40+ contributors). The format is: **Role:** Name, Name.

**Notable collaborators on Evolver:**
- Executive producers: Edward R. Pressman, Terrence Malick
- Narration: Cate Blanchett
- Music: Jonny Greenwood, Meredith Monk, Jon Hopkins
- Scientific advisors: Fraunhofer Institute, Allen Institute for Cell Science

### Studio-Level Credits (Information Page)

The Information page does **not** list individual team members with photos/bios. Instead it presents:
- A collective artist statement (the studio speaks as "we")
- Gallery representation (bitforms Gallery, Gazelli Art House)
- Contact emails by type (general, press, jobs)
- Studio address
- Social media links (Instagram, Facebook, X, Vimeo)

**This is a deliberate design choice** — MLF presents as a collective, not a roster of individuals. The studio identity supersedes individual profiles.

### Studio Philosophy (quoted)

> "We believe in the power of stories to tickle senses and shift perceptions."

> Work that takes "people on a multisensory journey to where imagination and information collide."

> Collaborating with "coders to poets, chemists to ventriloquists, brands to institutions."

> All work "grounded in research."

**Tone:** Confident, playful, interdisciplinary. Short declarative sentences. No academic hedging.

### Takeaway for Latent States
Two models to consider: (a) MLF's collective approach where the lab speaks as a unit and individuals appear only in project credits, or (b) a more traditional lab page with individual profiles. For a research lab, individual profiles with photos and research interests are probably expected — but the project-level credits pattern (PI, postdocs, students, collaborators, by role) is excellent.

---

## 6. Exhibitions Page

Three temporal categories, each with distinct treatment:

- **Upcoming:** Title, dates (month range), venue, city
- **Current:** Includes permanent installations — some without end dates
- **Past:** Reverse chronological, same metadata

Exhibition entries link to external ticketing or venue pages. The page emphasizes geographic reach ("London to New York, Melbourne to Seoul") and institutional prestige (Barbican, ACMI, Sundance).

### Takeaway for Latent States
Maps to a "News & Events" or "Presentations" page. The three-bucket temporal organization (upcoming talks, current exhibitions, past) is clean and useful.

---

## 7. Interactive Elements and Transitions

- **Previous/Next project navigation** at bottom of every project page — creates a "flip through the portfolio" behavior
- **"Enquire" links** — call to action for presenting work
- **External links** to project-specific microsites (e.g., oftheoak.co.uk field guide)
- **Pagination controls** on homepage: "Less -" / "More +" (not infinite scroll)
- **Prefetch configurations** for faster navigation between pages

No visible scroll-triggered animations, parallax effects, or complex JavaScript interactions in the HTML. The site lets the content (large images, video) provide the visual impact rather than relying on UI animation.

### Takeaway for Latent States
Restraint is the lesson. No parallax, no scroll animations, no hover tricks. Let the research imagery speak. Previous/Next navigation between projects is worth implementing.

---

## 8. Media Handling

- **Images:** Self-hosted, high-resolution (3000px wide), responsive. Sequential numbering with captions. No apparent lazy-loading markup in HTML (though may be handled by WordPress/JS).
- **Video:** Not prominently embedded on project pages examined. No Vimeo/YouTube iframes visible in the crawled pages, despite MLF being a video-heavy studio. Video may be handled through hero media or external links rather than inline players.
- **External media:** Links to Vimeo channel in social links. Project-specific sites host interactive content.

### Takeaway for Latent States
Self-hosted images at high resolution, captioned with context (experiment, setup, result). For video, consider linking to external platforms rather than embedding — keeps pages fast and clean.

---

## 9. Mobile Considerations

The site uses responsive image sizing (intrinsic dimensions with responsive containers). WordPress 6.9.4 with modern theme likely handles mobile breakpoints. The minimal navigation (three items) works well at any screen size. No hamburger menu apparent in the markup, suggesting the nav may stay visible even on mobile.

---

## 10. Technical Stack

- **CMS:** WordPress 6.9.4
- **Design:** Studio Airport (Amsterdam-based design studio)
- **Development:** September Digital
- **Analytics:** Plausible (privacy-respecting)
- **Error tracking:** Sentry
- **Performance:** Prefetch link configurations for faster navigation

---

## Summary: Design Principles Worth Adopting

| MLF Pattern | Latent States Equivalent |
|:------------|:------------------------|
| Dark, immersive background | Dark theme with brain imaging / data viz as visual anchors |
| Three-section navigation | Research, Team, News (or similar three-part structure) |
| Curated homepage (subset of work) | Featured projects, not exhaustive list |
| Image + category + title on grid | Image + research area + project name |
| Metadata block on project pages | Year, methods, funding, PI, publications |
| Poetic-but-grounded descriptions | Accessible science writing: question, approach, significance |
| Hierarchical credits by role | PI, postdocs, students, collaborators |
| Previous/Next project navigation | Browse between research projects |
| No UI animation; content speaks | Let the science visuals carry the design |
| Collective voice on about page | Lab identity and philosophy, then individual profiles |
| Exhibition timeline (upcoming/current/past) | Talks, workshops, conferences timeline |
