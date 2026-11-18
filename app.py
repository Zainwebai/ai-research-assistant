import streamlit as st
import feedparser
import urllib.parse
import requests
import fitz  # PyMuPDF, used to read PDF files
from styles import apply_custom_styling, render_masthead
from ai_engine import (
    load_model,
    load_qa_model,
    generate_ai_response,
    load_embedding_model,
    build_search_index,
    find_relevant_chunks,
    answer_question,
    detect_research_gaps,
)
from research_library import (
    init_db,
    save_paper,
    get_all_saved_papers,
    get_all_collections,
    update_paper_details,
    delete_paper,
    is_paper_saved,
)
from citations import format_citation, format_bibliography

init_db()

st.set_page_config(page_title="AI Research Assistant", page_icon="📚", layout="centered")
apply_custom_styling()
render_masthead()

query = st.text_input("Enter a topic to search (e.g. 'neural networks'):")

search_button = st.button("Search")

@st.cache_data(ttl=600)
def search_arxiv(search_term):
    encoded_query = urllib.parse.quote(search_term)
    url = f"https://export.arxiv.org/api/query?search_query=all:{encoded_query}&start=0&max_results=5"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    response = requests.get(url, headers=headers, timeout=30)
    return response.status_code, response.text


@st.cache_data(ttl=600)
def search_semantic_scholar(search_term, limit=5):
    """
    Semantic Scholar's public API — free, no API key required for normal usage.
    Covers a much broader range of fields than arXiv alone (medicine, social science, etc.).
    """
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {"query": search_term, "fields": "title,authors,abstract,year,url", "limit": limit}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        return response.status_code, response.json()
    except requests.exceptions.RequestException:
        return None, None


@st.cache_resource
def get_model():
    return load_model()

@st.cache_resource
def get_qa_model():
    return load_qa_model()

@st.cache_resource
def get_embedding_model():
    return load_embedding_model()


def build_unified_results(arxiv_entries, semantic_scholar_items):
    """
    Combines arXiv and Semantic Scholar results into one common format,
    so the rest of the app doesn't need to know which source a paper came from.
    """
    unified = []

    for entry in arxiv_entries:
        authors = [author.name for author in entry.authors]
        unified.append({
            "title": entry.title,
            "authors": authors,
            "year": entry.published[:4] if hasattr(entry, "published") else "",
            "abstract": entry.summary,
            "url": entry.link,
            "source": "arXiv",
        })

    for item in semantic_scholar_items or []:
        authors = [a.get("name", "") for a in (item.get("authors") or [])]
        unified.append({
            "title": item.get("title") or "(untitled)",
            "authors": authors,
            "year": str(item.get("year") or ""),
            "abstract": item.get("abstract") or "(no abstract available)",
            "url": item.get("url") or "",
            "source": "Semantic Scholar",
        })

    return unified


# --- Search section ---

if search_button and query:
    arxiv_entries = []
    semantic_scholar_items = []

    try:
        status_code, raw_text = search_arxiv(query)
        if status_code == 429:
            st.write("arXiv is rate-limiting us right now — showing other sources only.")
        elif status_code == 200:
            feed = feedparser.parse(raw_text)
            arxiv_entries = feed.entries
    except requests.exceptions.RequestException as e:
        st.write(f"arXiv request failed: {e}")

    ss_status, ss_data = search_semantic_scholar(query)
    if ss_status == 200 and ss_data:
        semantic_scholar_items = ss_data.get("data", [])
    elif ss_status is not None and ss_status != 200:
        st.write(f"Semantic Scholar returned an unexpected response: {ss_status}")

    combined = build_unified_results(arxiv_entries, semantic_scholar_items)

    if len(combined) == 0:
        st.write("No results found across any source. Try a different search term.")
    else:
        st.write(f"Found {len(combined)} results across arXiv and Semantic Scholar:")
        st.session_state["search_results"] = combined


if "search_results" in st.session_state:
    results = st.session_state["search_results"]

    for index, paper in enumerate(results):
        st.subheader(paper["title"])
        st.write(f"**Source:** {paper['source']}  |  **Year:** {paper['year']}")
        authors_str = ", ".join(paper["authors"]) if paper["authors"] else "Unknown"
        st.write(f"**Authors:** {authors_str}")
        st.write(paper["abstract"])
        if paper["url"]:
            st.write(f"[View source]({paper['url']})")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("Summarize", key=f"summarize_btn_{index}"):
                with st.spinner("Summarizing..."):
                    tokenizer, model = get_model()
                    abstract_summary = generate_ai_response(
                        paper["abstract"], tokenizer, model,
                        mode="summarize", max_output_length=100, min_output_length=25
                    )
                    st.write("**AI Summary:**")
                    st.write(abstract_summary)

        with col2:
            already_saved = is_paper_saved(paper["title"])
            if already_saved:
                st.write("Saved to library")
            else:
                if st.button("Save to Library", key=f"save_btn_{index}"):
                    save_paper(
                        paper["title"], authors_str, paper["year"],
                        paper["source"], paper["url"], paper["abstract"]
                    )
                    st.success("Saved to 'General' — you can organize it below.")
                    st.rerun()

        with col3:
            style = st.selectbox("Citation style", ["APA", "MLA", "IEEE"], key=f"style_{index}")
            if st.button("Get Citation", key=f"cite_btn_{index}"):
                citation = format_citation(paper["authors"], paper["year"], paper["title"], paper["source"], style)
                st.code(citation, language=None)

        st.write("---")

    # --- Gap detection across current search results ---
    st.write("## Find Research Gaps")
    st.caption("Beta feature using a free local model — will improve significantly with a stronger AI model.")
    if st.button("Analyze gaps across these results"):
        with st.spinner("Analyzing..."):
            tokenizer, model = get_model()
            abstracts = [p["abstract"] for p in results if p["abstract"]]
            gaps = detect_research_gaps(abstracts, tokenizer, model)
            st.write("### Possible gaps:")
            st.write(gaps)


