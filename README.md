# LumiGRAD 🎓

**AI-Powered Academic Performance Intelligence System.**

LumiGRAD tracks your mastery across course topics over time, detects learning trends (improving, stable, regressing, or inactive), and generates actionable weekly plans — powered by an LLM backend and a clean Streamlit dashboard.

---

## Features

- **Topic-level mastery tracking** with time decay (your learning state evolves realistically over weeks/months)
- **Learning state classification** — automatically labels each topic as *improving*, *stable*, *regressing*, or *inactive*
- **Explainable weekly plan generation** — AI-generated study plans grounded in your actual performance data
- **Quiz module** — scrapes course lecture PDFs and generates + grades quizzes via LLM agents
- **Streamlit dashboard** — visual progress overview and quiz interface in one place
- **SQLite storage** — lightweight, file-based, built to scale across months of usage

---

## Quickstart

### 1. Clone the repo

```bash
git clone https://github.com/NishaanthSivakumar/MLDA_DLWEEK2026.git
cd MLDA_DLWEEK2026
```

### 2. Set up your environment file

Create a `.env` file in the project root. **This file is not included in the repository for security reasons — you must create it yourself.**

#### Option A: Azure OpenAI (recommended)

```env
AZURE_OPENAI_ENDPOINT=https://<your-resource-name>.openai.azure.com
AZURE_OPENAI_API_KEY=your-azure-api-key-here
AZURE_OPENAI_DEPLOYMENT=your-deployment-name
AZURE_OPENAI_API_VERSION=2024-10-21
```

#### Option B: OpenAI

```env
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_MODEL=gpt-4o
```

> ⚠️ Never commit your `.env` file to version control. It is listed in `.gitignore` by default.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Initialize the database and seed mock data

```bash
python -m db_engine.setup_db
```

This creates `db_engine/lumi_grad.db` and seeds a 2-course mock learning pattern so you can explore the dashboard immediately.

### 5. Launch the app

```bash
streamlit run landing.py
```

---


## LLM Configuration

LumiGRAD supports both **Azure OpenAI** and **OpenAI** via environment variables. The app auto-detects which provider to use based on which variables are present.

| Provider | Required Variables |
|---|---|
| **Azure OpenAI** | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT` |
| **OpenAI** | `OPENAI_API_KEY` |

Optional variables:
- `OPENAI_MODEL` — defaults to `gpt-4o`
- `AZURE_OPENAI_API_VERSION` — defaults to `2024-10-21`

---

## How It Works

1. **Mastery tracking** — quiz results are stored per topic with timestamps. A time-decay function reduces confidence scores for topics you haven't revisited recently.
2. **State classification** — each topic is classified based on score trend and recency: *improving*, *stable*, *regressing*, or *inactive*.
3. **Weekly plan generation** — an LLM agent reads your current learning state and produces a prioritized, explainable study plan.
4. **Quiz pipeline** — `quiz_runner.py` scrapes the lecture page for a PDF, extracts text, and passes it to `QuizAgent`. Answers are evaluated by `GraderAgent`, both returning strict JSON consumed by the UI.

---

## Notes

- All database paths are centralized in `db_engine/db.py` to avoid path/import issues across modules.
- The quiz agents return strict JSON — if you extend them, maintain the schema to avoid UI breakage.
- SQLite is used intentionally for simplicity; the schema is straightforward to migrate to PostgreSQL if needed.

---

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.

---

## License

[MIT](LICENSE)
