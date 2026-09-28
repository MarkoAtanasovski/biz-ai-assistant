import { useEffect, useState } from "react";
import "./App.css";

// Where the Java backend runs. Override with VITE_API_URL.
const API = import.meta.env.VITE_API_URL ?? "http://localhost:8080/api";

const SUGGESTIONS = [
  "Which region performed best and by how much?",
  "Which product sold best?",
  "How did July compare to August?",
  "What will sales be next year?",
];

const eur = (n) =>
  new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(n);

async function getJson(path) {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`${path} returned ${res.status}`);
  return res.json();
}

function Breakdown({ title, label, field, rows }) {
  const max = Math.max(...rows.map((r) => r.revenue));
  return (
    <section className="breakdown">
      <h2>{title}</h2>
      <table>
        <thead>
          <tr>
            <th>{label}</th>
            <th>Revenue</th>
            <th className="num">Units</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r[field]}>
              <td>{r[field]}</td>
              <td>
                <span className="bar" style={{ width: `${(r.revenue / max) * 100}%` }} aria-hidden="true" />
                <span className="amount">{eur(r.revenue)}</span>
              </td>
              <td className="num">{r.units_sold.toLocaleString("en-GB")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export default function App() {
  const [data, setData] = useState(null);
  const [dataError, setDataError] = useState("");
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    Promise.all([
      getJson("/analytics/summary"),
      getJson("/analytics/by-region"),
      getJson("/analytics/by-product"),
    ])
      .then(([summary, regions, products]) => setData({ summary, regions, products }))
      .catch(() =>
        setDataError(`Can't reach the backend at ${API}. Start the Java service (port 8080) and the Python service (port 8000).`)
      );
  }, []);

  async function ask(text) {
    const q = text.trim();
    if (!q || loading) return;
    setQuestion(q);
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/ai/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail ?? `Request failed (${res.status})`);
      setResult(body);
    } catch (e) {
      setResult(null);
      setError(
        e instanceof TypeError
          ? `Can't reach the backend at ${API}.`
          : e.message
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <header>
        <h1>Sales questions</h1>
        <p className="lede">Ask about July and August sales in plain English. Numbers come from the data, not the model.</p>
      </header>

      <form
        className="ask"
        onSubmit={(e) => {
          e.preventDefault();
          ask(question);
        }}
      >
        <label htmlFor="q">Your question</label>
        <div className="row">
          <input
            id="q"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Which product sold best?"
            autoComplete="off"
          />
          <button type="submit" disabled={loading || !question.trim()}>
            {loading ? "Asking" : "Ask"}
          </button>
        </div>
        <ul className="suggestions">
          {SUGGESTIONS.map((s) => (
            <li key={s}>
              <button type="button" className="chip" onClick={() => ask(s)} disabled={loading}>
                {s}
              </button>
            </li>
          ))}
        </ul>
      </form>

      <section className="answer" aria-live="polite">
        {loading && <p className="pending">Reading the data</p>}
        {error && <p className="error" role="alert">{error}</p>}
        {result && !loading && (
          <>
            <p className="answer-text">{result.answer}</p>
            <p className="meta">
              Answered by {result.model} in {result.attempts} {result.attempts === 1 ? "attempt" : "attempts"}
            </p>
          </>
        )}
        {!result && !loading && !error && <p className="empty">Pick a suggestion or type a question to get started.</p>}
      </section>

      {dataError && <p className="error" role="alert">{dataError}</p>}

      {data && (
        <>
          <dl className="figures">
            <div><dt>Total revenue</dt><dd>{eur(data.summary.total_revenue)}</dd></div>
            <div><dt>Units sold</dt><dd>{data.summary.total_units_sold.toLocaleString("en-GB")}</dd></div>
            <div><dt>Average per sale</dt><dd>{eur(data.summary.average_revenue_per_sale)}</dd></div>
            <div><dt>Sales records</dt><dd>{data.summary.number_of_sales_records}</dd></div>
          </dl>
          <div className="breakdowns">
            <Breakdown title="By region" label="Region" field="region" rows={data.regions} />
            <Breakdown title="By product" label="Product" field="product" rows={data.products} />
          </div>
        </>
      )}
    </main>
  );
}