# --- My Research Library (basic Zotero-style reference manager) ---

st.write("## My Research Library")

all_collections = get_all_collections()
collection_options = ["All collections"] + all_collections
selected_collection = st.selectbox("Filter by collection", collection_options)

saved_papers = get_all_saved_papers(
    collection=selected_collection if selected_collection != "All collections" else None
)

if len(saved_papers) == 0:
    st.write("No papers saved yet — use 'Save to Library' on any search result above.")
else:
    st.caption(f"{len(saved_papers)} paper(s) in view")

    export_style = st.selectbox("Bibliography export style", ["APA", "MLA", "IEEE"], key="export_style")
    bibliography_text = format_bibliography(saved_papers, export_style)
    st.download_button(
        "Export bibliography (.txt)",
        data=bibliography_text,
        file_name=f"bibliography_{selected_collection.replace(' ', '_')}.txt",
        mime="text/plain",
    )

    st.write("---")

    for paper in saved_papers:
        st.write(f"**{paper['title']}**  ({paper['source']}, {paper['year']})")
        st.write(f"Authors: {paper['authors']}")
        st.write(paper["abstract"][:300] + ("..." if len(paper["abstract"]) > 300 else ""))
        if paper["url"]:
            st.write(f"[View source]({paper['url']})")

        current_tags = paper["tags"] if paper["tags"] else ""
        tag_list = [t.strip() for t in current_tags.split(",") if t.strip()]
        if tag_list:
            st.write(" ".join(f"`{t}`" for t in tag_list))
        st.write(f"Collection: *{paper['collection']}*")

        with st.expander("Edit collection, tags, and notes"):
            new_collection = st.text_input(
                "Collection (folder) name", value=paper["collection"], key=f"collection_{paper['id']}"
            )
            new_tags = st.text_input(
                "Tags (comma-separated)", value=current_tags, key=f"tags_{paper['id']}"
            )
            new_notes = st.text_area(
                "Notes", value=paper["notes"] or "", key=f"notes_{paper['id']}"
            )
            if st.button("Update", key=f"update_{paper['id']}"):
                update_paper_details(paper["id"], new_collection, new_tags, new_notes)
                st.success("Updated!")
                st.rerun()

        if st.button("Remove from library", key=f"delete_{paper['id']}"):
            delete_paper(paper["id"])
            st.rerun()

        st.write("---")


st.write("## Upload a Research Paper (PDF)")

uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

if uploaded_file is not None:
    pdf_bytes = uploaded_file.read()
    pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")

    st.write(f"PDF loaded successfully. Number of pages: {pdf_document.page_count}")

    full_text = ""
    for page_number in range(pdf_document.page_count):
        page = pdf_document[page_number]
        full_text += page.get_text()

    pdf_document.close()

    st.write("### Extracted Text Preview (first 1000 characters):")
    st.text(full_text[:1000])
    st.write(f"Total characters extracted: {len(full_text)}")

    if st.session_state.get("paper_text") != full_text:
        st.session_state.pop("search_index", None)
        st.session_state.pop("search_chunks", None)

    st.session_state["paper_text"] = full_text


st.write("## Summarize the Paper")

if "paper_text" in st.session_state:
    if st.button("Generate Summary"):
        tokenizer, model = get_model()
        full_text = st.session_state["paper_text"]

        progress_bar = st.progress(0, text="Starting...")

        def update_progress(current, total):
            progress_bar.progress(current / total, text=f"Summarizing section {current} of {total}...")

        final_summary, chunk_summaries = generate_ai_response(
            full_text, tokenizer, model,
            mode="full_document_summarize",
            progress_callback=update_progress
        )

        progress_bar.empty()

        st.write("### Summary (covers the entire paper):")
        st.write(final_summary)

        with st.expander(f"See section-by-section breakdown ({len(chunk_summaries)} sections)"):
            for i, s in enumerate(chunk_summaries):
                st.write(f"**Section {i+1}:** {s}")
else:
    st.write("Upload a PDF above first, then come back here to generate a summary.")


st.write("## Chat with the Paper")

if "paper_text" in st.session_state:

    if "search_index" not in st.session_state:
        with st.spinner("Preparing paper for chat (one-time setup)..."):
            embedding_model = get_embedding_model()
            index, chunks = build_search_index(st.session_state["paper_text"], embedding_model)
            st.session_state["search_index"] = index
            st.session_state["search_chunks"] = chunks
        st.success("Ready! Ask a question about the paper below.")

    user_question = st.text_input("Ask a question about the uploaded paper:")

    if st.button("Ask") and user_question:
        with st.spinner("Thinking..."):
            embedding_model = get_embedding_model()
            qa_tokenizer, qa_model = get_qa_model()

            relevant_chunks = find_relevant_chunks(
                user_question,
                st.session_state["search_index"],
                st.session_state["search_chunks"],
                embedding_model,
            )

            answer = answer_question(user_question, relevant_chunks, qa_tokenizer, qa_model)

            st.write("### Answer:")
            st.write(answer)

            with st.expander("See the exact text this answer was based on"):
                for i, chunk in enumerate(relevant_chunks):
                    st.write(f"**Excerpt {i+1}:**")
                    st.write(chunk)
else:
    st.write("Upload a PDF above first, then come back here to chat with it.")