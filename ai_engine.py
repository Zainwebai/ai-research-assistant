"""
Central AI engine for the AI Research Assistant.

Every AI call in the app routes through generate_ai_response() below.
Right now it uses free, local Hugging Face models:
- BART for summarization
- DistilBERT (SQuAD-tuned) for question-answering
To upgrade to a paid API later (OpenAI, Anthropic, etc.), only the
inside of this file needs to change — app.py stays exactly the same.
"""

import torch
from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    AutoModelForQuestionAnswering,
)
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

MODEL_NAME = "facebook/bart-large-cnn"
QA_MODEL_NAME = "distilbert-base-cased-distilled-squad"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"


def load_model():
    """Loads the summarization tokenizer and model."""
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
    return tokenizer, model


def load_qa_model():
    """Loads a dedicated question-answering model."""
    tokenizer = AutoTokenizer.from_pretrained(QA_MODEL_NAME)
    model = AutoModelForQuestionAnswering.from_pretrained(QA_MODEL_NAME)
    return tokenizer, model


def summarize(text, tokenizer, model, max_output_length=150, min_output_length=40):
    """Summarizes one chunk of text using the loaded model."""
    inputs = tokenizer(text, return_tensors="pt", max_length=1024, truncation=True)
    summary_ids = model.generate(
        inputs["input_ids"],
        max_length=max_output_length,
        min_length=min_output_length,
        num_beams=4,
        length_penalty=2.0,
        early_stopping=True
    )
    return tokenizer.decode(summary_ids[0], skip_special_tokens=True)


def summarize_full_document(full_text, tokenizer, model, chunk_size=3000, progress_callback=None):
    """Hierarchical summarization: summarizes the ENTIRE document."""
    chunks = [full_text[i:i + chunk_size] for i in range(0, len(full_text), chunk_size)]

    chunk_summaries = []
    for i, chunk in enumerate(chunks):
        if progress_callback:
            progress_callback(i + 1, len(chunks))
        chunk_summaries.append(summarize(chunk, tokenizer, model, max_output_length=130, min_output_length=30))

    combined = " ".join(chunk_summaries)

    if len(combined) > chunk_size:
        final_summary = summarize(combined, tokenizer, model, max_output_length=250, min_output_length=80)
    else:
        final_summary = combined

    return final_summary, chunk_summaries


def extractive_answer(question, context, qa_tokenizer, qa_model):
    """
    Finds the exact answer span within a SINGLE passage of context.
    Returns both the answer text and a proper combined confidence score
    (start position confidence x end position confidence).
    """
    inputs = qa_tokenizer(question, context, return_tensors="pt", truncation=True, max_length=384)

    with torch.no_grad():
        outputs = qa_model(**inputs)

    start_probs = torch.softmax(outputs.start_logits, dim=1)
    end_probs = torch.softmax(outputs.end_logits, dim=1)

    start_index = torch.argmax(start_probs)
    end_index = torch.argmax(end_probs) + 1

    if end_index <= start_index:
        end_index = start_index + 1

    answer_tokens = inputs["input_ids"][0][start_index:end_index]
    answer = qa_tokenizer.decode(answer_tokens, skip_special_tokens=True)

    confidence = (start_probs[0][start_index] * end_probs[0][end_index - 1]).item()

    return answer.strip(), confidence


def generate_ai_response(prompt, tokenizer, model, mode="summarize", **kwargs):
    """Central entry point for ALL AI text generation in the app."""
    if mode == "summarize":
        return summarize(prompt, tokenizer, model, **kwargs)
    elif mode == "full_document_summarize":
        return summarize_full_document(prompt, tokenizer, model, **kwargs)
    else:
        raise ValueError(f"Unknown mode: {mode}")


def load_embedding_model():
    """Loads the small model used to convert text into searchable embeddings."""
    return SentenceTransformer(EMBEDDING_MODEL_NAME)


def chunk_text(text, chunk_size=1000, overlap=150):
    """Splits text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def build_search_index(text, embedding_model):
    """Turns a paper's full text into a searchable FAISS index."""
    chunks = chunk_text(text)
    embeddings = embedding_model.encode(chunks)
    embeddings = np.array(embeddings).astype("float32")

    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)

    return index, chunks


def find_relevant_chunks(question, index, chunks, embedding_model, top_k=4):
    """
    Finds the top_k chunks most relevant to the question.
    Always also includes the very first chunk (title/author/abstract area).
    """
    question_embedding = embedding_model.encode([question])
    question_embedding = np.array(question_embedding).astype("float32")

    distances, indices = index.search(question_embedding, top_k)
    relevant_indices = list(dict.fromkeys(indices[0]))

    if 0 not in relevant_indices:
        relevant_indices = [0] + relevant_indices

    relevant_chunks = [chunks[i] for i in relevant_indices]
    return relevant_chunks


def answer_question(question, relevant_chunks, qa_tokenizer, qa_model):
    """
    Runs the QA model SEPARATELY on each relevant chunk, then returns the
    answer from whichever chunk gave the highest confidence.
    """
    best_answer = ""
    best_confidence = -1.0

    for chunk in relevant_chunks:
        answer, confidence = extractive_answer(question, chunk, qa_tokenizer, qa_model)
        if answer and confidence > best_confidence:
            best_answer = answer
            best_confidence = confidence

    if not best_answer or best_confidence < 0.05:
        return "I couldn't find a confident answer to that in the paper. Try rephrasing the question, or it may not be covered in the text."

    return best_answer


def detect_research_gaps(abstracts_list, tokenizer, model):
    """
    Free-tier gap detection: looks across several paper abstracts and tries to
    surface what seems under-explored. This is a rough, best-effort feature using
    our local summarization model (not built for open-ended reasoning) — quality
    will improve significantly once a stronger model (e.g. Claude) is wired in later.
    """
    combined_text = "\n\n".join(
        f"Paper {i+1}: {abstract}" for i, abstract in enumerate(abstracts_list)
    )
    prompt = (
        "The following are abstracts from several research papers on the same topic. "
        "Identify what appears to be under-explored, missing, or a potential research gap "
        "across them:\n\n" + combined_text
    )
    return summarize(prompt, tokenizer, model, max_output_length=200, min_output_length=60)