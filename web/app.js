"use strict";
/* KOS GUI — vanilla SPA. Hash routing, JSON API client, tiny markdown renderer.
   No build step, no dependencies. */

const App = {};
const appEl = () => document.getElementById("app");

let CONFIG = null;            // /api/config — extractor mode, supported types, statuses
const TYPE_META = {
  fact:      { icon: "●", cls: "type-fact" },
  insight:   { icon: "✦", cls: "type-insight" },
  decision:  { icon: "◆", cls: "type-decision" },
  procedure: { icon: "▸", cls: "type-procedure" },
};

/* ---------- API ---------- */
async function api(path, opts) {
  const res = await fetch(path, opts);
  const ct = res.headers.get("content-type") || "";
  const data = ct.includes("json") ? await res.json() : await res.text();
  if (!res.ok && !(data && data.error)) throw new Error(`HTTP ${res.status}`);
  return data;
}
const apiGet = (p) => api(p);
const apiSend = (p, method, body) =>
  api(p, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

/* ---------- escaping + helpers ---------- */
function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
function attr(s) { return esc(s).replace(/'/g, "&#39;"); }
const num = (v) => { const n = parseFloat(v); return isNaN(n) ? null : n; };

function render(html) { appEl().innerHTML = html; }
function setLoading() { render('<div class="loading">Loading…</div>'); }
function errorView(msg) {
  render(`<div class="banner banner-error">${esc(msg)}</div>
          <a class="btn" href="#/">← Dashboard</a>`);
}

/* ---------- visual tokens ---------- */
function typeBadge(type) {
  const m = TYPE_META[type] || TYPE_META.fact;
  return `<span class="type-badge ${m.cls}">${m.icon} ${esc(type || "fact")}</span>`;
}
function meter(label, value) {
  const n = num(value);
  if (n == null) return `<div class="meter"><span class="label">${esc(label)}</span><span class="pct muted">n/a</span></div>`;
  const pct = Math.round(n * 100);
  return `<div class="meter"><span class="label">${esc(label)}</span>
    <span class="track"><span class="fill" style="width:${pct}%"></span></span>
    <span class="pct">${pct}%</span></div>`;
}
function statusPill(status) {
  const s = status || "active";
  return `<span class="pill ${esc(s)}">${esc(s)}</span>`;
}
function tagList(tags, link = true) {
  tags = tags || [];
  if (!tags.length) return "";
  return `<div class="tags">${tags.map(t =>
    link ? `<a class="tag" href="#/tag/${encodeURIComponent(t)}">${esc(t)}</a>`
         : `<span class="tag">${esc(t)}</span>`).join("")}</div>`;
}
function excerpt(body, n = 160) {
  const s = (body || "").replace(/\s+/g, " ").trim();
  return s.length > n ? s.slice(0, n) + "…" : s;
}

/* ---------- minimal markdown renderer (+ [[ID]] wikilinks) ---------- */
function routeForId(id) {
  if (/^ATOM-/.test(id)) return `#/atom/${id}`;
  if (/^SRC-/.test(id)) return `#/source/${id}`;
  if (/^THESIS-/.test(id)) return `#/thesis/${id}`;
  if (/^PROJ-/.test(id)) return `#/project/${id}`;
  return null;
}
function inlineMd(text) {
  let s = esc(text);
  s = s.replace(/`([^`]+)`/g, (_, c) => `<code>${c}</code>`);
  s = s.replace(/\[\[([A-Za-z0-9\-]+)\]\]/g, (_, id) => {
    const r = routeForId(id);
    return r ? `<a class="wikilink" href="${r}">${id}</a>` : `[[${id}]]`;
  });
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, t, u) =>
    `<a href="${attr(u)}" ${/^https?:/.test(u) ? 'target="_blank" rel="noopener"' : ""}>${t}</a>`);
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>");
  return s;
}
function renderMarkdown(md) {
  const lines = (md || "").split("\n");
  let html = "", i = 0, listType = null;
  const closeList = () => { if (listType) { html += `</${listType}>`; listType = null; } };
  while (i < lines.length) {
    let line = lines[i];
    if (/^```/.test(line)) {
      closeList();
      const buf = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) buf.push(lines[i++]);
      i++;
      html += `<pre><code>${esc(buf.join("\n"))}</code></pre>`;
      continue;
    }
    const h = line.match(/^(#{1,4})\s+(.*)$/);
    if (h) { closeList(); html += `<h${h[1].length}>${inlineMd(h[2])}</h${h[1].length}>`; i++; continue; }
    const ul = line.match(/^\s*[-*]\s+(.*)$/);
    const cb = line.match(/^\s*[-*]\s+\[([ xX])\]\s+(.*)$/);
    const ol = line.match(/^\s*\d+\.\s+(.*)$/);
    if (cb) {
      if (listType !== "ul") { closeList(); html += "<ul>"; listType = "ul"; }
      const checked = cb[1].toLowerCase() === "x";
      html += `<li><input type="checkbox" disabled ${checked ? "checked" : ""}> ${inlineMd(cb[2])}</li>`;
      i++; continue;
    }
    if (ul) {
      if (listType !== "ul") { closeList(); html += "<ul>"; listType = "ul"; }
      html += `<li>${inlineMd(ul[1])}</li>`; i++; continue;
    }
    if (ol) {
      if (listType !== "ol") { closeList(); html += "<ol>"; listType = "ol"; }
      html += `<li>${inlineMd(ol[1])}</li>`; i++; continue;
    }
    if (line.trim() === "") { closeList(); i++; continue; }
    closeList();
    html += `<p>${inlineMd(line)}</p>`;
    i++;
  }
  closeList();
  return html;
}

/* ---------- shared fragments ---------- */
function atomCard(a) {
  return `<a class="card atom-card" href="#/atom/${esc(a.id)}">
    <div>${typeBadge(a.type)}</div>
    <div class="title">${esc(a.title) || "(untitled)"}</div>
    <div class="excerpt">${esc(excerpt(a.body))}</div>
    ${tagList(a.tags, false)}
  </a>`;
}
function atomRow(a) {
  if (a.missing) return `<div class="card"><span class="muted">missing: ${esc(a.id)}</span></div>`;
  return atomCard(a);
}

/* ===================================================================== */
/* Views                                                                 */
/* ===================================================================== */

async function viewDashboard() {
  setLoading();
  const s = await apiGet("/api/stats");
  const c = s.counts;
  const total = c.sources + c.atoms + c.theses + c.projects;
  if (total === 0) {
    render(`<div class="empty">
      <div class="big">Your knowledge base is empty.</div>
      <p>Capture your first document — paste a URL or drop a file, and KOS will
         extract the reusable ideas inside it.</p>
      <a class="btn btn-primary" href="#/add">+ Add your first source</a>
    </div>`);
    return;
  }
  const byType = Object.entries(s.by_type || {})
    .map(([t, n]) => `<span class="type-badge ${(TYPE_META[t]||TYPE_META.fact).cls}">${(TYPE_META[t]||TYPE_META.fact).icon} ${esc(t)} ${n}</span>`)
    .join(" ");
  render(`
    <div class="page-head"><h1>Dashboard</h1><span class="sub">at-a-glance state of the knowledge base</span>
      <button class="btn btn-sm" id="rebuildBtn" style="margin-left:auto" title="Re-run ingest: mint atoms from any new/changed sources (cached, idempotent) and regenerate all indexes">↻ Rebuild indexes</button>
    </div>
    <div id="rebuildMsg"></div>
    <div class="grid grid-stats" style="margin:18px 0">
      <a class="card stat" href="#/browse"><div class="n">${c.atoms}</div><div class="l">Atoms</div></a>
      <a class="card stat" href="#/browse?lens=source"><div class="n">${c.sources}</div><div class="l">Sources</div></a>
      <a class="card stat" href="#/theses"><div class="n">${c.theses}</div><div class="l">Theses</div></a>
      <a class="card stat" href="#/projects"><div class="n">${c.projects}</div><div class="l">Projects</div></a>
      <a class="card stat" href="#/tags"><div class="n">${c.tags}</div><div class="l">Tags</div></a>
    </div>
    <div style="margin:6px 0 22px">${byType}</div>
    <div class="row2">
      <div><h2>Recent atoms</h2><div class="list">${(s.recent_atoms||[]).map(atomCard).join("") || '<p class="muted">none yet</p>'}</div></div>
      <div><h2>Recent sources</h2><div class="list">${(s.recent_sources||[]).map(sourceRow).join("") || '<p class="muted">none yet</p>'}</div></div>
    </div>`);

  const btn = document.getElementById("rebuildBtn");
  const msg = document.getElementById("rebuildMsg");
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    msg.innerHTML = `<div class="banner banner-info"><span class="spinner"></span> Rebuilding — extracting from new/changed sources and regenerating indexes…</div>`;
    try {
      const r = await apiSend("/api/ingest", "POST", {});
      if (r.error) { msg.innerHTML = `<div class="banner banner-error">${esc(r.error)}</div>`; btn.disabled = false; return; }
      msg.innerHTML = `<div class="banner banner-ok">Indexes rebuilt.</div>`;
      viewDashboard();  // refresh counts
    } catch (e) {
      msg.innerHTML = `<div class="banner banner-error">${esc(e.message)}</div>`;
      btn.disabled = false;
    }
  });
}

