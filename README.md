# Business AI Assistant

Ask questions about sales data in plain English. A Python service computes the real numbers, an LLM (Google Gemini) explains them, and a React dashboard shows the result.

**Status:** all four layers are connected. Java owns the data, sends it to Python on every request, and Python does the analytics and the AI call.

## Architecture

```
React dashboard (5173)  --->  Spring Boot backend (8080)  --->  Python / FastAPI (8000)  --->  Google Gemini API
                               owns the data (H2)              pandas analytics, no
                               /api/sales  /api/analytics/*     data of its own
                               /api/ai/ask
```

Java reads the sales rows from its own database on every request and sends them to Python, which computes the numbers and (for `/ai/ask`) asks Gemini to explain them. Python holds no data of its own; Java is the single source of truth.

| Folder | What it is | Stack |
|---|---|---|
| `backend-java/` | Owns the sales data; calls Python for analytics and AI | Spring Boot 3, Spring Data JPA, H2, WebClient |
| `analytics-python/` | Stateless analytics + the `/ai/ask` question endpoint | FastAPI, pandas, google-genai |
| `frontend-react/` | Dashboard: question box, answer, KPI figures, breakdown tables | React 18, Vite |

## Design decisions

- **pandas does the math, the LLM does the explaining.** Language models are unreliable at arithmetic, so the service computes the figures itself and gives them to the model as context. The prompt tells the model to answer only from that data and to say so when it can't.
- **Retry with exponential backoff.** Temporary Gemini errors (429, 500, 503, 504) are retried up to 3 times. Permanent errors (wrong model, bad key) fail immediately.
- **No secrets in code.** The API key and model name come from environment variables.
- **CORS is restricted** to the local dev frontend.

## Run it

All three services must be running for the dashboard to work fully.

### Option A: Docker Compose (all three services, one command)
```
cp .env.example .env
# edit .env and add your real GEMINI_API_KEY
docker compose up --build
```
Open http://localhost:5173

### Option B: run each service directly (Windows)

**1. Python service**
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

**2. Java backend (new terminal)**
Open `backend-java` in IntelliJ IDEA (JDK 21) and run `BackendApplication`, or run `mvn spring-boot:run`. It calls the Python service at `http://localhost:8000` by default (see `analytics.base-url` in `application.properties`). Then visit http://localhost:8080/api/sales

**3. React dashboard (new terminal)**
```
cd frontend-react
npm install
npm run dev
```
Open http://localhost:5173

## API

The frontend only talks to Java. Java is the one calling Python underneath.

| Method | Path (on Java, port 8080) | Returns |
|---|---|---|
| GET | `/api/sales` | Raw sales rows from the database |
| GET | `/api/analytics/summary` | Total revenue, units, average per sale |
| GET | `/api/analytics/by-region` | Revenue and units per region |
| GET | `/api/analytics/by-product` | Revenue and units per product |
| POST | `/api/ai/ask` | `{"question": "..."}` returns an answer, model name, attempts |

## Roadmap

- [x] Spring Boot REST API with JPA and H2
- [x] Python analytics service
- [x] Gemini question endpoint with retry logic
- [x] React dashboard
- [x] Java backend calls the Python service instead of using its own copy of the data
- [x] Docker Compose to start every service with one command
- [ ] Tests
