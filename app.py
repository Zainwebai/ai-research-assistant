import streamlit as st
import feedparser
import urllib.parse
import requests
import fitz  # this is PyMuPDF, used to read PDF files
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

st.title("AI Research Assistant")
st.write("Search for research papers on arXiv")

query = st.text_input("Enter a topic to search (e.g. 'neural networks'):")

search_button = st.button("Search")

@st.cache_data(ttl=600)  # cache results for 10 minutes so repeat searches don't re-hit arXiv
def search_arxiv(search_term):
    encoded_query = urllib.parse.quote(search_term)
    url = f"https://export.arxiv.org/api/query?search_query=all:{encoded_query}&start=0&max_results=5"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    response = requests.get(url, headers=headers, timeout=30)
    return response.status_code, response.text

# --- Summarization model setup (shared by both search results and PDF upload) ---

@st.cache_resource  # loads the model once and keeps it in memory across reruns
def load_summarizer_model():
    model_name = "facebook/bart-large-cnn"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    return tokenizer, model

def summarize_text(text, tokenizer, model, max_output_length=150, min_output_length=40):
    inputs = tokenizer(text, return_tensors="pt", max_length=1024, truncation=True)
    summary_ids = model.generate(
        inputs["input_ids"],
        max_length=max_output_length,
        min_length=min_output_length,
        num_beams=4,
        early_stopping=True
    )
    return tokenizer.decode(summary_ids[0], skip_special_tokens=True)

# --- Search section ---

if search_button and query:
    try:
        status_code, raw_text = search_arxiv(query)

        if status_code == 429:
            st.write("arXiv is rate-limiting us. Please wait a few minutes and try again.")
        elif status_code != 200:
            st.write(f"Unexpected response from arXiv: {status_code}")
        else:
            feed = feedparser.parse(raw_text)

            if len(feed.entries) == 0:
                st.write("No results found. Try a different search term.")
            else:
                st.write(f"Found {len(feed.entries)} results:")

                # Save search results in session_state so summarize buttons
                # still work correctly after the page reruns on click
                st.session_state["search_results"] = feed.entries

    except requests.exceptions.RequestException as e:
        st.write(f"Request failed: {e}")

# Display search results (runs on every rerun, using saved results if they exist)
if "search_results" in st.session_state:
    for index, entry in enumerate(st.session_state["search_results"]):
        st.subheader(entry.title)
        authors = ", ".join(author.name for author in entry.authors)
        st.write(f"**Authors:** {authors}")
        st.write(f"**Published:** {entry.published}")
        st.write(entry.summary)
        st.write(f"[Read full paper]({entry.link})")

        # Unique key per button needed since we have multiple in a loop
        if st.button("Summarize this paper", key=f"summarize_btn_{index}"):
            with st.spinner("Summarizing..."):
                tokenizer, model = load_summarizer_model()
                abstract_summary = summarize_text(entry.summary, tokenizer, model, max_output_length=100, min_output_length=25)
                st.write("**AI Summary:**")
                st.write(abstract_summary)

        st.write("---")


st.write("## Upload a Research Paper (PDF)")

uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

if uploaded_file is not None:
    # Read the uploaded file's raw bytes
    pdf_bytes = uploaded_file.read()

    # Open the PDF from memory (not from disk) using PyMuPDF
    pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")

    st.write(f"PDF loaded successfully. Number of pages: {pdf_document.page_count}")

    # Extract text from every page and combine it into one string
    full_text = ""
    for page_number in range(pdf_document.page_count):
        page = pdf_document[page_number]
        full_text += page.get_text()

    pdf_document.close()

    st.write("### Extracted Text Preview (first 1000 characters):")
    st.text(full_text[:1000])
    st.write(f"Total characters extracted: {len(full_text)}")

    # Save the full text so later parts (summarization, chat) can use it
    st.session_state["paper_text"] = full_text


st.write("## Summarize the Paper")

if "paper_text" in st.session_state:
    if st.button("Generate Summary"):
        with st.spinner("Loading AI model and generating summary... this may take a minute the first time."):
            tokenizer, model = load_summarizer_model()

            full_text = st.session_state["paper_text"]

            # Chunk text since the model can only read ~1024 tokens at once
            max_chunk_length = 3000
            chunks = [full_text[i:i + max_chunk_length] for i in range(0, len(full_text), max_chunk_length)]
            chunks_to_summarize = chunks[:3]  # keep it fast for now

            combined_summary = ""
            for chunk in chunks_to_summarize:
                combined_summary += summarize_text(chunk, tokenizer, model) + " "

            st.write("### Summary:")
            st.write(combined_summary)
else:
    st.write("Upload a PDF above first, then come back here to generate a summary.")