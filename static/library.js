// Zotero-style library. Runs after site.js, which supplies $, esc, sb, flash, FORMATS and exportBar.
window.addEventListener("load", async () => {
  const {data: sess} = await sb.auth.getSession();
  if (!sess.session) return location.href = "/login";

  let cols = [], papers = [], col = "", cur = null, q = "", tab = "info", del = false;
  const tagSel = new Set(), sort = {k: "title", d: 1};
  const zNames = a => (a || "").split(";").map(x => x.trim()).filter(Boolean);
  const lastOf = n => (n.includes(",") ? n.split(",")[0] : n.split(/\s+/).pop()).trim();
  const creator = p => { const L = zNames(p.authors).map(lastOf); return L.length > 2 ? L[0] + " et al." : L.join(" and "); };
  const tagsOf = p => (p.tags || "").split(/[,;]/).map(t => t.trim()).filter(Boolean);
  const KEY = {title: p => p.title.toLowerCase(), creator: p => creator(p).toLowerCase(), date: p => p.year || 0, cites: p => p.citations || 0};

  // ---------- file parsers: CSV (Zotero and Publish or Perish), RIS, BibTeX, JSON ----------
  function recFromObj(o) {
    const g = (...ks) => { for (const k of ks) { const v = o[k]; if (v != null && String(v).trim()) return String(v).trim(); } return ""; };
    const A = g("authors", "author", "creators");
    const list = /\sand\s/i.test(A) ? A.split(/\s+and\s+/i) : ("cites" in o || "articleurl" in o) ? A.split(",") : A.split(";");
    const y = (g("year", "publication year", "date").match(/\d{4}/) || [])[0];
    return {
      title: g("title", "article title"),
      authors: list.map(s => s.trim()).filter(Boolean).join("; "),
      year: y ? +y : null,
      venue: g("source", "publication title", "journal", "booktitle", "venue", "publisher"),
      doi: g("doi").replace(/^https?:\/\/(dx\.)?doi\.org\//i, ""),
      url: g("articleurl", "url", "link"),
      abstract: g("abstract", "abstract note"),
      citations: parseInt(g("cites", "citations", "ecc")) || 0,
      tags: g("manual tags", "tags", "keywords").replace(/;/g, ","),
      notes: g("notes", "note")
    };
  }
  function parseCSV(t) {
    const rows = []; let r = [], f = "", inq = false;
    for (let i = 0; i < t.length; i++) {
      const c = t[i];
      if (inq) { if (c === '"') { if (t[i + 1] === '"') { f += '"'; i++; } else inq = false; } else f += c; }
      else if (c === '"') inq = true;
      else if (c === ",") { r.push(f); f = ""; }
      else if (c === "\n" || c === "\r") { if (c === "\r" && t[i + 1] === "\n") i++; r.push(f); f = ""; rows.push(r); r = []; }
      else f += c;
    }
    if (f !== "" || r.length) { r.push(f); rows.push(r); }
    return rows;
  }
  function parseRIS(t) {
    const out = []; let o = null;
    t.split(/\r?\n/).forEach(line => {
      const m = line.match(/^([A-Z][A-Z0-9])  - ?(.*)$/); if (!m) return;
      const k = m[1], v = m[2].trim();
      if (k === "TY") { o = {au: [], kw: []}; return; }
      if (!o) return;
      if (k === "ER") { out.push(recFromObj({title: o.ti, author: o.au.join("; "), year: o.py, journal: o.jo, doi: o.do, url: o.ur, abstract: o.ab, keywords: o.kw.join(", "), notes: o.n1})); o = null; return; }
      if (k === "AU" || k === "A1") o.au.push(v);
      else if (k === "KW") o.kw.push(v);
      else { const key = {TI: "ti", T1: "ti", PY: "py", Y1: "py", DA: "py", JO: "jo", JF: "jo", T2: "jo", DO: "do", UR: "ur", AB: "ab", N2: "ab", N1: "n1"}[k]; if (key && !o[key]) o[key] = v; }
    });
    return out;
  }
  function parseBib(t) {
    const out = [];
    t.split(/^@/m).slice(1).forEach(chunk => {
      if (/^(comment|string|preamble)/i.test(chunk)) return;
      const o = {}, re = /(\w+)\s*=\s*(\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}|"[^"]*"|[^,\n}]+)/g; let m;
      while ((m = re.exec(chunk))) {
        let v = m[2].trim(); if (v[0] === "{" || v[0] === '"') v = v.slice(1, -1);
        o[m[1].toLowerCase()] = v.replace(/[{}]/g, "").replace(/\s+/g, " ").trim();
      }
      out.push(recFromObj(o));
    });
    return out;
  }
  function parseFile(text) {
    const s = text.trim();
    if (s[0] === "[" || s[0] === "{") return [].concat(JSON.parse(s)).map(o => recFromObj(Object.fromEntries(Object.entries(o).map(([k, v]) => [k.toLowerCase(), Array.isArray(v) ? v.join(", ") : v]))));
    if (/^TY  - /m.test(s)) return parseRIS(s);
    if (s[0] === "@") return parseBib(s);
    const rows = parseCSV(s); if (rows.length < 2) return [];
    const h = rows[0].map(x => x.trim().toLowerCase());
    return rows.slice(1).filter(r => r.some(c => c.trim())).map(r => recFromObj(Object.fromEntries(h.map((k, i) => [k, r[i]]))));
  }

  // ---------- load and import ----------
  async function load() {
    const out = [];
    for (let from = 0; ; from += 1000) {   // the database returns 1,000 rows at a time
      const {data, error} = await sb.from("papers").select("*").order("created_at").order("id").range(from, from + 999);
      if (error) { flash(error.message); break; }
      out.push(...data); if (data.length < 1000) break;
    }
    papers = out;
    const c = await sb.from("collections").select("*").order("name"); cols = c.data || [];
    if (cur) cur = papers.find(p => p.id === cur.id) || null;
    draw();
  }
  async function importRecs(name, recs) {
    const have = new Set(papers.map(p => p.title.toLowerCase())), fresh = [];
    recs.forEach(r => { const k = r.title.toLowerCase(); if (r.title && !have.has(k)) { have.add(k); fresh.push(r); } });
    if (!fresh.length) return flash("Nothing new: every paper in that file is already in your library.");
    let target = cols.find(c => c.name === name);
    if (!target) {
      const {data, error} = await sb.from("collections").insert({name}).select().single();
      if (error) return flash(error.message);
      target = data;
    }
    for (let i = 0; i < fresh.length; i += 200) {
      flash(`Importing ${Math.min(i + 200, fresh.length)} of ${fresh.length}…`);
      const {error} = await sb.from("papers").insert(fresh.slice(i, i + 200).map(r => ({...r, collection_id: target.id})));
      if (error) return flash(error.message);
    }
    col = target.id; await load();
    flash(`Imported ${fresh.length} papers into “${name}”. Skipped ${recs.length - fresh.length}.`);
  }
  async function handleFile(f) {
    if (!f) return;
    try {
      const recs = parseFile((await f.text()).replace(/^\uFEFF/, ""));
      if (!recs.length) return flash("No papers found. Use a CSV, RIS, BibTeX or JSON file.");
      await importRecs(f.name.replace(/\.[^.]+$/, ""), recs);
    } catch (err) { flash("Import failed: " + err.message); }
  }
  async function patch(p, v) {
    const {error} = await sb.from("papers").update(v).eq("id", p.id);
    if (error) return flash(error.message);
    Object.assign(p, v); flash("Saved"); draw();
  }

  // ---------- drawing ----------
  const view = () => {
    const s = q.toLowerCase();
    const L = papers.filter(p => (!col || p.collection_id === col) && [...tagSel].every(t => tagsOf(p).includes(t)) && (!s || [p.title, p.authors, p.year, p.tags, p.notes].join(" ").toLowerCase().includes(s)));
    const f = KEY[sort.k];
    return L.sort((a, b) => (f(a) > f(b) ? 1 : f(a) < f(b) ? -1 : 0) * sort.d);
  };
  function draw() {
    const inCol = id => papers.filter(p => p.collection_id === id).length;
    $("#zcols").innerHTML = [["", "My Library", papers.length]].concat(cols.map(c => [c.id, c.name, inCol(c.id)])).map(x => `<button class="ci ${col === x[0] ? "on" : ""}" data-col="${x[0]}"><span>${esc(x[1])}</span><span>${x[2]}</span></button>`).join("");
    const tc = {}; papers.filter(p => !col || p.collection_id === col).forEach(p => tagsOf(p).forEach(t => tc[t] = (tc[t] || 0) + 1));
    const tf = $("#ztf").value.toLowerCase();
    $("#ztl").innerHTML = Object.keys(tc).filter(t => t.toLowerCase().includes(tf)).sort().slice(0, 150).map(t => `<button class="tg ${tagSel.has(t) ? "on" : ""}" data-tag="${esc(t)}">${esc(t)}</button>`).join("") || '<span class="mu">No tags</span>';
    const L = view();
    $("#zn").textContent = L.length + " items";
    const th = (k, l) => `<th data-th="${k}">${l}${sort.k === k ? (sort.d > 0 ? " ▲" : " ▼") : ""}</th>`;
    $("#zt").innerHTML = `<thead><tr>${th("title", "Title")}${th("creator", "Creator")}${th("date", "Date")}${th("cites", "Cites")}</tr></thead><tbody>` +
      L.map(p => `<tr data-id="${p.id}" tabindex="0" class="${cur && cur.id === p.id ? "on" : ""}"><td><i class="ic"></i>${esc(p.title)}</td><td>${esc(creator(p))}</td><td>${p.year || ""}</td><td>${p.citations || ""}</td></tr>`).join("") + "</tbody>";
    drawDetail();
  }
  function drawDetail() {
    const p = cur, box = $("#zd");
    if (!p) { box.innerHTML = '<p class="mu pad">Select an item to see its details. Use Import file to add a CSV, RIS or BibTeX export.</p>'; return; }
    const tabs = ["info", "notes", "tags"].map(t => `<button class="tb ${tab === t ? "on" : ""}" data-t="${t}">${t[0].toUpperCase() + t.slice(1)}</button>`).join("");
    let body;
    if (tab === "info") {
      const row = (l, v) => v ? `<div class="fr"><span>${l}</span><div>${v}</div></div>` : "";
      const A = zNames(p.authors);
      body = row("Title", esc(p.title)) + A.slice(0, 30).map(a => row("Author", esc(a))).join("") + (A.length > 30 ? row("", `and ${A.length - 30} more`) : "")
        + row("Date", p.year || "") + row("Publication", esc(p.venue))
        + row("DOI", p.doi ? `<a href="https://doi.org/${esc(p.doi)}" target="_blank" rel="noopener">${esc(p.doi)}</a>` : "")
        + row("URL", /^https?:\/\//i.test(p.url) ? `<a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.url)}</a>` : "")
        + row("Cited by", p.citations ? p.citations.toLocaleString() : "")
        + `<div class="fr"><span>Collection</span><div><select id="dc" aria-label="Collection"><option value="">None</option>${cols.map(c => `<option value="${c.id}" ${c.id === p.collection_id ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select></div></div>`
        + `<h4>Abstract</h4><p class="ab">${p.abstract ? esc(p.abstract) : '<span class="mu">No abstract.</span>'}</p>`
        + `<div class="pad"><button class="zb" id="ddel">${del ? "Click again to delete" : "Remove from library"}</button></div>`;
    } else if (tab === "notes") {
      body = `<div class="pad"><textarea id="dn" rows="16" aria-label="Notes">${esc(p.notes)}</textarea><button class="zb" id="dsave">Save note</button></div>`;
    } else {
      body = `<div class="pad"><input id="dt" value="${esc(p.tags)}" placeholder="Separate tags with commas" aria-label="Tags"><div class="chips">${tagsOf(p).map(t => `<span class="chip">${esc(t)}</span>`).join("")}</div><button class="zb" id="dsave">Save tags</button></div>`;
    }
    box.innerHTML = `<div class="tabs">${tabs}</div><div class="dbody">${body}</div>`;
    const dc = $("#dc"); if (dc) dc.onchange = () => patch(p, {collection_id: dc.value || null});
    const sv = $("#dsave"); if (sv) sv.onclick = () => patch(p, tab === "notes" ? {notes: $("#dn").value} : {tags: $("#dt").value.trim()});
    const dd = $("#ddel"); if (dd) dd.onclick = async () => {
      if (!del) { del = true; return drawDetail(); }
      await sb.from("papers").delete().eq("id", p.id); papers = papers.filter(x => x.id !== p.id); cur = null; del = false; draw();
    };
  }

  // ---------- events ----------
  const zw = $("#zw");
  zw.addEventListener("click", e => {
    const t = e.target.closest("[data-col],[data-th],[data-tag],[data-t],tr[data-id]");
    if (!t) return;
    del = false;
    if (t.dataset.col !== undefined) col = t.dataset.col;
    else if (t.dataset.th) { sort.d = sort.k === t.dataset.th ? -sort.d : 1; sort.k = t.dataset.th; }
    else if (t.dataset.tag) { tagSel.has(t.dataset.tag) ? tagSel.delete(t.dataset.tag) : tagSel.add(t.dataset.tag); }
    else if (t.dataset.t) tab = t.dataset.t;
    else { cur = papers.find(p => p.id === t.dataset.id); tab = "info"; }
    draw();
  });
  zw.addEventListener("keydown", e => { if ((e.key === "Enter" || e.key === " ") && e.target.matches("tr[data-id]")) { e.preventDefault(); e.target.click(); } });
  zw.addEventListener("dragover", e => e.preventDefault());
  zw.addEventListener("drop", e => { e.preventDefault(); handleFile(e.dataTransfer.files[0]); });
  $("#zimp").onclick = () => $("#zfile").click();
  $("#zfile").onchange = e => { handleFile(e.target.files[0]); e.target.value = ""; };
  $("#zq").addEventListener("input", e => { q = e.target.value.trim(); draw(); });
  $("#ztf").addEventListener("input", draw);
  $("#zadd").onclick = async () => {
    const name = (prompt("Collection name") || "").trim(); if (!name) return;
    const {error} = await sb.from("collections").insert({name}); if (error) return flash(error.message);
    load();
  };
  exportBar($("#zexp"), view);
  load();
});