import uuid
import feedparser
import fitz  # PyMuPDF
import requests
from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

import ai_engine as ai
from citations import format_citation
from research_library import (
    init_db, save_paper, get_all_saved_papers,
    update_paper_details, delete_paper, is_paper_saved,
)

app = Flask(__name__)
init_db()

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
SEARCH_CACHE = {}   # search term -> results, so repeat searches don't hit the sources again
DOCS = {}           # uploaded PDFs kept in memory: doc_id -> text, search index, chunks
_models = {}


def get_model(name):
    """Loads each AI model the first time it is needed, then reuses it."""
    loaders = {"sum": ai.load_model, "qa": ai.load_qa_model, "emb": ai.load_embedding_model}
    if name not in _models:
        _models[name] = loaders[name]()
    return _models[name]


def search_sources(term):
    if term in SEARCH_CACHE:
        return SEARCH_CACHE[term]
    papers = []
    try:
        r = requests.get("https://export.arxiv.org/api/query", headers=HEADERS, timeout=30,
                         params={"search_query": f"all:{term}", "max_results": 5})
        if r.status_code == 200:
            for e in feedparser.parse(r.text).entries:
                papers.append({"title": " ".join(e.title.split()), "authors": [a.name for a in e.authors],
                               "year": e.published[:4], "abstract": " ".join(e.summary.split()),
                               "url": e.link, "source": "arXiv"})
    except requests.RequestException:
        pass
    try:
        r = requests.get("https://api.semanticscholar.org/graph/v1/paper/search", headers=HEADERS, timeout=30,
                         params={"query": term, "fields": "title,authors,abstract,year,url", "limit": 5})
        if r.status_code == 200:
            for i in r.json().get("data", []):
                papers.append({"title": i.get("title") or "(untitled)",
                               "authors": [a.get("name", "") for a in i.get("authors") or []],
                               "year": str(i.get("year") or ""), "abstract": i.get("abstract") or "(no abstract available)",
                               "url": i.get("url") or "", "source": "Semantic Scholar"})
    except requests.RequestException:
        pass
    for p in papers:
        p["citations"] = {s: format_citation(p["authors"], p["year"], p["title"], p["source"], s)
                          for s in ("APA", "MLA", "IEEE")}
    if papers:
        SEARCH_CACHE[term] = papers
    return papers


# ---------- pages ----------
@app.get("/")
def page_search():
    return render_template("search.html", page="search")


@app.get("/library")
def page_library():
    return render_template("library.html", page="library")


@app.get("/reader")
def page_reader():
    return render_template("reader.html", page="reader")


# ---------- search and summaries ----------
@app.get("/api/search")
def api_search():
    term = request.args.get("q", "").strip()
    if not term:
        return jsonify([])
    return jsonify([dict(p, saved=is_paper_saved(p["title"])) for p in search_sources(term)])


@app.post("/api/summarize")
def api_summarize():
    tok, model = get_model("sum")
    summary = ai.generate_ai_response(request.json.get("text", ""), tok, model, mode="summarize",
                                      max_output_length=100, min_output_length=25)
    return jsonify(summary=summary)


# ---------- library ----------
@app.get("/api/library")
def api_library_list():
    return jsonify(get_all_saved_papers())


@app.post("/api/library")
def api_library_add():
    d = request.json
    if not is_paper_saved(d["title"]):
        save_paper(d["title"], d.get("authors", ""), d.get("year", ""), d.get("source", ""),
                   d.get("url", ""), d.get("abstract", ""))
    return jsonify(ok=True)


@app.put("/api/library/<int:pid>")
def api_library_update(pid):
    d = request.json
    update_paper_details(pid, d.get("collection", "General"), d.get("tags", ""), d.get("notes", ""))
    return jsonify(ok=True)


@app.delete("/api/library/<int:pid>")
def api_library_delete(pid):
    delete_paper(pid)
    return jsonify(ok=True)


# ---------- reading a PDF ----------
@app.post("/api/pdf")
def api_pdf():
    pdf = fitz.open(stream=request.files["file"].read(), filetype="pdf")
    text = "".join(page.get_text() for page in pdf)
    pages = pdf.page_count
    pdf.close()
    if not text.strip():
        return jsonify(error="No text found in this PDF. It may be a scanned document."), 400
    index, chunks = ai.build_search_index(text, get_model("emb"))
    doc_id = uuid.uuid4().hex
    DOCS[doc_id] = {"text": text, "index": index, "chunks": chunks}
    return jsonify(doc_id=doc_id, pages=pages, chars=len(text))


@app.post("/api/pdf/summary")
def api_pdf_summary():
    doc = DOCS.get(request.json.get("doc_id"))
    if not doc:
        return jsonify(error="Upload the PDF again, the server was restarted."), 404
    tok, model = get_model("sum")
    final, sections = ai.generate_ai_response(doc["text"], tok, model, mode="full_document_summarize")
    return jsonify(summary=final, sections=sections)


@app.post("/api/pdf/ask")
def api_pdf_ask():
    doc = DOCS.get(request.json.get("doc_id"))
    if not doc:
        return jsonify(error="Upload the PDF again, the server was restarted."), 404
    question = request.json.get("question", "")
    chunks = ai.find_relevant_chunks(question, doc["index"], doc["chunks"], get_model("emb"))
    qa_tok, qa_model = get_model("qa")
    return jsonify(answer=ai.answer_question(question, chunks, qa_tok, qa_model), excerpts=chunks)


@app.errorhandler(Exception)
def on_error(e):
    if isinstance(e, HTTPException):
        return e
    return jsonify(error=str(e)), 500


if __name__ == "__main__":
    app.run(port=5000, debug=False)