function sourceRow(s) {
  const note = s.reliability != null ? meter("reliability", s.reliability) : "";
  return `<a class="card" href="#/source/${esc(s.id)}">
    <div class="title" style="font-weight:600">${esc(s.title) || "(untitled source)"}</div>
    <div class="meta-line">${s.ingested ? "ingested " + esc(s.ingested) : ""}${s.atom_count != null ? " · " + s.atom_count + " atoms" : ""}</div>
    ${note}
  </a>`;
}

/* ---------- Browse / Search ---------- */
async function viewBrowse(query) {
  setLoading();
  const lens = query.lens || "atoms";
  const lensNav = `<div class="lens">
    ${lensLink("atoms", "All atoms", lens, query)}
    ${lensLink("source", "By source", lens, query)}
    ${lensLink("tag", "By tag", lens, query)}
    <a class="btn btn-sm" href="#/theses">Theses</a>
    <a class="btn btn-sm" href="#/projects">Projects</a>
  </div>`;

  if (lens === "tag") {
    const tags = await apiGet("/api/tags");
    render(`<h1>Browse</h1>${lensNav}
      <div class="tags">${tags.map(t =>
        `<a class="tag" href="#/tag/${encodeURIComponent(t.tag)}">${esc(t.tag)}<span class="ct">${t.count}</span></a>`).join("") || '<p class="muted">no tags</p>'}</div>`);
    return;
  }
  if (lens === "source") {
    const sources = await apiGet("/api/sources");
    render(`<h1>Browse</h1>${lensNav}
      <div class="list">${sources.map(sourceRow).join("") || '<p class="muted">no sources</p>'}</div>`);
    return;
  }

  // atoms lens with composable filters
  const types = ["fact", "insight", "decision", "procedure"];
  const tags = await apiGet("/api/tags");
  const sources = await apiGet("/api/sources");
  const qs = new URLSearchParams();
  ["tag", "type", "source", "q"].forEach(k => { if (query[k]) qs.set(k, query[k]); });
  const atoms = await apiGet("/api/atoms?" + qs.toString());
  render(`<h1>Browse</h1>${lensNav}
    <div class="filterbar">
      <div class="field"><label>Search</label>
        <input type="search" id="f-q" value="${attr(query.q||"")}" placeholder="title / body / tag"></div>
      <div class="field"><label>Type</label>
        <div class="type-filter" id="f-type">
          ${types.map(t => `<button data-type="${t}" class="btn ${query.type===t?"on "+(TYPE_META[t].cls):""}" style="${query.type===t?"":""}">${esc(t)}</button>`).join("")}
        </div></div>
      <div class="field"><label>Tag</label>
        <select id="f-tag"><option value="">all</option>${tags.map(t=>`<option ${query.tag===t.tag?"selected":""}>${esc(t.tag)}</option>`).join("")}</select></div>
      <div class="field"><label>Source</label>
        <select id="f-source"><option value="">all</option>${sources.map(s=>`<option value="${attr(s.id)}" ${query.source===s.id?"selected":""}>${esc(s.title)}</option>`).join("")}</select></div>
      <button class="btn" id="f-clear">Clear</button>
    </div>
    <p class="muted">${atoms.length} atom${atoms.length===1?"":"s"}</p>
    <div class="grid grid-cards">${atoms.map(atomCard).join("") || '<p class="muted">No atoms match these filters.</p>'}</div>`);

  const apply = () => {
    const p = new URLSearchParams();
    const q = document.getElementById("f-q").value.trim();
    const tag = document.getElementById("f-tag").value;
    const src = document.getElementById("f-source").value;
    if (q) p.set("q", q);
    if (tag) p.set("tag", tag);
    if (src) p.set("source", src);
    if (query.type) p.set("type", query.type);
    location.hash = "#/browse?" + p.toString();
  };
  document.getElementById("f-q").addEventListener("change", apply);
  document.getElementById("f-tag").addEventListener("change", apply);
  document.getElementById("f-source").addEventListener("change", apply);
  document.getElementById("f-clear").addEventListener("click", () => location.hash = "#/browse");
  document.getElementById("f-type").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-type]"); if (!b) return;
    const t = b.dataset.type;
    const p = new URLSearchParams(location.hash.split("?")[1] || "");
    if (query.type === t) p.delete("type"); else p.set("type", t);
    location.hash = "#/browse?" + p.toString();
  });
}
function lensLink(key, label, current, query) {
  const p = new URLSearchParams(); p.set("lens", key);
  return `<a class="btn btn-sm ${current===key?"btn-primary":""}" href="#/browse?${p}">${label}</a>`;
}

