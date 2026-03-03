# LumiGRAD (Clean Build)

This is a minimal, hackathon build that demonstrates:
- Topic-level mastery tracking with time decay (evolving learning state)
- Learning state classification (improving/stable/regressing/inactive)
- Explainable, actionable weekly plan generation
- Streamlit dashboard + quiz page
- SQLite storage (lightweight, realistic over months/years)

## Quickstart

### 1) Install
```bash
pip install -r requirements.txt
```

### 2) Create DB + seed mock data
```bash
python -m db_engine.setup_db
```

This creates `db_engine/lumi_grad.db` and seeds the 2-course mock pattern.

### 3) Run Streamlit
```bash
streamlit run landing.py
```

## Notes
- `quiz/quiz_runner.py` scrapes the lecture page for a PDF, extracts text, and calls an LLM QuizAgent.
- `quiz/agents.py` includes QuizAgent + GraderAgent (LLM-based) that return strict JSON consumed by the UI.
- All DB paths are centralized in `db_engine/db.py` to avoid NameError/relative-path issues.

## LLM Configuration

The app supports **OpenAI** or **Azure OpenAI** via environment variables.

### OpenAI

Set:
- `OPENAI_API_KEY`
- (optional) `OPENAI_MODEL` (default: `gpt-4o`)

### Azure OpenAI

Set:
- `AZURE_OPENAI_ENDPOINT` (example: `https://<resource>.openai.azure.com`)
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_DEPLOYMENT` (your deployment name)
- (recommended) `AZURE_OPENAI_API_VERSION` (default in code: `2024-10-21`)

For Azure, the **deployment name** is passed as the `model` parameter in the SDK.
