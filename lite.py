from flask import Flask, jsonify, render_template, request
from core import register, search_sources

app = Flask(__name__, static_folder="public/static")
register(app)


@app.get("/")
def page_search():
    return render_template("search.html", page="search")


@app.get("/api/search")
def api_search():
    term = request.args.get("q", "").strip()
    return jsonify(search_sources(term) if term else [])


@app.post("/api/summarize")
def api_summarize():
    return jsonify(error="AI summaries only work in the local version of this project."), 501