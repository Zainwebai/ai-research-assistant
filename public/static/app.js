// Discover page: searches arXiv and Semantic Scholar, summarizes abstracts, saves to your library.
// Uses $, esc, sb, flash and user from site.js.
if (document.body.dataset.page === "search") {
  let results = [];

  const api = async (url, body) => {
    const r = await fetch(url, body ? {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)} : {});
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.error || "Something went wrong. Check the terminal for details.");
    return d;
  };

  const card = (p, i) => `<article class="item">
    <h3>${esc(p.title)}</h3>
    <p class="muted">${esc(p.authors.join(", ") || "Unknown authors")}, ${esc(p.year)}. ${esc(p.source)}</p>
    <p>${esc(p.abstract)}</p>
    ${p.url ? `<p><a href="${esc(p.url)}" target="_blank" rel="noopener">View source</a></p>` : ""}
    <div class="row">
      <button class="btn alt" data-do="sum" data-i="${i}">Summarize</button>
      <button class="btn alt" data-do="save" data-i="${i}">Save to Library</button>
    </div>
    <details><summary>Citations</summary><pre>${esc(Object.entries(p.citations).map(([k, v]) => k + ": " + v).join("\n\n"))}</pre></details>
    <div class="out"></div></article>`;

  const go = async () => {
    const q = $("#q").value.trim(), b = $("#go");
    if (!q) return;
    b.disabled = true; b.textContent = "Searching…"; $("#status").textContent = "Searching…";
    try {
      results = await api("/api/search?q=" + encodeURIComponent(q));
      $("#status").textContent = results.length ? `Found ${results.length} papers.` : "No results. Try a different search term.";
      $("#results").innerHTML = results.map(card).join("");
    } catch (e) { $("#status").innerHTML = `<span class="err">${esc(e.message)}</span>`; }
    b.disabled = false; b.textContent = "Search";
  };
  $("#go").onclick = go;
  $("#q").addEventListener("keydown", e => { if (e.key === "Enter") go(); });

  $("#results").addEventListener("click", async e => {
    const b = e.target.closest("[data-do]");
    if (!b) return;
    const p = results[+b.dataset.i], out = b.closest(".item").querySelector(".out");
    if (b.dataset.do === "sum") {
      b.disabled = true; b.textContent = "Working…";
      try {
        const d = await api("/api/summarize", {text: p.abstract});
        out.innerHTML = `<p><strong>AI summary.</strong> ${esc(d.summary)}</p>`;
      } catch (err) { out.innerHTML = `<p class="err">${esc(err.message)}</p>`; }
      b.disabled = false; b.textContent = "Summarize";
    } else {
      if (!user) return location.href = "/login";
      const {error} = await sb.from("papers").insert({title: p.title, authors: p.authors.join("; "), year: +p.year || null, venue: p.source, url: p.url, abstract: p.abstract});
      if (error) return flash(error.message);
      b.disabled = true; b.textContent = "Saved";
    }
  });
}