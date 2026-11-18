"""
Custom visual styling for the AI Research Assistant.
Injected once at the top of app.py via apply_custom_styling().
"""

import streamlit as st


def apply_custom_styling():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:wght@400;600;700&family=Inter:wght@400;500;600&display=swap');

        :root {
            --ink-900: #16213E;
            --paper-50: #FAF6EE;
            --brass-600: #A6712E;
            --moss-700: #3F5B4A;
            --line-200: #DCD4C2;
        }

        .stApp {
            background-color: var(--paper-50);
            font-family: 'Inter', sans-serif;
            color: var(--ink-900);
        }

        .ara-masthead {
            border-top: 3px solid var(--ink-900);
            border-bottom: 1px solid var(--line-200);
            padding: 1.6rem 0 1.1rem 0;
            margin-bottom: 2rem;
        }
        .ara-masthead-label {
            font-family: 'Inter', sans-serif;
            font-size: 0.8rem;
            color: var(--brass-600);
            letter-spacing: 0.02em;
            margin-bottom: 0.3rem;
        }
        .ara-masthead h1 {
            font-family: 'Source Serif 4', serif;
            font-weight: 700;
            font-size: 2.4rem;
            color: var(--ink-900);
            margin: 0;
            line-height: 1.15;
        }
        .ara-masthead p {
            font-family: 'Source Serif 4', serif;
            font-style: italic;
            font-size: 1.05rem;
            color: #5B5445;
            margin: 0.4rem 0 0 0;
        }

        h2 {
            font-family: 'Source Serif 4', serif !important;
            font-weight: 600 !important;
            color: var(--ink-900) !important;
            border-left: 4px solid var(--brass-600);
            padding-left: 0.7rem;
            margin-top: 2.4rem !important;
        }

        h3 {
            font-family: 'Source Serif 4', serif !important;
            color: var(--ink-900) !important;
        }

        hr {
            border: none;
            border-top: 1px solid var(--line-200);
            margin: 1.4rem 0;
        }

        .stButton > button {
            background-color: var(--ink-900);
            color: var(--paper-50);
            border: none;
            border-radius: 2px;
            font-family: 'Inter', sans-serif;
            font-weight: 500;
            padding: 0.5rem 1.1rem;
            transition: background-color 0.15s ease;
        }
        .stButton > button:hover {
            background-color: var(--brass-600);
            color: var(--paper-50);
        }

        .stTextInput > div > div > input {
            border: 1px solid var(--line-200);
            border-radius: 2px;
            background-color: #FFFFFF;
            font-family: 'Inter', sans-serif;
        }
        .stTextInput > div > div > input:focus {
            border-color: var(--brass-600);
            box-shadow: 0 0 0 1px var(--brass-600);
        }

        [data-testid="stFileUploaderDropzone"] {
            background-color: #FFFFFF;
            border: 1px dashed var(--line-200);
            border-radius: 2px;
        }

        .stProgress > div > div {
            background-color: var(--brass-600);
        }

        .streamlit-expanderHeader {
            font-family: 'Inter', sans-serif;
            font-weight: 500;
            color: var(--ink-900);
        }

        .stCodeBlock, code {
            font-family: 'Source Serif 4', serif;
            background-color: #FFFFFF !important;
            border: 1px solid var(--line-200) !important;
        }

        .stMarkdown h3 {
            margin-bottom: 0.2rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_masthead():
    st.markdown(
        """
        <div class="ara-masthead">
            <div class="ara-masthead-label">A RESEARCH TOOL</div>
            <h1>AI Research Assistant</h1>
            <p>Search, read, and question the literature — in one place.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )