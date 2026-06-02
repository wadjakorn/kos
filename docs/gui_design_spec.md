# KOS GUI — Design Handoff Spec

**Audience:** product/UX designer.
**Purpose:** design a GUI front end for the Knowledge Operating System (KOS). This
spec describes the existing engine, the workflows to surface, screen-by-screen
requirements, system states, and the hard rules the UI must never break. No
visual design exists yet — you own look, layout, and interaction patterns. This
defines *what* the screens must do, not *how* they look.

---

## 1. What KOS is (one paragraph)

KOS turns documents into a searchable web of small, reusable knowledge units.
You feed it a source (a web page, a feed, a book, a Word doc, a video). It
extracts **atoms** — the smallest standalone ideas — each tagged and traceable
back to where it came from. Atoms link into **theses** (claims you're tracking)
and **projects** (goals you're working toward). Everything is browsable through
auto-generated **indexes**. Today it is a command-line tool over plain files in a
git repo; the GUI is a friendlier face over the same engine.

---

## 2. The five entities (the data the UI shows)

| Entity | What it is | Key fields the UI surfaces |
|--------|-----------|-----------------------------|
| **Source** | An ingested document. Origin of atoms. | title, origin (URL/path), ingested date, reliability (0–1 trust score), summary, tags, list of atoms it produced |
| **Atom** | Smallest reusable idea. | type (`fact` / `insight` / `decision` / `procedure`), title, body, tags, source + source_location (provenance), created date, confidence (0–1), linked theses, linked projects |
| **Thesis** | A claim under evaluation. | title, status (`active` / `confirmed` / `challenged` / `archived`), confidence, supporting_atoms, contradicting_atoms |
| **Project** | A goal-oriented workspace. | objective, linked atoms, linked theses, open questions, decisions, deliverables |
| **Index** | Auto-generated registry. | master, topic (by tag), source (atoms per source), thesis, tag (vocabulary + counts) |

**Atom types — give each a distinct visual token (icon/color):**
- `fact` — verifiable statement
- `insight` — interpretation / synthesis
- `decision` — a choice that was made
- `procedure` — a how-to / steps

**Reliability & confidence are 0–1 floats.** Show as a meter/badge, not a raw
number where avoidable. Reliability = trust in the *source*. Confidence = trust
in the *atom* or *thesis*.

---

## 3. Primary user & jobs-to-be-done

One user (knowledge worker / researcher / the repo owner). Not multi-tenant. Jobs:

1. **Capture** — "I found something worth keeping. Get it into the system with
   minimal friction." (paste a URL, drop a file)
2. **Review extraction** — "What did it pull out? Is that right?"
3. **Retrieve** — "What do I already know about X?" (search/browse atoms by tag,
   source, type)
4. **Curate** — "Track this claim. Link the evidence for and against it." (build
   theses; gather atoms into projects)
5. **Trust-check** — "Where did this come from? How reliable?" (follow
   provenance back to source)

---

## 4. Core workflows to design

### 4.1 Add a source (the money path)

Maps to the CLI `kos add <input>`. This is the most-used flow — make it fast.

**Input:** one of —
- a URL (web article)
- a feed URL (RSS/Atom — **expands to many sources, one per entry**)
- a YouTube URL (transcript)
- an uploaded file: `.md` `.txt` `.html` `.epub` `.docx`

**Options the user can set before submitting:**
- tags (free-form, comma-or-chip entry; auto-normalized to lowercase-kebab)
- title override (optional — system infers one)
- reliability (0–1, default 0.7) — a slider/stepper
- "scaffold only, don't process yet" toggle (CLI `--no-ingest`)

**The system auto-detects type from the input.** Designer should let the user
*override* the detected type (CLI `--type`) as an advanced/secondary control —
not a required first step. Detected type should be shown back to the user
("Detected: RSS feed → will create 12 sources").

**Steps the UI walks through:**
1. Input (paste URL or drop file) + options.
2. Fetch/parse (async, can take seconds — needs a progress state; YouTube/feeds
   can be slow).
3. Extraction → atoms produced.
4. Result: source(s) written, atoms minted, indexes updated. Show counts +
   links to the new source and its atoms.

**A feed produces N sources at once.** Design the result screen to handle 1 *or*
many sources from a single add.

### 4.2 Review what was extracted

After an add (or any time, from a source's detail view): show the source and the
atoms extracted from it, side by side with the original text where possible.
Each atom shows type, title, body, tags, confidence, and the `source_location`
(e.g. "§3", "p.12") that anchors it back to the source. Provenance is sacred
(see §7) — always visible.

### 4.3 Browse & search

Entry point mirrors `indexes/`. Surface these lenses:
- **All entities** (master index) — grouped by kind, counts per group.
- **By tag** (topic + tag index) — tag cloud / list with counts; click a tag →
  its atoms.
- **By source** (source index) — sources with their atoms nested under them.
- **By type** — filter atoms to fact/insight/decision/procedure.
- **Theses** — list with status + confidence; supporting/contradicting evidence.

Search across atom titles/bodies/tags. Filters compose (tag + type + source).

### 4.4 Curate theses

- Create a thesis (a claim). Set status, confidence.
- Attach atoms as **supporting** or **contradicting** evidence (drag/drop or
  pick from search).
- The thesis view shows the evidence balance at a glance (supporting vs
  contradicting). Status lifecycle: `active → confirmed | challenged → archived`.

### 4.5 Curate projects

- Create a project with an objective.
- Link atoms, theses. Track open questions, decisions, deliverables.
- A project is a workspace view pulling its linked entities together.

---

## 5. Screen inventory (minimum set)

1. **Home / Dashboard** — counts (sources, atoms, theses, projects), recent
   adds, quick "Add source" entry, jump-to-search. The at-a-glance state of the
   knowledge base.
2. **Add Source** — the §4.1 flow. Likely a modal or dedicated page with a
   progress/result state.
3. **Source detail** — frontmatter (origin, reliability, tags, summary) + the
   atoms extracted from it + link to original.
4. **Atom detail** — full atom; provenance link back to source +
   source_location; tags; linked theses/projects; type & confidence.
5. **Browse / Search** — the §4.3 lenses with composable filters.
6. **Thesis detail** — claim, status, confidence, supporting vs contradicting
   evidence columns.
7. **Project workspace** — objective + linked atoms/theses + open questions /
   decisions / deliverables.
8. **Tag / Topic view** — atoms for a tag.

(Settings/extraction config in §8 is optional/advanced — defer if scoping down.)

---

## 6. System states the UI must represent

Design empty / loading / error / success for each. Specific ones that matter:

- **Empty knowledge base** — fresh install, nothing ingested. Onboarding moment
  → push toward "Add your first source."
- **Fetching/parsing in progress** — network fetch + extraction is async and can
  take seconds (feeds, YouTube transcripts especially). Needs a real progress
  state, not a frozen button.
- **Source with zero atoms** — extraction can legitimately yield no atoms (e.g.
  a thin page, or marker mode on prose with no `::atom` markers). The source
  still exists. Show it as a valid-but-empty source, not an error. *(Engine note:
  zero-atom sources appear in the master index but not the source index, which
  groups atoms by source.)*
- **Empty-body skip** — if extracted text is blank, that doc is skipped with a
  notice. Surface which inputs were skipped after a multi-source add.
- **Duplicate / idempotent re-add** — re-adding unchanged content produces **0
  new atoms** by design (dedup by content hash). The UI must say "already
  known, nothing new" rather than imply failure.
- **Fetch failure** — network/URL error. Show the reason, offer retry.
- **TLS certificate failure** — a known real case (self-hosted/misconfigured
  hosts). The engine offers an "insecure / skip cert check" escape hatch. In a
  GUI this is a **security-sensitive confirmation** — see §7.
- **Missing dependency** — YouTube needs the external `yt-dlp` tool installed;
  if absent the add fails with a clear "install yt-dlp" message. Design a
  graceful "this input type needs an extra tool" state.
- **Unsupported file type** — clear rejection + the list of supported types +
  the option to force a loader type.

---

## 7. Non-negotiable rules the UI must respect

These come from the engine's contract. Breaking them corrupts the knowledge base.

1. **Indexes are generated, never editable.** Browse/search views are *read-only
   projections*. Never offer an "edit index" affordance. The system rebuilds
   them on every ingest.
2. **Every atom must show its provenance.** Source + source_location are
   required and always present. An atom detached from its origin is invalid —
   never design an atom view that hides where it came from.
3. **Idempotency is a feature, not a bug.** Re-processing the same content adds
   nothing. Frame "0 new atoms" as success ("already captured"), never as an
   error.
4. **"Insecure fetch" is a deliberate, explicit user choice.** Bypassing TLS
   verification must be an opt-in confirmation with a plain-language warning
   ("This skips the security check that proves the site is who it claims to be.
   Only for hosts you trust."). Never default-on, never silent.
5. **Index-first navigation.** The UI's job is to let users reach an atom
   through indexes/filters, then drop to the source only when the atom isn't
   enough. Mirror that hierarchy: indexes → atoms → source.

---

## 8. Optional / advanced surfaces (scope down if needed)

- **Extraction mode** — the engine has two: *marker* (default; parses
  human-written `::atom` blocks — deterministic, no AI) and *LLM* (a local model
  invents atoms from prose). The LLM mode has backends (a CLI command, or a local
  model server). This is power-user config. A GUI could expose a single toggle
  ("Let AI extract atoms automatically") + an advanced panel for the command /
  endpoint / model. Tokens/secrets come from environment variables, **never
  stored in a config field the UI writes** — don't design a "paste your API key
  here" box that persists to disk.
- **Manual atom authoring** — advanced users embed `::atom` blocks in markdown by
  hand. A GUI atom editor could write these. Lower priority.

---

## 9. CLI → GUI feature map (ground truth for behavior)

| CLI | GUI equivalent |
|-----|----------------|
| `kos add <url\|file>` | Add Source flow (§4.1) |
| `--tags a,b` | tag chip input |
| `--title T` | title override field |
| `--reliability 0.7` | reliability slider (default 0.7) |
| `--type ...` | "detected type — override" advanced control |
| `--no-ingest` | "scaffold only" toggle |
| `--insecure` | guarded "trust this host / skip cert check" confirmation (§7.4) |
| `ingest.py` (re-run) | implicit; happens after add. A manual "rebuild indexes" action could exist for power users |
| `ingest.py --dry-run` | a "preview what would be extracted" mode before committing |
| `indexes/master_index.md` etc. | the Browse/Search lenses (§4.3), read-only |

**Supported input types (today):** URL/`.html`, RSS/Atom feed, `.md`/`.txt`,
`.epub`, `.docx`, YouTube URL. New types can be added engine-side without UI
rework — design the type list to be extensible, not hardcoded to exactly six.

---

## 10. Tone & framing notes

- This is a *personal thinking tool*, not an enterprise dashboard. Favor
  calm, low-chrome, reading-friendly density. Atoms are text; the UI is mostly
  about making text findable and traceable.
- The emotional core is **trust**: every claim traces to a source with a
  reliability score. Make provenance feel reassuring and ever-present, not
  buried in a detail panel.
- Capture should feel **frictionless** (paste-and-go); curation (theses,
  projects) is slower, more deliberate work — those screens can afford more
  density and controls.

---

## 11. Open questions for the designer to flag back

- Mobile/responsive scope, or desktop-web only?
- Is real-time collaboration ever in scope? (Engine is single-user, git-native —
  assume no for now.)
- How heavy should the thesis "evidence balance" visualization be (simple two
  columns vs. a weighted/scored view)?
- Should the graph of atom↔thesis↔project links get a visual graph view, or is
  list/filter navigation enough for v1?