async function viewSearch(query) {
  setLoading();
  const q = query.q || "";
  const r = await apiGet("/api/search?q=" + encodeURIComponent(q));
  const sec = (title, items, rowFn) => items.length
    ? `<h2>${title} (${items.length})</h2><div class="list">${items.map(rowFn).join("")}</div>` : "";
  const total = r.atoms.length + r.sources.length + r.theses.length + r.projects.length;
  render(`<div class="page-head"><h1>Search</h1><span class="sub">“${esc(q)}”</span></div>
    ${total === 0 ? '<p class="muted">No matches.</p>' : ""}
    ${sec("Atoms", r.atoms, atomCard)}
    ${sec("Sources", r.sources, sourceRow)}
    ${sec("Theses", r.theses, t => `<a class="card" href="#/thesis/${esc(t.id)}">${esc(t.title)} ${statusPill(t.status)}</a>`)}
    ${sec("Projects", r.projects, p => `<a class="card" href="#/project/${esc(p.id)}">${esc(p.title)} ${statusPill(p.status)}</a>`)}`);
}

/* ---------- Atom detail (provenance always present) ---------- */
async function viewAtom(id) {
  setLoading();
  const a = await apiGet("/api/atoms/" + encodeURIComponent(id));
  if (!a || a.error) return errorView("Atom not found.");
  const th = (a.linked_theses || []).map(t =>
    `<li><a href="#/thesis/${esc(t.id)}">${esc(t.title)}</a> <span class="muted">(${esc(t.relation)})</span></li>`).join("");
  const pr = (a.linked_projects || []).map(p =>
    `<li><a href="#/project/${esc(p.id)}">${esc(p.title)}</a></li>`).join("");
  render(`
    <div class="breadcrumb"><a href="#/browse">Browse</a> › Atom</div>
    <div class="page-head">${typeBadge(a.type)}<h1>${esc(a.title)}</h1></div>
    <div class="provenance">
      <div class="lab">Provenance</div>
      From source <a href="#/source/${esc(a.source)}">${esc(a.source_title || a.source)}</a>
      ${a.source_location ? "· located at <strong>" + esc(a.source_location) + "</strong>" : ""}
    </div>
    ${meter("confidence", a.confidence)}
    <div class="card prose" style="margin:16px 0">${renderMarkdown(a.body)}</div>
    ${tagList(a.tags)}
    ${th ? `<h2>Linked theses</h2><ul>${th}</ul>` : ""}
    ${pr ? `<h2>Linked projects</h2><ul>${pr}</ul>` : ""}
    <div class="meta-line" style="margin-top:18px">${esc(a.id)} · created ${esc(a.created)}</div>
    <div class="btn-row" style="margin-top:18px">
      <button class="btn btn-danger" id="del-atom">Delete atom</button></div>`);
  bindDelete("del-atom", {
    title: "Delete atom",
    msg: "Removes this atom and every link to it. This cannot be undone.",
    url: "/api/atoms/" + encodeURIComponent(a.id),
    after: a.source ? "#/source/" + encodeURIComponent(a.source) : "#/browse",
  });
}

