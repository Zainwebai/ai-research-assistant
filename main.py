import math
import requests
from flask import jsonify, render_template, request
from server import app
import config


@app.context_processor
def inject_config():
    return {"SB_URL": config.SUPABASE_URL, "SB_KEY": config.SUPABASE_ANON_KEY}


@app.get("/login")
def page_login():
    return render_template("login.html", page="login")


@app.get("/literature")
def page_literature():
    return render_template("literature.html", page="literature")


@app.get("/my-library")
def page_my_library():
    return render_template("my_library.html", page="mylib")


def abstract_text(inverted):
    """OpenAlex stores abstracts as {word: [positions]}, so rebuild the sentence."""
    if not inverted:
        return ""
    words = {pos: w for w, positions in inverted.items() for pos in positions}
    return " ".join(words[i] for i in sorted(words))


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
            "api_key": config.OPENALEX_API_KEY,
            "select": "doi,title,publication_year,cited_by_count,authorships,primary_location,abstract_inverted_index"})
        if r.status_code != 200:
            return jsonify(error=f"OpenAlex returned {r.status_code}. Check your OpenAlex key in config.py."), 502
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


if __name__ == "__main__":
    app.run(port=5000, debug=False)