import { useMemo, useState } from "react";
import styles from "./UploadClean.module.css";

const ACTIONS = [
  { value: "drop_column", label: "Drop column", needs: "column" },
  { value: "drop_duplicates", label: "Drop duplicate rows", needs: "none" },
  { value: "impute_median", label: "Impute NaN with median", needs: "column" },
  { value: "impute_mean", label: "Impute NaN with mean", needs: "column" },
  { value: "impute_mode", label: "Impute NaN with mode", needs: "column" },
  { value: "impute_value", label: "Impute NaN with value", needs: "column_value" },
  { value: "strip_whitespace", label: "Strip whitespace", needs: "column" },
  { value: "parse_dates", label: "Parse as datetime", needs: "column" },
  { value: "filter_outliers_iqr", label: "Drop outliers (1.5·IQR)", needs: "column" },
];

export default function UploadClean() {
  const [stage, setStage] = useState("idle"); // idle | suggested | cleaned
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [upload, setUpload] = useState(null);     // /api/upload response
  const [rejected, setRejected] = useState({});   // suggestion id -> true if rejected
  const [customSteps, setCustomSteps] = useState([]);
  const [cleaned, setCleaned] = useState(null);   // /api/clean response

  const reset = () => {
    setStage("idle");
    setBusy(false);
    setError(null);
    setUpload(null);
    setRejected({});
    setCustomSteps([]);
    setCleaned(null);
  };

  const handleUpload = async (file) => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await fetch("/api/upload", { method: "POST", body: fd });
      if (!r.ok) throw new Error((await safeError(r)) || `HTTP ${r.status}`);
      const data = await r.json();
      setUpload(data);
      setRejected({});
      setCustomSteps([]);
      setStage("suggested");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const handleApply = async () => {
    if (!upload) return;
    setBusy(true);
    setError(null);
    try {
      const accepted = upload.suggestions
        .filter((s) => !rejected[s.id])
        .map(({ id, reason, ...rest }) => rest); // server doesn't need id/reason
      const steps = [...accepted, ...customSteps];
      const r = await fetch("/api/clean", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: upload.session_id, steps }),
      });
      if (!r.ok) throw new Error((await safeError(r)) || `HTTP ${r.status}`);
      const data = await r.json();
      setCleaned(data);
      setStage("cleaned");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className={styles.wrap}>
      <header className={styles.intro}>
        <h2>Upload & Clean</h2>
        <p>
          Upload any CSV. The backend inspects it with pandas, suggests
          cleaning steps, you decide which to apply (and add your own),
          then download the result.
        </p>
      </header>

      {error && <div className={styles.error}>⚠ {error}</div>}

      {stage === "idle" && <IdleStage busy={busy} onPick={handleUpload} />}

      {stage === "suggested" && upload && (
        <SuggestedStage
          upload={upload}
          rejected={rejected}
          onToggle={(id) => setRejected((r) => ({ ...r, [id]: !r[id] }))}
          customSteps={customSteps}
          setCustomSteps={setCustomSteps}
          busy={busy}
          onApply={handleApply}
          onReset={reset}
        />
      )}

      {stage === "cleaned" && cleaned && upload && (
        <CleanedStage upload={upload} cleaned={cleaned} onReset={reset} />
      )}
    </section>
  );
}

// ---------- Stages ------------------------------------------------------

