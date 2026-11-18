"""
Generates citation strings in common academic formats, and full bibliography exports.
Pure formatting logic — no AI model involved.
"""


def format_apa(authors, year, title, source=""):
    if not authors:
        author_str = ""
    elif len(authors) == 1:
        author_str = authors[0]
    elif len(authors) == 2:
        author_str = f"{authors[0]} & {authors[1]}"
    else:
        author_str = f"{authors[0]} et al."
    return f"{author_str} ({year}). {title}. {source}".strip()


def format_mla(authors, year, title, source=""):
    if not authors:
        author_str = ""
    else:
        author_str = authors[0]
        if len(authors) > 1:
            author_str += ", et al."
    return f'{author_str}. "{title}." {source}, {year}.'.strip()


def format_ieee(authors, year, title, source=""):
    if not authors:
        author_str = ""
    elif len(authors) <= 3:
        author_str = ", ".join(authors)
    else:
        author_str = f"{authors[0]} et al."
    return f'{author_str}, "{title}," {source}, {year}.'.strip()


def format_citation(authors, year, title, source="", style="APA"):
    """Main entry point: pick the style and generate one citation string."""
    if style == "APA":
        return format_apa(authors, year, title, source)
    elif style == "MLA":
        return format_mla(authors, year, title, source)
    elif style == "IEEE":
        return format_ieee(authors, year, title, source)
    else:
        raise ValueError(f"Unknown citation style: {style}")


def format_bibliography(papers, style="APA"):
    """
    Formats a whole list of saved papers (from the library) into one
    bibliography text block, ready to copy or download — a basic version
    of what Zotero's 'export bibliography' feature does.
    """
    lines = []
    for paper in papers:
        # Saved papers store authors as a comma-joined string, not a list, so split it back out
        authors_list = [a.strip() for a in paper["authors"].split(",") if a.strip()]
        citation = format_citation(authors_list, paper["year"], paper["title"], paper["source"], style)
        lines.append(citation)
    return "\n\n".join(lines)