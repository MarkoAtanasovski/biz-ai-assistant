# Business AI Assistant

Ask questions about your sales data in plain English. Upload a CSV, and an LLM (Google Gemini) picks which calculation to run; pandas does the math; a React dashboard shows the result.

<!-- Demo GIF: record it, save as docs/demo.gif, then uncomment the next line.
![Demo: upload a CSV and ask a question](docs/demo.gif)
-->

## Architecture

```
React dashboard (5173) --> Spring Boot (8080) --> Python / FastAPI (8000) --> Gemini API
                            owns the data          pandas analytics +
                            PostgreSQL             function-calling loop
                            CSV upload
```

Java stores the sales rows in PostgreSQL and sends them to Python on every request. Python holds no data of its own; Java is the single source of truth.

| Folder | What it is | Stack |
|---|---|---|
| `backend-java/` | Owns the data, imports CSVs, calls Python | Spring Boot 3, JPA, PostgreSQL, WebClient |
| `analytics-python/` | Stateless analytics + the `/ai/ask` endpoint | FastAPI, pandas, google-genai |
| `frontend-react/` | Dashboard: question box, answer, upload, tables | React 18, Vite |

## Design decisions

- **The model never sees raw rows.** Gemini is given a small set of functions (`get_summary`, `get_totals_by`, `get_top_n`, `compare_values`) and decides which to call. Python runs them with pandas and returns only aggregates. This keeps individual records out of the prompt, keeps the prompt small however big the data is, and means every number in an answer traces back to a function call (the UI shows them under "How this was calculated").
- **pandas does the math, the LLM does the explaining.** Even differences and percent changes are computed in code, because language models are unreliable at arithmetic.
- **Bounded tool loop.** The model can chain calls (e.g. rank regions, then compare two), but stops after 5 rounds. Bad arguments come back to the model as an error result instead of crashing the request.
- **Retry with exponential backoff.** Temporary Gemini errors (429, 500, 503, 504) are retried up to 3 times; permanent ones (wrong model, bad key) fail immediately.
- **Uploads are validated before anything is saved.** A bad row gives an error naming the row, and existing data is untouched. Excel-style semicolon files with decimal commas work.
- **Timeouts everywhere.** Java gives up on Python after 15 s (60 s for `/ai/ask`) and returns a 504 instead of hanging.
- **One error shape.** Every error the UI sees is `{"detail": "..."}`.
- **No secrets in code.** The API key and model name come from environment variables.

## Run it

### Option A: Docker Compose (everything, one command)
```
cp .env.example .env
# edit .env and add your real GEMINI_API_KEY
docker compose up --build
```
Open http://localhost:5173. Data lives in a Docker volume and survives restarts (`docker compose down -v` wipes it).

### Option B: run each service directly

**1. Python service**
```
cd analytics-python
python -m venv venv
venv\Scripts\activate          # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
set GEMINI_API_KEY=your_key_here     # macOS/Linux: export ...
uvicorn main:app --reload --port 8000
```
Get a free key at https://aistudio.google.com. The model defaults to `gemini-3.8-flash`; model names change often, so if you get "model not found", set `GEMINI_MODEL` to a current Flash model. API docs: http://localhost:8000/docs

**2. Java backend** (new terminal, JDK 21)
```
cd backend-java
mvn spring-boot:run -Dspring-boot.run.profiles=h2     # no database needed (in-memory)
```
To use PostgreSQL instead, start one and drop the profile (defaults: `localhost:5432/bizai`, user/password `bizai`; override with `DB_URL`, `DB_USER`, `DB_PASSWORD`).

**3. React dashboard** (new terminal)
```
cd frontend-react
npm install
npm run dev
```
Open http://localhost:5173.

## API (Java, port 8080)

The frontend only talks to Java.

| Method | Path | Returns |
|---|---|---|
| GET | `/api/sales` | Raw sales rows |
| POST | `/api/sales/upload` | Multipart `file` (+ `mode=replace\|append`). Returns `{imported, mode, totalRows}` |
| GET | `/api/analytics/summary` | Total revenue, units, average per sale, record count |
| GET | `/api/analytics/by-region` / `by-product` / `by-month` | Revenue and units per group |
| POST | `/api/ai/ask` | `{"question": "..."}` returns `{answer, model, tool_calls, llm_calls, retries}` |

CSV format: header row `region, product, revenue, units_sold, month` (month as `2026-07`; a full date is cut down to its month). A sample is in `frontend-react/public/sample-sales.csv`.

## Tests

```
cd analytics-python && pip install -r requirements-dev.txt && python -m pytest   # analytics, retry, tool loop, API (Gemini faked)
cd backend-java && mvn test                                                     # CSV parser + Spring Boot API test (in-memory H2)
```
GitHub Actions runs both, plus the frontend build, on every push (`.github/workflows/ci.yml`).

## Roadmap

- [x] Spring Boot REST API with JPA
- [x] Python analytics service
- [x] Gemini question endpoint with retry logic
- [x] React dashboard
- [x] Java owns the data; Python is stateless
- [x] Docker Compose
- [x] PostgreSQL + CSV upload
- [x] Function calling instead of pasting data into the prompt
- [x] Tests + CI
- [ ] Database migrations (Flyway) instead of `ddl-auto=update`
- [ ] Authentication