function IdleStage({ busy, onPick }) {
  const [dragging, setDragging] = useState(false);

  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    onPick(file);
  };

  return (
    <div
      className={`${styles.drop} ${dragging ? styles.dropActive : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
    >
      <p className={styles.dropTitle}>Drop a CSV here</p>
      <p className={styles.dropHint}>or</p>
      <label className={styles.btnPrimary}>
        <input
          type="file"
          accept=".csv,text/csv"
          hidden
          disabled={busy}
          onChange={(e) => onPick(e.target.files?.[0])}
        />
        {busy ? "Uploading…" : "Choose file"}
      </label>
      <p className={styles.dropFoot}>Max 25 MB · CSV only</p>
    </div>
  );
}

function SuggestedStage({
  upload,
  rejected,
  onToggle,
  customSteps,
  setCustomSteps,
  busy,
  onApply,
  onReset,
}) {
  const acceptedCount =
    upload.suggestions.filter((s) => !rejected[s.id]).length + customSteps.length;
  return (
    <div className={styles.stack}>
      <DatasetSummary upload={upload} />

      <div className={styles.panel}>
        <div className={styles.panelHead}>
          <h3>Suggested cleaning steps</h3>
          <span className={styles.count}>
            {acceptedCount} of {upload.suggestions.length + customSteps.length} accepted
          </span>
        </div>
        {upload.suggestions.length === 0 ? (
          <p className={styles.empty}>
            No issues detected. The data looks ready as-is — or add your own
            steps below.
          </p>
        ) : (
          <ul className={styles.suggList}>
            {upload.suggestions.map((s) => {
              const off = !!rejected[s.id];
              return (
                <li
                  key={s.id}
                  className={`${styles.sugg} ${off ? styles.suggOff : ""}`}
                >
                  <button
                    type="button"
                    className={styles.suggToggle}
                    aria-pressed={!off}
                    onClick={() => onToggle(s.id)}
                  >
                    {off ? "Rejected" : "Accepted"}
                  </button>
                  <div className={styles.suggBody}>
                    <code className={styles.suggAction}>{s.action}</code>
                    {s.column && (
                      <code className={styles.suggCol}>{s.column}</code>
                    )}
                    <p className={styles.suggReason}>{s.reason}</p>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <CustomStepEditor
        columns={upload.columns}
        steps={customSteps}
        setSteps={setCustomSteps}
      />

      <div className={styles.actions}>
        <button
          type="button"
          className={styles.btnGhost}
          onClick={onReset}
          disabled={busy}
        >
          Start over
        </button>
        <button
          type="button"
          className={styles.btnPrimary}
          onClick={onApply}
          disabled={busy || acceptedCount === 0}
        >
          {busy ? "Cleaning…" : `Apply ${acceptedCount} step(s)`}
        </button>
      </div>
    </div>
  );
}

function CleanedStage({ upload, cleaned, onReset }) {
  const [b0, c0] = upload.shape;
  const [b1, c1] = cleaned.shape_after;
  return (
    <div className={styles.stack}>
      <div className={styles.panel}>
        <h3>Result</h3>
        <div className={styles.statsRow}>
          <Stat label="Rows" before={b0} after={b1} />
          <Stat label="Columns" before={c0} after={c1} />
          <Stat
            label="Missing"
            before={Object.values(upload.missing).reduce((a, b) => a + b, 0)}
            after={Object.values(cleaned.missing_after).reduce((a, b) => a + b, 0)}
          />
        </div>
        <a
          className={styles.btnPrimary}
          href={cleaned.download_url}
          download
          style={{ alignSelf: "flex-start", marginTop: 14 }}
        >
          Download cleaned CSV
        </a>
      </div>

      <div className={styles.panel}>
        <h3>What happened</h3>
        <ul className={styles.logList}>
          {cleaned.log.map((entry, i) => (
            <li key={i} className={styles[`log_${entry.status}`]}>
              <code className={styles.suggAction}>{entry.action}</code>
              {entry.column && (
                <code className={styles.suggCol}>{entry.column}</code>
              )}
              <span className={styles.logDetail}>{entry.detail}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className={styles.panel}>
        <h3>Preview ({cleaned.preview.length} of {cleaned.shape_after[0]} rows)</h3>
        <PreviewTable rows={cleaned.preview} />
      </div>

      <div className={styles.actions}>
        <button type="button" className={styles.btnGhost} onClick={onReset}>
          Upload another file
        </button>
      </div>
    </div>
  );
}

// ---------- Sub-components ----------------------------------------------

function DatasetSummary({ upload }) {
  const [rows, cols] = upload.shape;
  const missingTotal = Object.values(upload.missing).reduce((a, b) => a + b, 0);
  return (
    <div className={styles.panel}>
      <h3>{upload.filename}</h3>
      <div className={styles.statsRow}>
        <Stat label="Rows" value={rows} />
        <Stat label="Columns" value={cols} />
        <Stat label="Missing values" value={missingTotal} />
      </div>
    </div>
  );
}

function Stat({ label, value, before, after }) {
  const changed = before !== undefined && before !== after;
  return (
    <div className={styles.stat}>
      <div className={styles.statLabel}>{label}</div>
      {before !== undefined ? (
        <div className={styles.statValue}>
          <span className={changed ? styles.statBefore : ""}>{before}</span>
          {changed && <span className={styles.statArrow}>→</span>}
          {changed && <span className={styles.statAfter}>{after}</span>}
        </div>
      ) : (
        <div className={styles.statValue}>{value}</div>
      )}
    </div>
  );
}

function CustomStepEditor({ columns, steps, setSteps }) {
  const [action, setAction] = useState("drop_column");
  const [column, setColumn] = useState(columns[0] || "");
  const [value, setValue] = useState("");
  const def = useMemo(() => ACTIONS.find((a) => a.value === action), [action]);

  const add = () => {
    const step = { action };
    if (def.needs !== "none") step.column = column;
    if (def.needs === "column_value") step.value = value;
    setSteps([...steps, step]);
    setValue("");
  };

  const remove = (i) => setSteps(steps.filter((_, j) => j !== i));

  return (
    <div className={styles.panel}>
      <h3>Add your own step</h3>
      <div className={styles.customRow}>
        <select
          className={styles.input}
          value={action}
          onChange={(e) => setAction(e.target.value)}
        >
          {ACTIONS.map((a) => (
            <option key={a.value} value={a.value}>{a.label}</option>
          ))}
        </select>
        {def.needs !== "none" && (
          <select
            className={styles.input}
            value={column}
            onChange={(e) => setColumn(e.target.value)}
          >
            {columns.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        )}
        {def.needs === "column_value" && (
          <input
            className={styles.input}
            placeholder="fill value"
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
        )}
        <button type="button" className={styles.btnGhost} onClick={add}>
          Add step
        </button>
      </div>

      {steps.length > 0 && (
        <ul className={styles.customList}>
          {steps.map((s, i) => (
            <li key={i} className={styles.customItem}>
              <code className={styles.suggAction}>{s.action}</code>
              {s.column && <code className={styles.suggCol}>{s.column}</code>}
              {s.value !== undefined && (
                <span className={styles.customVal}>= {String(s.value)}</span>
              )}
              <button
                type="button"
                className={styles.removeBtn}
                onClick={() => remove(i)}
                aria-label="Remove step"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function PreviewTable({ rows }) {
  if (!rows.length) return <p className={styles.empty}>No rows.</p>;
  const cols = Object.keys(rows[0]);
  return (
    <div className={styles.scroll}>
      <table className={styles.table}>
        <thead>
          <tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {cols.map((c) => <td key={c}>{formatCell(r[c])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatCell(v) {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") {
    return Number.isInteger(v) ? v : v.toFixed(Math.abs(v) < 1 ? 3 : 2);
  }
  return String(v);
}

async function safeError(r) {
  const text = await r.text().catch(() => "");
  if (!text) return `HTTP ${r.status}`;
  try {
    const data = JSON.parse(text);
    if (data.detail) return `HTTP ${r.status} — ${data.detail}`;
  } catch {
    // Not JSON — likely an HTML error page from the Vite proxy or backend.
    // Surface the first line so we can tell "backend not running" from "bug".
    const snippet = text.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
    if (snippet) return `HTTP ${r.status} — ${snippet.slice(0, 200)}`;
  }
  return `HTTP ${r.status}`;
}
