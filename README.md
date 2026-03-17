# SynGen v2.0 — Synthetic Data Platform

Prompt-driven synthetic data generation with Groq (llama-3.3-70b), FastAPI, and a full statistical engine.

## What's New in v2.0

- **Groq LLM** — llama-3.3-70b-versatile for ultra-fast schema extraction
- **Advanced distributions** — Normal, Uniform, Lognormal, Poisson, Exponential, Beta, Gamma, Zipf
- **16+ field types** — UUID, Date, IP, URL, Color, Text, Country, and more
- **Schema editor** — Add, edit, remove fields via modal UI without re-prompting
- **Constraints engine** — Conditional field rules (if X = Y then set Z)
- **Unique enforcement** — Deduplicated fields across the dataset
- **Nullable control** — Per-field or global null rate
- **Column stats** — Mean, std, percentiles, histograms, category distributions
- **Mini charts** — Inline histogram visualizations per numeric field
- **4 export formats** — CSV, JSON, Excel (formatted), Parquet

## Quick Start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Set Groq API key (free at console.groq.com)
cp .env.example .env
# Edit .env → GROQ_API_KEY=your_key

# 3. Run
uvicorn app.main:app --reload --port 8000
# Open http://localhost:8000
```

## Docker

```bash
docker build -t syngen .
docker run -p 8000:8000 -e GROQ_API_KEY=your_key syngen
```

---


## Project Structure

```
syngen2/
├── app/
│   ├── main.py                 # FastAPI routes
│   ├── schema_interpreter.py   # Groq LLM → schema
│   ├── data_engine.py          # Statistical data engine (NumPy/SciPy/Faker)
│   └── exporters.py            # CSV/JSON/Excel/Parquet
├── static/
│   ├── css/main.css            # Aurora glass UI
│   └── js/main.js              # Frontend logic
├── templates/index.html        # Main page
├── requirements.txt
├── Dockerfile
└── .env.example
```

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Web UI |
| POST | `/api/interpret` | Prompt → schema (Groq) |
| POST | `/api/generate` | Schema → dataset + stats |
| POST | `/api/export/{fmt}` | CSV / JSON / Excel / Parquet |
| POST | `/api/schema/add-field` | Add field to schema |
| POST | `/api/schema/remove-field` | Remove field by index |
| POST | `/api/schema/edit-field` | Edit field by index |
| GET | `/api/examples` | Example prompts |
| GET | `/api/field-types` | All supported field types |
| GET | `/api/docs` | Swagger UI |

## Notes

- Without GROQ_API_KEY, the app returns a built-in demo schema (e-commerce customers)
- Data generation is fully server-side — no external calls during generate/export
- Relationship modeling uses weighted linear blending post-generation
- Constraint engine applies conditional field overrides after generation
