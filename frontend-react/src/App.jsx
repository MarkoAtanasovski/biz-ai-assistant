import { useEffect, useRef, useState } from "react";
import "./App.css";

// Where the Java backend runs. Override with VITE_API_URL.
const API = import.meta.env.VITE_API_URL ?? "/api";

const SUGGESTIONS = [
  "Which region performed best and by how much?",
  "Which product sold best?",
  "How did the first month compare to the latest month?",
  "What will sales be next year?",
];

const eur = (n) =>
  new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(n);

// Every backend error looks like {"detail": "..."}; be defensive anyway,
// because a proxy can answer with HTML and FastAPI validation errors are lists.
async function readBody(res) {
  try {
    return await res.json();
  } catch {
    return null;
  }
}

function errorText(body, status) {
  const d = body?.detail ?? body?.error ?? body?.message;
  if (typeof d === "string") return d;
  if (d) return JSON.stringify(d);
  return `Request failed (${status})`;
}

async function getJson(path) {
  const res = await fetch(`${API}${path}`);
  const body = await readBody(res);
  if (!res.ok) throw new Error(errorText(body, res.status));
  return body;
}

function Breakdown({ title, label, field, rows }) {
  const max = Math.max(0, ...rows.map((r) => r.revenue)) || 1;
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

const formatCall = (c) => `${c.name}(${Object.entries(c.args ?? {}).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ")})`;

export default function App() {
  const [data, setData] = useState(null);
  const [dataError, setDataError] = useState("");
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const [mode, setMode] = useState("replace");
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState(null); // {ok: bool, text: string}
  const fileInput = useRef(null);

  async function loadData() {
    try {
      const [summary, regions, products, months] = await Promise.all([
        getJson("/analytics/summary"),
        getJson("/analytics/by-region"),
        getJson("/analytics/by-product"),
        getJson("/analytics/by-month"),
      ]);
      setData({ summary, regions, products, months });
      setDataError("");
    } catch (e) {
      setDataError(
        e instanceof TypeError
          ? `Can't reach the backend at ${API}. Start the Java service (port 8080) and the Python service (port 8000).`
          : e.message
      );
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  async function upload(e) {
    e.preventDefault();
    const file = fileInput.current?.files?.[0];
    if (!file || uploading) return;
    setUploading(true);
    setUploadMsg(null);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("mode", mode);
      const res = await fetch(`${API}/sales/upload`, { method: "POST", body: form });
      const body = await readBody(res);
      if (!res.ok) throw new Error(errorText(body, res.status));
      setUploadMsg({ ok: true, text: `Imported ${body.imported} rows (${body.totalRows} in the database now).` });
      setResult(null); // the old answer was about the old data
      setError("");
      fileInput.current.value = "";
      await loadData();
    } catch (err) {
      setUploadMsg({
        ok: false,
        text: err instanceof TypeError ? `Can't reach the backend at ${API}.` : err.message,
      });
    } finally {
      setUploading(false);
    }
  }

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
      const body = await readBody(res);
      if (!res.ok) throw new Error(errorText(body, res.status));
      setResult(body);
    } catch (e) {
      setResult(null);
      setError(e instanceof TypeError ? `Can't reach the backend at ${API}.` : e.message);
    } finally {
      setLoading(false);
    }
  }

  const hasData = data && data.summary.number_of_sales_records > 0;

  return (
    <main>
      <header>
        <h1>Sales questions</h1>
        <p className="lede">Ask about your sales data in plain English. The model decides which calculation to run; the numbers come from the data, not the model.</p>
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
            maxLength={500}
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
              Answered by {result.model}
              {result.tool_calls?.length > 0 &&
                ` after running ${result.tool_calls.length} ${result.tool_calls.length === 1 ? "calculation" : "calculations"}`}
              {result.retries > 0 && ` (${result.retries} ${result.retries === 1 ? "retry" : "retries"})`}
            </p>
            {result.tool_calls?.length > 0 && (
              <details className="calls">
                <summary>How this was calculated</summary>
                <ul>
                  {result.tool_calls.map((c, i) => (
                    <li key={i}><code>{formatCall(c)}</code></li>
                  ))}
                </ul>
              </details>
            )}
          </>
        )}
        {!result && !loading && !error && <p className="empty">Pick a suggestion or type a question to get started.</p>}
      </section>

      {dataError && <p className="error" role="alert">{dataError}</p>}

      {data && !hasData && (
        <p className="empty">No sales data yet. Upload a CSV below to get started.</p>
      )}

      {hasData && (
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
            <Breakdown title="By month" label="Month" field="month" rows={data.months} />
          </div>
        </>
      )}

      <form className="upload" onSubmit={upload}>
        <h2>Your own data</h2>
        <p className="hint">
          CSV with the columns <code>region, product, revenue, units_sold, month</code> (month as 2026-07).
          Comma or semicolon files both work. <a href="/sample-sales.csv" download>Download a sample</a>.
        </p>
        <div className="row">
          <input ref={fileInput} type="file" accept=".csv,text/csv" aria-label="CSV file" required />
          <select value={mode} onChange={(e) => setMode(e.target.value)} aria-label="Import mode">
            <option value="replace">Replace existing data</option>
            <option value="append">Add to existing data</option>
          </select>
          <button type="submit" disabled={uploading}>{uploading ? "Uploading" : "Upload"}</button>
        </div>
        {uploadMsg && (
          <p className={uploadMsg.ok ? "ok" : "error"} role={uploadMsg.ok ? "status" : "alert"}>{uploadMsg.text}</p>
        )}
      </form>
    </main>
  );
}