/* Wire a danger button to a confirm modal → DELETE → navigate (or show error). */
function bindDelete(btnId, { title, msg, url, after }) {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  btn.addEventListener("click", async () => {
    if (!(await confirmModal(title, msg, "Delete"))) return;
    btn.disabled = true;
    try {
      const res = await apiSend(url, "DELETE");
      if (res && res.error) throw new Error(res.error);
      App.go(after);
    } catch (e) {
      btn.disabled = false;
      appEl().insertAdjacentHTML("afterbegin",
        `<div class="banner banner-error">Delete failed: ${esc(e.message)}</div>`);
    }
  });
}

/* ---------- Source detail (review what was extracted) ---------- */
async function viewSource(id) {
  setLoading();
  const s = await apiGet("/api/sources/" + encodeURIComponent(id));
  if (!s || s.error) return errorView("Source not found.");
  const origin = /^https?:/.test(s.origin || "")
    ? `<a href="${attr(s.origin)}" target="_blank" rel="noopener">${esc(s.origin)}</a>` : esc(s.origin);
  const atoms = s.atoms || [];
  render(`
    <div class="breadcrumb"><a href="#/browse?lens=source">Sources</a> › Source</div>
    <h1>${esc(s.title)}</h1>
    <div class="meta-line">Origin: ${origin || "—"}${s.ingested ? " · ingested " + esc(s.ingested) : ""}</div>
    ${meter("reliability", s.reliability)}
    ${s.reliability_note ? `<p class="muted">${esc(s.reliability_note)}</p>` : ""}
    ${s.summary ? `<p>${esc(s.summary)}</p>` : ""}
    ${tagList(s.tags)}
    <h2>Atoms extracted (${atoms.length})</h2>
    ${atoms.length
      ? `<div class="grid grid-cards">${atoms.map(atomCard).join("")}</div>`
      : `<div class="banner banner-info">No atoms were extracted from this source.
         That's valid — the source is captured, it just produced no reusable units
         (a thin page, or no <code>::atom</code> markers in marker mode).</div>`}
    <details class="advanced" style="margin-top:20px"><summary>Original source text</summary>
      <div class="prose" style="margin-top:10px">${renderMarkdown(s.body)}</div></details>
    <div class="btn-row" style="margin-top:20px">
      <button class="btn btn-danger" id="del-source">Delete source</button></div>`);
  bindDelete("del-source", {
    title: "Delete source",
    msg: `Removes this source and the ${atoms.length} atom(s) extracted from it, `
       + "plus every link to them. This cannot be undone.",
    url: "/api/sources/" + encodeURIComponent(s.id),
    after: "#/browse?lens=source",
  });
}

/* ---------- Theses ---------- */
async function viewTheses() {
  setLoading();
  const list = await apiGet("/api/theses");
  render(`<div class="page-head"><h1>Theses</h1><span class="sub">claims under evaluation</span></div>
    <div class="btn-row"><a class="btn btn-primary" href="#/thesis/new">+ New thesis</a></div>
    <div class="list" style="margin-top:16px">${list.map(t => `
      <a class="card" href="#/thesis/${esc(t.id)}">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:10px">
          <span style="font-weight:600">${esc(t.title)}</span>${statusPill(t.status)}</div>
        ${meter("confidence", t.confidence)}
      </a>`).join("") || '<p class="muted">No theses yet.</p>'}</div>`);
}

async function viewThesis(id) {
  setLoading();
  const t = await apiGet("/api/theses/" + encodeURIComponent(id));
  if (!t || t.error) return errorView("Thesis not found.");
  const col = (items) => items.length
    ? `<div class="list">${items.map(atomRow).join("")}</div>` : '<p class="muted">none</p>';
  render(`
    <div class="breadcrumb"><a href="#/theses">Theses</a> › Thesis</div>
    <div class="page-head"><h1>${esc(t.title)}</h1>${statusPill(t.status)}</div>
    ${meter("confidence", t.confidence)}
    <div class="btn-row"><a class="btn btn-sm" href="#/thesis/${esc(t.id)}/edit">Edit / attach evidence</a></div>
    <div class="card prose" style="margin:16px 0">${renderMarkdown(t.body)}</div>
    <h2>Evidence balance — ${t.supporting.length} for · ${t.contradicting.length} against</h2>
    <div class="evidence">
      <div class="col supporting"><h3>Supporting</h3>${col(t.supporting)}</div>
      <div class="col contradicting"><h3>Contradicting</h3>${col(t.contradicting)}</div>
    </div>`);
}

/* ---------- Projects ---------- */
async function viewProjects() {
  setLoading();
  const list = await apiGet("/api/projects");
  render(`<div class="page-head"><h1>Projects</h1><span class="sub">goal-oriented workspaces</span></div>
    <div class="btn-row"><a class="btn btn-primary" href="#/project/new">+ New project</a></div>
    <div class="list" style="margin-top:16px">${list.map(p => `
      <a class="card" href="#/project/${esc(p.id)}">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:10px">
          <span style="font-weight:600">${esc(p.title)}</span>${statusPill(p.status)}</div>
      </a>`).join("") || '<p class="muted">No projects yet.</p>'}</div>`);
}

async function viewProject(id) {
  setLoading();
  const p = await apiGet("/api/projects/" + encodeURIComponent(id));
  if (!p || p.error) return errorView("Project not found.");
  const atoms = p.atoms || [], theses = p.theses || [];
  render(`
    <div class="breadcrumb"><a href="#/projects">Projects</a> › Project</div>
    <div class="page-head"><h1>${esc(p.title)}</h1>${statusPill(p.status)}</div>
    <div class="btn-row"><a class="btn btn-sm" href="#/project/${esc(p.id)}/edit">Edit</a></div>
    <div class="card prose" style="margin:16px 0">${renderMarkdown(p.body)}</div>
    ${atoms.length ? `<h2>Linked atoms</h2><div class="grid grid-cards">${atoms.map(atomRow).join("")}</div>` : ""}
    ${theses.length ? `<h2>Linked theses</h2><div class="list">${theses.map(t =>
      t.missing ? `<div class="card muted">missing: ${esc(t.id)}</div>`
                : `<a class="card" href="#/thesis/${esc(t.id)}">${esc(t.title)} ${statusPill(t.status)}</a>`).join("")}</div>` : ""}`);
}

