AI Research Assistant — Setup Instructions

REQUIREMENTS:
- Python 3.11 or 3.12 installed (avoid Python 3.13/3.14 — some AI libraries don't have ready-made installers for them yet and will fail to install)
- Download Python from https://python.org (check "Add Python to PATH" during install)

SETUP STEPS:
1. Extract this folder anywhere on your computer.
2. Open the folder in VS Code (File > Open Folder), or open a terminal inside it.
3. Create a virtual environment:
   python -m venv venv
4. Activate it:
   Windows: venv\Scripts\activate
   Mac/Linux: source venv/bin/activate
5. Install required libraries:
   pip install -r requirements.txt
   (This step downloads AI libraries like PyTorch/Transformers — may take several minutes and a few hundred MB of internet.)
6. Run the app:
   streamlit run app.py
7. Your browser should open automatically at http://localhost:8501
   If not, copy that address into your browser manually.

NOTES:
- The first time you click "Generate Summary" or "Summarize this paper," it will download an AI model (~1.6GB total) — this needs internet and can take a few minutes. After that, it's cached and fast.
- If you get a PowerShell error about "running scripts is disabled" on step 4, run this once first:
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
  Then type Y and press Enter, and retry step 4.