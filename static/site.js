const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

// Keep only the origin of the Supabase URL, so a trailing slash or extra path can't break requests.
let SB_ORIGIN = "";
try { SB_ORIGIN = new URL(CFG.url).origin; } catch (e) {}
const urlOk = /^https:\/\/[a-z0-9]+\.supabase\.co$/.test(SB_ORIGIN);
const sb = supabase.createClient(urlOk ? SB_ORIGIN : "https://invalid.supabase.co", CFG.key);

const NOW = new Date().getFullYear();
const names = a => (a || "").split(";").map(x => x.trim()).filter(Boolean);
const lastName = a => ((names(a)[0] || "anon").split(" ").pop().replace(/[^A-Za-z]/g, "") || "anon");
const short = a => { const n = names(a); return n.length > 2 ? n[0] + " et al." : n.join(", ") || "Unknown"; };
function flash(t) { const f = $("#flash"); f.textContent = t; f.hidden = false; clearTimeout(flash.t); flash.t = setTimeout(() => f.hidden = true, 4500); }

// Export formats: CSV, BibTeX, RIS (opens in Zotero, EndNote, Mendeley) and a DOI list.
const FORMATS = {
  CSV: {ext: "csv", fn: L => "Title,Authors,Year,Venue,DOI,Citations,URL\n" + L.map(p => [p.title, p.authors, p.year, p.venue, p.doi, p.citations, p.url].map(v => '"' + String(v == null ? "" : v).replace(/"/g, '""') + '"').join(",")).join("\n")},
  BibTeX: {ext: "bib", fn: L => L.map((p, i) => `@article{${lastName(p.authors).toLowerCase()}${p.year || ""}${String.fromCharCode(97 + i % 26)},\n  title = {${p.title}},\n  author = {${names(p.authors).join(" and ")}},\n  year = {${p.year || ""}},\n  journal = {${p.venue || ""}},\n  doi = {${p.doi || ""}}\n}`).join("\n\n")},
  RIS: {ext: "ris", fn: L => L.map(p => ["TY  - JOUR", ...names(p.authors).map(a => "AU  - " + a), "TI  - " + p.title, "PY  - " + (p.year || ""), "JO  - " + (p.venue || ""), "DO  - " + (p.doi || ""), "UR  - " + (p.url || ""), "AB  - " + (p.abstract || ""), "ER  - "].join("\n")).join("\n\n")},
  DOIs: {ext: "txt", fn: L => L.filter(p => p.doi).map(p => "https://doi.org/" + p.doi).join("\n")}
};
function exportBar(el, getList) {
  el.innerHTML = Object.keys(FORMATS).map(k => `<button class="btn alt" data-fmt="${k}">${k}</button>`).join("");
  el.onclick = e => {
    const k = e.target.dataset.fmt, L = k && getList();
    if (!k) return;
    if (!L.length) return flash("Nothing to export yet.");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([FORMATS[k].fn(L)], {type: "text/plain"}));
    a.download = "papers." + FORMATS[k].ext; a.click(); URL.revokeObjectURL(a.href);
  };
}

let user = null;
(async function boot() {
  if (!urlOk) flash("Fix SUPABASE_URL in config.py. It should look like https://abcdefgh.supabase.co, with nothing after .co");
  const {data} = await sb.auth.getSession();
  user = data.session ? data.session.user : null;
  const who = user ? ((user.user_metadata && user.user_metadata.full_name) || user.email) : "";
  $("#acct").innerHTML = user ? `<span>${esc(who)}</span><button class="btn alt" id="out">Log out</button>` : '<a class="btn" href="/login">Log in</a> <a class="btn alt" href="/login#signup">Sign up</a>';
  if (user) $("#out").onclick = async () => { await sb.auth.signOut(); location.href = "/login"; };
  const pg = document.body.dataset.page;
  if (pg === "login") login();
  if (pg === "literature") literature();
  if (pg === "mylib") mylib();
})();

function login() {
  const go = async mode => {
    const creds = {email: $("#em").value.trim(), password: $("#pw").value};
    if (mode === "up") creds.options = {data: {full_name: $("#nm").value.trim()}};
    const {data, error} = await (mode === "in" ? sb.auth.signInWithPassword(creds) : sb.auth.signUp(creds));
    if (error) return flash(error.message);
    if (mode === "up" && !data.session) return flash("Account created. Confirm it from the email we sent, then log in.");
    location.href = "/my-library";
  };
  $("#in").onclick = () => go("in"); $("#up").onclick = () => go("up");
}

function literature() {
  let rows = [];
  $("#to").value = NOW;
  const sel = () => $$(".pick:checked").map(c => rows[+c.value]);
  exportBar($("#exp"), () => sel().length ? sel() : rows);
  function draw() {
    const c = rows.map(p => p.citations).sort((a, b) => b - a), tot = c.reduce((s, v) => s + v, 0);
    let h = 0, g = 0, run = 0;
    c.forEach((v, i) => { if (v >= i + 1) h = i + 1; run += v; if (run >= (i + 1) ** 2) g = i + 1; });
    const ys = rows.map(p => p.year).filter(Boolean), span = ys.length ? NOW - Math.min(...ys) + 1 : 1;
    const auth = rows.reduce((s, p) => s + names(p.authors).length, 0);
    const m = [["Papers", rows.length], ["Citations", tot.toLocaleString()], ["Cites/paper", (tot / (rows.length || 1)).toFixed(1)], ["Cites/year", (tot / span).toFixed(1)], ["h-index", h], ["g-index", g], ["Authors/paper", (auth / (rows.length || 1)).toFixed(1)]];
    $("#metrics").innerHTML = rows.length ? m.map(x => `<div><b>${x[1]}</b><span>${x[0]}</span></div>`).join("") : "";
    $("#tbl").innerHTML = rows.length ? '<tr><th><input type="checkbox" id="all" aria-label="Select all"></th><th>#</th><th>Cites</th><th>Per year</th><th>Authors</th><th>Title</th><th>Year</th><th>Source</th></tr>' + rows.map((p, i) => `<tr><td><input type="checkbox" class="pick" value="${i}" aria-label="Select paper ${i + 1}"></td><td class="num">${i + 1}</td><td class="num">${p.citations}</td><td class="num">${(p.citations / Math.max(1, NOW - (p.year || NOW) + 1)).toFixed(1)}</td><td>${esc(short(p.authors))}</td><td>${p.url ? `<a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.title)}</a>` : esc(p.title)}</td><td>${p.year || ""}</td><td>${esc(p.venue)}</td></tr>`).join("") : "";
    const all = $("#all"); if (all) all.onchange = () => $$(".pick").forEach(c => c.checked = all.checked);
  }
  $("#go").onclick = async () => {
    const q = $("#q").value.trim(), b = $("#go");
    if (!q) return flash("Enter keywords first.");
    b.disabled = true; b.textContent = "Searching…"; $("#st").textContent = "Pulling papers. 1,000 results can take about 30 seconds.";
    try {
      const p = new URLSearchParams({q, from: $("#from").value, to: $("#to").value, n: $("#n").value, sort: $("#sort").value});
      const r = await fetch("/api/literature?" + p), d = await r.json();
      if (!r.ok) throw new Error(d.error || "Search failed.");
      rows = d.results; $("#st").textContent = `${rows.length} papers retrieved from ${d.total.toLocaleString()} matches.`; draw();
    } catch (e) { $("#st").innerHTML = `<span class="err">${esc(e.message)}</span>`; }
    b.disabled = false; b.textContent = "Search";
  };
  $("#save").onclick = async () => {
    if (!user) return location.href = "/login";
    const L = sel(); if (!L.length) return flash("Tick the papers you want to save.");
    const {error} = await sb.from("papers").insert(L.map(p => ({title: p.title, authors: p.authors, year: p.year || null, venue: p.venue, doi: p.doi, url: p.url, abstract: p.abstract, citations: p.citations})));
    flash(error ? error.message : L.length + " papers saved to your library.");
  };
}

async function mylib() {
  if (!user) { await new Promise(r => setTimeout(r, 400)); if (!user) return location.href = "/login"; }
  let cols = [], papers = [], col = "", cur = null, q = "", del = null;
  const shown = () => papers.filter(p => (!col || p.collection_id === col) && (!q || [p.title, p.authors, p.tags, p.notes].join(" ").toLowerCase().includes(q)));
  exportBar($("#zexp"), shown);
  async function load() {
    const [a, b] = await Promise.all([sb.from("collections").select("*").order("name"), sb.from("papers").select("*").order("created_at", {ascending: false})]);
    cols = a.data || []; papers = b.data || []; draw();
  }
  function draw() {
    const cnt = id => papers.filter(p => p.collection_id === id).length, L = shown();
    $("#zc").innerHTML = [["", "All papers", papers.length]].concat(cols.map(c => [c.id, c.name, cnt(c.id)])).map(x => `<button class="coll ${col === x[0] ? "on" : ""}" data-col="${x[0]}"><span>${esc(x[1])}</span><span>${x[2]}</span></button>`).join("");
    $("#zn").textContent = papers.length ? `${L.length} of ${papers.length} papers` : "Your library is empty. Save papers from the Literature page.";
    $("#zt").innerHTML = L.length ? "<tr><th>Title</th><th>Authors</th><th>Year</th><th>Cites</th></tr>" + L.map(p => `<tr data-i="${p.id}" class="${cur && cur.id === p.id ? "on" : ""}"><td>${esc(p.title)}</td><td>${esc(short(p.authors))}</td><td>${p.year || ""}</td><td class="num">${p.citations}</td></tr>`).join("") : "";
    drawDetail();
  }
  function drawDetail() {
    const p = cur; if (!p) return;
    $("#zd").innerHTML = `<h3>${esc(p.title)}</h3><p class="muted">${esc(names(p.authors).join(", ") || "Unknown authors")}</p>
      <p class="muted">${p.year || ""}${p.venue ? ". <i>" + esc(p.venue) + "</i>" : ""}${p.doi ? `. <a href="https://doi.org/${esc(p.doi)}" target="_blank" rel="noopener">DOI ${esc(p.doi)}</a>` : ""}</p>
      <div class="sec"><b>CITED BY</b><span class="big">${p.citations.toLocaleString()}</span></div>
      <div class="sec"><b>ABSTRACT</b>${p.abstract ? esc(p.abstract) : '<span class="muted">No abstract stored.</span>'}</div>
      <label class="sec">Collection<select id="dc"><option value="">None</option>${cols.map(c => `<option value="${c.id}" ${c.id === p.collection_id ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select></label>
      <label>Tags<input id="dt" value="${esc(p.tags)}" placeholder="Separate with commas"></label>
      <label>Notes<textarea id="dn" rows="6">${esc(p.notes)}</textarea></label>
      <div class="row"><button class="btn" id="dsave">Save changes</button><button class="btn alt" id="ddel">${del === p.id ? "Confirm delete" : "Delete"}</button></div>`;
    $("#dsave").onclick = async () => {
      const v = {collection_id: $("#dc").value || null, tags: $("#dt").value.trim(), notes: $("#dn").value};
      const {error} = await sb.from("papers").update(v).eq("id", p.id);
      if (error) return flash(error.message); Object.assign(p, v); flash("Saved"); draw();
    };
    $("#ddel").onclick = async () => {
      if (del !== p.id) { del = p.id; return drawDetail(); }
      await sb.from("papers").delete().eq("id", p.id); papers = papers.filter(x => x.id !== p.id); cur = null; del = null;
      $("#zd").innerHTML = '<p class="muted">Paper deleted.</p>'; draw();
    };
  }
  $("#zp").addEventListener("click", e => {
    const c = e.target.closest("[data-col]"), r = e.target.closest("tr[data-i]");
    if (c) { col = c.dataset.col; draw(); }
    if (r) { cur = papers.find(p => p.id === r.dataset.i); del = null; draw(); }
  });
  $("#zq").addEventListener("input", e => { q = e.target.value.trim().toLowerCase(); draw(); });
  $("#ncb").onclick = async () => {
    const name = $("#nc").value.trim(); if (!name) return;
    const {error} = await sb.from("collections").insert({name}); if (error) return flash(error.message);
    $("#nc").value = ""; load();
  };
  load();
}