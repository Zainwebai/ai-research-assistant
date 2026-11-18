"""Pages and API routes shared by the local site (main.py) and the Vercel site (lite.py)."""
import math
import os
import feedparser
import requests
from flask import jsonify, render_template, request
from citations import format_citation

try:
    import config
except ImportError:  # on Vercel there is no config.py, so settings come from environment variables
    config = None

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
SEARCH_CACHE = {}


def setting(name):
    return os.environ.get(name) or getattr(config, name, "")


def abstract_text(inverted):
    """OpenAlex stores abstracts as {word: [positions]}, so rebuild the sentence."""
    if not inverted:
        return ""
    words = {pos: w for w, positions in inverted.items() for pos in positions}
    return " ".join(words[i] for i in sorted(words))


def search_sources(term):
    """Searches arXiv and Semantic Scholar together, for the Discover page."""
    if term in SEARCH_CACHE:
        return SEARCH_CACHE[term]
    papers = []
    try:
        r = requests.get("https://export.arxiv.org/api/query", headers=HEADERS, timeout=25,
                         params={"search_query": f"all:{term}", "max_results": 5})
        if r.status_code == 200:
            for e in feedparser.parse(r.text).entries:
                papers.append({"title": " ".join(e.title.split()), "authors": [a.name for a in e.authors],
                               "year": e.published[:4], "abstract": " ".join(e.summary.split()),
                               "url": e.link, "source": "arXiv"})
    except requests.RequestException:
        pass
    try:
        r = requests.get("https://api.semanticscholar.org/graph/v1/paper/search", headers=HEADERS, timeout=25,
                         params={"query": term, "fields": "title,authors,abstract,year,url", "limit": 5})
        if r.status_code == 200:
            for i in r.json().get("data", []):
                papers.append({"title": i.get("title") or "(untitled)",
                               "authors": [a.get("name", "") for a in i.get("authors") or []],
                               "year": str(i.get("year") or ""),
                               "abstract": i.get("abstract") or "(no abstract available)",
                               "url": i.get("url") or "", "source": "Semantic Scholar"})
    except requests.RequestException:
        pass
    for p in papers:
        p["citations"] = {s: format_citation(p["authors"], p["year"], p["title"], p["source"], s)
                          for s in ("APA", "MLA", "IEEE")}
    if papers:
        SEARCH_CACHE[term] = papers
    return papers


def register(app):
    @app.context_processor
    def inject_config():
        return {"SB_URL": setting("SUPABASE_URL"), "SB_KEY": setting("SUPABASE_ANON_KEY")}

    @app.get("/login")
    def page_login():
        return render_template("login.html", page="login")

    @app.get("/literature")
    def page_literature():
        return render_template("literature.html", page="literature")

    @app.get("/my-library")
    def page_my_library():
        return render_template("my_library.html", page="mylib")

    @app.get("/api/literature")
    def api_literature():
        q = request.args.get("q", "").strip()
        n = min(int(request.args.get("n", 100)), 1000)
        flt = []
        if request.args.get("from"):
            flt.append(f"from_publication_date:{request.args['from']}-01-01")
        if request.args.get("to"):
            flt.append(f"to_publication_date:{request.args['to']}-12-31")
        results, total = [], 0
        for page in range(1, math.ceil(n / 100) + 1):
            r = requests.get("https://api.openalex.org/works", timeout=40, params={
                "search": q, "filter": ",".join(flt), "per_page": 100, "page": page,
                "sort": request.args.get("sort", "relevance_score:desc"),
                "api_key": setting("OPENALEX_API_KEY"),
                "select": "doi,title,publication_year,cited_by_count,authorships,primary_location,abstract_inverted_index"})
            if r.status_code != 200:
                return jsonify(error=f"OpenAlex returned {r.status_code}. Check your OpenAlex key."), 502
            data = r.json()
            total = data["meta"]["count"]
            for w in data["results"]:
                src = ((w.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
                doi = (w.get("doi") or "").replace("https://doi.org/", "")
                results.append({
                    "title": w.get("title") or "(untitled)",
                    "authors": "; ".join(a["author"]["display_name"] for a in w.get("authorships", [])),
                    "year": w.get("publication_year"), "venue": src, "doi": doi,
                    "url": f"https://doi.org/{doi}" if doi else "",
                    "abstract": abstract_text(w.get("abstract_inverted_index")),
                    "citations": w.get("cited_by_count") or 0})
            if len(data["results"]) < 100:
                break
        return jsonify(total=total, results=results[:n])