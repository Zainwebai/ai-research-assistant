# AI Research Assistant

A research website: search up to 1,000 papers with citation metrics, import your own CSV, RIS or BibTeX files into a Zotero-style library, and export in standard formats. Accounts and data are stored in Supabase.

## Setup
1. Install Python 3.11 and create an environment: `py -3.11 -m venv venv311`, then `venv311\Scripts\activate`
2. Install: `pip install -r requirements.txt`
3. Create a free Supabase project and run the SQL for the `collections` and `papers` tables in its SQL Editor.
4. Copy `config.example.py` to `config.py` and fill in your Supabase URL, publishable key and a free OpenAlex key.
5. Run: `python main.py`, then open http://127.0.0.1:5000