/* ---------- Tag view ---------- */
async function viewTag(tag) {
  setLoading();
  const atoms = await apiGet("/api/atoms?tag=" + encodeURIComponent(tag));
  render(`<div class="breadcrumb"><a href="#/tags">Tags</a> › Tag</div>
    <div class="page-head"><h1>#${esc(tag)}</h1><span class="sub">${atoms.length} atom${atoms.length===1?"":"s"}</span></div>
    <div class="grid grid-cards">${atoms.map(atomCard).join("") || '<p class="muted">No atoms with this tag.</p>'}</div>`);
}

async function viewTags() {
  setLoading();
  const tags = await apiGet("/api/tags");
  render(`<h1>Tags</h1><p class="muted">vocabulary · ${tags.length} tags</p>
    <div class="tags">${tags.map(t =>
      `<a class="tag" href="#/tag/${encodeURIComponent(t.tag)}">${esc(t.tag)}<span class="ct">${t.count}</span></a>`).join("")}</div>`);
}

/* ===================================================================== */
/* Add Source                                                            */
/* ===================================================================== */
function guessType(input) {
  if (/youtube\.com|youtu\.be/i.test(input)) return "YouTube transcript";
  if (/\.(xml|rss|atom)(\?|$)/i.test(input) || /\/feed\/?$/i.test(input)) return "RSS/Atom feed → may create many sources";
  if (/^https?:/i.test(input)) return "web page";
  return null;
}
function viewAdd() {
  const exts = (CONFIG.upload_exts || []).join(",");
  const typeOpts = ["", ...(CONFIG.supported_types || [])]
    .map(t => `<option value="${attr(t)}">${t || "auto-detect"}</option>`).join("");
  render(`
    <h1>Add a source</h1>
    <p class="muted">Paste a URL (web page, feed, or YouTube) or upload a file. KOS
       extracts the reusable ideas and traces each back here.</p>
    <form class="form" id="addForm">
      <div class="field">
        <label for="a-input">URL</label>
        <input type="url" id="a-input" placeholder="https://…">
        <span class="hint" id="a-detect"></span>
      </div>
      <div class="field">
        <label for="a-file">…or upload a file</label>
        <input type="file" id="a-file" accept="${attr(exts)}">
        <span class="hint">Supported: ${esc(exts)}</span>
      </div>
      <div class="field">
        <label for="a-tags">Tags</label>
        <input type="text" id="a-tags" placeholder="comma,separated (auto-normalized)">
      </div>
      <div class="row2">
        <div class="field"><label for="a-title">Title override</label>
          <input type="text" id="a-title" placeholder="(optional — inferred)"></div>
        <div class="field"><label for="a-rel">Reliability: <span id="a-rel-v">0.70</span></label>
          <input type="range" id="a-rel" min="0" max="1" step="0.05" value="0.7"></div>
      </div>
      <details class="advanced">
        <summary>Advanced</summary>
        <div class="field" style="margin-top:10px"><label for="a-type">Force type</label>
          <select id="a-type">${typeOpts}</select>
          <span class="hint">Leave on auto-detect unless detection is wrong.</span></div>
        <div class="field inline"><input type="checkbox" id="a-noingest">
          <label for="a-noingest" style="font-weight:400">Scaffold only — write the source but don't extract atoms yet</label></div>
        <div class="field inline"><input type="checkbox" id="a-insecure">
          <label for="a-insecure" style="font-weight:400">Skip TLS certificate check (trusted hosts only)</label></div>
      </details>
      <div class="btn-row">
        <button type="submit" class="btn btn-primary">Add source</button>
        <button type="button" class="btn" id="a-preview">Preview extraction</button>
      </div>
    </form>
    <div id="addResult"></div>`);

  const input = document.getElementById("a-input");
  const detect = document.getElementById("a-detect");
  input.addEventListener("input", () => {
    const g = guessType(input.value.trim());
    detect.textContent = g ? "Detected: " + g : "";
  });
  const rel = document.getElementById("a-rel");
  rel.addEventListener("input", () => document.getElementById("a-rel-v").textContent = (+rel.value).toFixed(2));
  document.getElementById("a-preview").addEventListener("click", previewExtraction);
  document.getElementById("addForm").addEventListener("submit", (e) => { e.preventDefault(); submitAdd(); });
}

async function previewExtraction() {
  const file = document.getElementById("a-file").files[0];
  const out = document.getElementById("addResult");
  if (!file) { out.innerHTML = `<div class="banner banner-info">Preview reads file text. Pick a text file (.md/.txt) to preview without writing anything.</div>`; return; }
  const body = await file.text();
  out.innerHTML = `<p class="muted"><span class="spinner"></span> previewing…</p>`;
  const atoms = await apiSend("/api/preview", "POST", { body });
  out.innerHTML = `<h2>Preview — ${atoms.length} candidate atom${atoms.length===1?"":"s"}</h2>
    <p class="muted">Nothing was written. Submit to actually capture.</p>
    <div class="grid grid-cards">${atoms.map(a => `<div class="card atom-card">
      <div>${typeBadge(a.type)}</div><div class="title">${esc(a.title)}</div>
      <div class="excerpt">${esc(excerpt(a.body))}</div></div>`).join("") || '<p class="muted">No atoms found in this text.</p>'}</div>`;
}

