# Business AI Assistant

Ask questions about sales data in plain English. A Python service computes the real numbers, an LLM (Google Gemini) explains them, and a React dashboard shows the result.

**Status:** work in progress. The Python service, the AI layer and the React dashboard work together today. The Java backend runs on its own and is not yet connected to the Python service (see Roadmap).

## Architecture

```
React dashboard (5173)  --->  Python / FastAPI (8000)  --->  Google Gemini API
                               pandas analytics
                               /analytics/*  /ai/ask

Spring Boot backend (8080)     Java + JPA + H2 database, /api/sales
(standalone for now)
```

| Folder | What it is | Stack |
|---|---|---|
| `analytics-python/` | Analytics endpoints and the `/ai/ask` question endpoint | FastAPI, pandas, google-genai |
| `frontend-react/` | Dashboard: question box, answer, KPI figures, breakdown tables | React 18, Vite |
| `backend-java/` | Sales REST API backed by an in-memory database | Spring Boot 3, Spring Data JPA, H2 |

## Design decisions

- **pandas does the math, the LLM does the explaining.** Language models are unreliable at arithmetic, so the service computes the figures itself and gives them to the model as context. The prompt tells the model to answer only from that data and to say so when it can't.
- **Retry with exponential backoff.** Temporary Gemini errors (429, 500, 503, 504) are retried up to 3 times. Permanent errors (wrong model, bad key) fail immediately.
- **No secrets in code.** The API key and model name come from environment variables.
- **CORS is restricted** to the local dev frontend.

## Run it (Windows)

### 1. Python service
```
cd analytics-python
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
set GEMINI_API_KEY=your_key_here
set GEMINI_MODEL=gemini-3.8-flash
uvicorn main:app --reload --port 8000
```
Get a free key at https://aistudio.google.com. Model names change often: if you get a "model not found" error, set `GEMINI_MODEL` to a current Flash model. Interactive API docs: http://localhost:8000/docs

### 2. React dashboard (new terminal)
```
cd frontend-react
npm install
npm run dev
```
Open http://localhost:5173

### 3. Java backend (optional, standalone)
Open `backend-java` in IntelliJ IDEA (JDK 21) and run `BackendApplication`, or run `mvn spring-boot:run`. Then visit http://localhost:8080/api/sales

## API

| Method | Path | Returns |
|---|---|---|
| GET | `/analytics/summary` | Total revenue, units, average per sale |
| GET | `/analytics/by-region` | Revenue and units per region |
| GET | `/analytics/by-product` | Revenue and units per product |
| POST | `/ai/ask` | `{"question": "..."}` returns an answer, model name, attempts |

## Roadmap

- [x] Spring Boot REST API with JPA and H2
- [x] Python analytics service
- [x] Gemini question endpoint with retry logic
- [x] React dashboard
- [ ] Java backend calls the Python service instead of using its own copy of the data
- [ ] Docker Compose to start every service with one command
- [ ] Tests
