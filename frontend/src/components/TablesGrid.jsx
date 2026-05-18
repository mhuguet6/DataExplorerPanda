import styles from "./TablesGrid.module.css";

// Tables come in two flavors in the JSON payload:
//   1. row-based:    { title, rows: [{col1:..., col2:...}, ...] }
//   2. matrix-based: { title, matrix: { rowKey: { colKey: value } } }
// We dispatch on which key is present.
export default function TablesGrid({ tables }) {
  const entries = Object.entries(tables);
  return (
    <section>
      <h2 className={styles.heading}>Tables</h2>
      <div className={styles.grid}>
        {entries.map(([key, t]) => (
          <div key={key} className={styles.card}>
            <h3>{t.title}</h3>
            {t.rows ? <RowTable rows={t.rows} /> : <MatrixTable matrix={t.matrix} />}
          </div>
        ))}
      </div>
    </section>
  );
}

function RowTable({ rows }) {
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

function MatrixTable({ matrix }) {
  const rowKeys = Object.keys(matrix);
  const colKeys = rowKeys.length ? Object.keys(matrix[rowKeys[0]]) : [];
  return (
    <div className={styles.scroll}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th></th>
            {colKeys.map((c) => <th key={c}>{c}</th>)}
          </tr>
        </thead>
        <tbody>
          {rowKeys.map((r) => (
            <tr key={r}>
              <th>{r}</th>
              {colKeys.map((c) => <td key={c}>{formatCell(matrix[r][c])}</td>)}
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
    // Show small fractions with 3 decimals, otherwise default toString
    return Number.isInteger(v) ? v : v.toFixed(Math.abs(v) < 1 ? 3 : 2);
  }
  return String(v);
}