function addSteps(stage) {
  const order = ["queued", "fetching", "writing", "extracting", "done"];
  const labels = { queued: "Queued", fetching: "Fetching", writing: "Writing", extracting: "Extracting", done: "Done" };
  const idx = order.indexOf(stage === "done" ? "done" : stage);
  return `<div class="steps">${order.map((s, i) =>
    `<div class="step ${i<idx?"done":""} ${s===stage?"active":""}">${labels[s]}</div>`).join("")}</div>`;
}

async function submitAdd() {
  const input = document.getElementById("a-input").value.trim();
  const file = document.getElementById("a-file").files[0];
  const tags = document.getElementById("a-tags").value;
  const title = document.getElementById("a-title").value.trim();
  const reliability = parseFloat(document.getElementById("a-rel").value);
  const noIngest = document.getElementById("a-noingest").checked;
  const insecure = document.getElementById("a-insecure").checked;
  const type = document.getElementById("a-type").value;
  const out = document.getElementById("addResult");

  if (!input && !file) { out.innerHTML = `<div class="banner banner-warn">Enter a URL or choose a file.</div>`; return; }

  // Guarded confirmation for the security-sensitive insecure fetch.
  if (insecure && input) {
    const ok = await confirmModal("Skip the security check?",
      `This bypasses TLS verification — the check that proves the site is really
       who it claims to be. Only do this for hosts you trust (e.g. your own
       self-hosted server). Never for the open web.`, "Skip check & fetch");
    if (!ok) return;
  }

  let job;
  if (file) {
    const p = new URLSearchParams({ filename: file.name, tags, reliability: String(reliability) });
    if (title) p.set("title", title);
    if (type) p.set("type", type);
    if (noIngest) p.set("no_ingest", "true");
    job = await api("/api/sources/add?" + p.toString(), { method: "POST", body: file });
  } else {
    job = await apiSend("/api/sources/add", "POST",
      { input, type: type || null, tags, title: title || null, reliability, no_ingest: noIngest, insecure });
  }
  if (job.error) { out.innerHTML = `<div class="banner banner-error">${esc(job.error)}</div>`; return; }
  pollJob(job.job_id, out);
}

async function pollJob(jobId, out) {
  const tick = async () => {
    const j = await apiGet("/api/jobs/" + jobId);
    if (!j) { out.innerHTML = `<div class="banner banner-error">Job lost.</div>`; return; }
    if (j.status === "done") { renderAddResult(j.result, out); return; }
    if (j.status === "error") { renderAddError(j.error, out); return; }
    out.innerHTML = `<h2>Processing…</h2>${addSteps(j.status)}
      <p class="muted"><span class="spinner"></span> ${esc(j.status)} — feeds and video transcripts can take a moment.</p>`;
    setTimeout(tick, 700);
  };
  tick();
}

function renderAddError(msg, out) {
  msg = msg || "Something went wrong.";
  let hint = "";
  if (/yt-dlp/i.test(msg)) hint = "This input type needs the external <code>yt-dlp</code> tool. Install it (<code>pip install yt-dlp</code>) and retry.";
  else if (/certificate|TLS/i.test(msg)) hint = "Certificate problem. For a host you trust, re-try with “Skip TLS certificate check” in Advanced.";
  else if (/unsupported/i.test(msg)) hint = "Try forcing a type under Advanced, or use a supported format.";
  out.innerHTML = `<div class="banner banner-error"><strong>Couldn't add this source.</strong><br>${esc(msg)}</div>
    ${hint ? `<div class="banner banner-info">${hint}</div>` : ""}
    <button class="btn" onclick="App.go('#/add')">Try again</button>`;
}

function renderAddResult(r, out) {
  const sources = r.sources || [];
  const newCount = r.new_count || 0;
  const srcAtoms = r.source_atom_count || 0;
  const extractor = r.extractor || "marker";
  let head;
  if (r.no_ingest) {
    head = `<div class="banner banner-ok">Source scaffolded (not yet extracted).
            Run extraction later, or re-add without “scaffold only”.</div>`;
  } else if (newCount > 0) {
    head = `<div class="banner banner-ok"><strong>Captured.</strong>
            ${sources.length} source${sources.length===1?"":"s"} · ${newCount} new atom${newCount===1?"":"s"}.</div>`;
  } else if (srcAtoms > 0) {
    // Source already in the store with atoms; re-ingest minted nothing new.
    head = `<div class="banner banner-info"><strong>Already captured.</strong>
            Nothing new — this content is already in your knowledge base (idempotent by design).</div>`;
  } else {
    // Source written, but the extractor produced zero atoms from it.
    const hint = extractor === "marker"
      ? `Marker mode found no <code>::atom</code> blocks in this source. Add <code>::atom</code> blocks to it, or switch to LLM extraction (<code>config/extractor.json</code> → <code>"extractor":"llm"</code>) to mint atoms from raw prose.`
      : `The <code>${esc(extractor)}</code> extractor returned no atoms for this source. The content may be too thin, or extraction failed — check the ingest logs.`;
    head = `<div class="banner banner-warn"><strong>Source saved — but no atoms extracted.</strong><br>${hint}</div>`;
  }
  const srcLinks = sources.map(s =>
    `<a class="card" href="#/source/${esc(s.id)}">${esc(s.title)}</a>`).join("");
  const skipped = (r.empty_skipped || []).length
    ? `<div class="banner banner-warn">Skipped ${r.empty_skipped.length} input(s) with empty text:
       ${r.empty_skipped.map(esc).join(", ")}.</div>` : "";
  out.innerHTML = `${head}${skipped}
    ${sources.length ? `<h2>Source${sources.length===1?"":"s"}</h2><div class="list">${srcLinks}</div>` : ""}
    ${(r.new_atoms||[]).length ? `<h2>New atoms</h2><div class="grid grid-cards">${r.new_atoms.map(atomCard).join("")}</div>` : ""}`;
}

/* ===================================================================== */
/* Curation forms — thesis / project                                     */
/* ===================================================================== */
function atomPicker(idPrefix, label, initial) {
  // returns html; state lives on a dataset on the hidden container
  return `<div class="field">
    <label>${esc(label)}</label>
    <div class="chips" id="${idPrefix}-chips"></div>
    <input type="search" id="${idPrefix}-search" placeholder="search atoms by title/tag to attach…">
    <div class="picker-results" id="${idPrefix}-results" style="display:none"></div>
  </div>`;
}
function wirePicker(idPrefix, initial, kind) {
  const chips = document.getElementById(idPrefix + "-chips");
  const search = document.getElementById(idPrefix + "-search");
  const results = document.getElementById(idPrefix + "-results");
  let selected = (initial || []).slice();
  const draw = () => {
    chips.innerHTML = selected.map(id =>
      `<span class="chip">${esc(id)}<button type="button" data-id="${attr(id)}">×</button></span>`).join("");
  };
  chips.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-id]"); if (!b) return;
    selected = selected.filter(x => x !== b.dataset.id); draw();
  });
  let timer;
  search.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      const q = search.value.trim();
      if (!q) { results.style.display = "none"; return; }
      const ep = kind === "thesis" ? "/api/theses" : "/api/atoms?q=" + encodeURIComponent(q);
      let items = await apiGet(ep);
      if (kind === "thesis") items = items.filter(t => (t.title||"").toLowerCase().includes(q.toLowerCase()));
      results.innerHTML = items.slice(0, 20).map(it =>
        `<div class="opt" data-id="${attr(it.id)}">${esc(it.title)} <span class="muted">${esc(it.id)}</span></div>`).join("")
        || `<div class="opt muted">no matches</div>`;
      results.style.display = "block";
    }, 250);
  });
  results.addEventListener("click", (e) => {
    const o = e.target.closest(".opt[data-id]"); if (!o) return;
    if (!selected.includes(o.dataset.id)) selected.push(o.dataset.id);
    draw(); search.value = ""; results.style.display = "none";
  });
  draw();
  return () => selected;
}

async function viewThesisForm(id) {
  setLoading();
  let t = { title: "", status: "active", confidence: "0.5", statement: "", reasoning: "",
            supporting_atoms: [], contradicting_atoms: [] };
  if (id) {
    const got = await apiGet("/api/theses/" + encodeURIComponent(id));
    if (!got || got.error) return errorView("Thesis not found.");
    t = got;
    const parsed = parseSections(got.body, ["Thesis Statement", "Reasoning"]);
    t.statement = parsed["Thesis Statement"] || "";
    t.reasoning = parsed["Reasoning"] || "";
  }
  const statuses = CONFIG.thesis_statuses || ["active"];
  render(`<h1>${id ? "Edit" : "New"} thesis</h1>
    <form class="form" id="thForm">
      <div class="field"><label>Title (the claim, one line)</label>
        <input type="text" id="th-title" value="${attr(t.title)}" required></div>
      <div class="row2">
        <div class="field"><label>Status</label><select id="th-status">
          ${statuses.map(s=>`<option ${t.status===s?"selected":""}>${esc(s)}</option>`).join("")}</select></div>
        <div class="field"><label>Confidence: <span id="th-conf-v">${num(t.confidence)??0.5}</span></label>
          <input type="range" id="th-conf" min="0" max="1" step="0.05" value="${num(t.confidence)??0.5}"></div>
      </div>
      <div class="field"><label>Thesis statement</label>
        <textarea id="th-statement">${esc(t.statement)}</textarea></div>
      <div class="field"><label>Reasoning</label>
        <textarea id="th-reasoning">${esc(t.reasoning)}</textarea></div>
      ${atomPicker("th-sup", "Supporting atoms", t.supporting_atoms)}
      ${atomPicker("th-con", "Contradicting atoms", t.contradicting_atoms)}
      <div class="btn-row"><button class="btn btn-primary" type="submit">${id?"Save":"Create"} thesis</button>
        <a class="btn" href="${id?"#/thesis/"+id:"#/theses"}">Cancel</a></div>
    </form>`);
  const conf = document.getElementById("th-conf");
  conf.addEventListener("input", () => document.getElementById("th-conf-v").textContent = (+conf.value).toFixed(2));
  const getSup = wirePicker("th-sup", t.supporting_atoms, "atom");
  const getCon = wirePicker("th-con", t.contradicting_atoms, "atom");
  document.getElementById("thForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = {
      title: document.getElementById("th-title").value.trim(),
      status: document.getElementById("th-status").value,
      confidence: document.getElementById("th-conf").value,
      statement: document.getElementById("th-statement").value,
      reasoning: document.getElementById("th-reasoning").value,
      supporting_atoms: getSup(), contradicting_atoms: getCon(),
    };
    const r = id ? await apiSend("/api/theses/" + id, "PUT", body)
                 : await apiSend("/api/theses", "POST", body);
    if (r.error) { alert(r.error); return; }
    App.go("#/thesis/" + r.id);
  });
}

async function viewProjectForm(id) {
  setLoading();
  let p = { title: "", status: "active", objective: "", linked_atoms: [], linked_theses: [],
            open_questions: [], decisions: [], deliverables: [] };
  if (id) {
    const got = await apiGet("/api/projects/" + encodeURIComponent(id));
    if (!got || got.error) return errorView("Project not found.");
    p = got;
    const parsed = parseSections(got.body, ["Objective", "Open Questions", "Decisions", "Deliverables"]);
    p.objective = parsed["Objective"] || "";
    p.open_questions = bulletLines(parsed["Open Questions"]);
    p.decisions = bulletLines(parsed["Decisions"]);
    p.deliverables = bulletLines(parsed["Deliverables"]);
    p.linked_atoms = (got.atoms || []).map(a => a.id);
    p.linked_theses = (got.theses || []).map(t => t.id);
  }
  const statuses = CONFIG.project_statuses || ["active"];
  render(`<h1>${id ? "Edit" : "New"} project</h1>
    <form class="form" id="prForm">
      <div class="field"><label>Title</label>
        <input type="text" id="pr-title" value="${attr(p.title)}" required></div>
      <div class="field"><label>Status</label><select id="pr-status">
        ${statuses.map(s=>`<option ${p.status===s?"selected":""}>${esc(s)}</option>`).join("")}</select></div>
      <div class="field"><label>Objective</label>
        <textarea id="pr-objective">${esc(p.objective)}</textarea></div>
      ${atomPicker("pr-atoms", "Linked atoms", p.linked_atoms)}
      ${atomPicker("pr-theses", "Linked theses", p.linked_theses)}
      <div class="field"><label>Open questions (one per line)</label>
        <textarea id="pr-questions">${esc((p.open_questions||[]).join("\n"))}</textarea></div>
      <div class="field"><label>Decisions (one per line)</label>
        <textarea id="pr-decisions">${esc((p.decisions||[]).join("\n"))}</textarea></div>
      <div class="field"><label>Deliverables (one per line)</label>
        <textarea id="pr-deliverables">${esc((p.deliverables||[]).join("\n"))}</textarea></div>
      <div class="btn-row"><button class="btn btn-primary" type="submit">${id?"Save":"Create"} project</button>
        <a class="btn" href="${id?"#/project/"+id:"#/projects"}">Cancel</a></div>
    </form>`);
  const getAtoms = wirePicker("pr-atoms", p.linked_atoms, "atom");
  const getTheses = wirePicker("pr-theses", p.linked_theses, "thesis");
  document.getElementById("prForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const lines = (elId) => document.getElementById(elId).value.split("\n").map(s=>s.trim()).filter(Boolean);
    const body = {
      title: document.getElementById("pr-title").value.trim(),
      status: document.getElementById("pr-status").value,
      objective: document.getElementById("pr-objective").value,
      linked_atoms: getAtoms(), linked_theses: getTheses(),
      open_questions: lines("pr-questions"), decisions: lines("pr-decisions"),
      deliverables: lines("pr-deliverables"),
    };
    const r = id ? await apiSend("/api/projects/" + id, "PUT", body)
                 : await apiSend("/api/projects", "POST", body);
    if (r.error) { alert(r.error); return; }
    App.go("#/project/" + r.id);
  });
}

/* parse "## Section" blocks out of a markdown body */
function parseSections(body, names) {
  const out = {};
  const re = /^##\s+(.+)$/gm;
  const marks = [];
  let m;
  while ((m = re.exec(body))) marks.push({ name: m[1].trim(), start: m.index + m[0].length, head: m.index });
  marks.forEach((mk, i) => {
    const end = i + 1 < marks.length ? marks[i + 1].head : body.length;
    out[mk.name] = body.slice(mk.start, end).trim();
  });
  return out;
}
function bulletLines(text) {
  if (!text) return [];
  return text.split("\n").map(l => l.replace(/^\s*[-*]\s*(\[[ xX]\]\s*)?/, "").trim())
    .filter(l => l && l !== "TODO");
}

/* ---------- modal ---------- */
function confirmModal(title, msg, okLabel) {
  return new Promise((resolve) => {
    const root = document.getElementById("modal-root");
    root.innerHTML = `<div class="modal-overlay"><div class="modal">
      <h2>${esc(title)}</h2>
      <div class="banner banner-warn">${msg}</div>
      <div class="btn-row"><button class="btn btn-danger" id="m-ok">${esc(okLabel)}</button>
        <button class="btn" id="m-cancel">Cancel</button></div></div></div>`;
    const close = (v) => { root.innerHTML = ""; resolve(v); };
    document.getElementById("m-ok").addEventListener("click", () => close(true));
    document.getElementById("m-cancel").addEventListener("click", () => close(false));
  });
}

/* ===================================================================== */
/* Router                                                                */
/* ===================================================================== */
function parseHash() {
  const raw = location.hash.replace(/^#/, "") || "/";
  const [path, qs] = raw.split("?");
  const query = {};
  new URLSearchParams(qs || "").forEach((v, k) => query[k] = v);
  return { parts: path.split("/").filter(Boolean), query };
}

async function route() {
  const { parts, query } = parseHash();
  try {
    if (parts.length === 0) return viewDashboard();
    switch (parts[0]) {
      case "add": return viewAdd();
      case "browse": return viewBrowse(query);
      case "search": return viewSearch(query);
      case "tags": return viewTags();
      case "tag": return viewTag(decodeURIComponent(parts[1]));
      case "atom": return viewAtom(parts[1]);
      case "source": return viewSource(parts[1]);
      case "theses": return viewTheses();
      case "projects": return viewProjects();
      case "thesis":
        if (parts[1] === "new") return viewThesisForm(null);
        if (parts[2] === "edit") return viewThesisForm(parts[1]);
        return viewThesis(parts[1]);
      case "project":
        if (parts[1] === "new") return viewProjectForm(null);
        if (parts[2] === "edit") return viewProjectForm(parts[1]);
        return viewProject(parts[1]);
    }
    errorView("Page not found: " + location.hash);
  } catch (e) {
    errorView("Error: " + e.message);
  }
}

App.go = (hash) => { if (location.hash === hash) route(); else location.hash = hash; };

window.addEventListener("hashchange", route);
document.getElementById("searchForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const q = document.getElementById("searchInput").value.trim();
  if (q) App.go("#/search?q=" + encodeURIComponent(q));
});

(async function init() {
  try {
    CONFIG = await apiGet("/api/config");
  } catch (e) {
    errorView("Cannot reach the KOS server. Is scripts/serve.py running?");
    return;
  }
  route();
})();
