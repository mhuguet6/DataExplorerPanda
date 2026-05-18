import styles from "./KeyMetrics.module.css";

const METRIC_DEFS = [
  { key: "total_passengers", label: "Passengers", fmt: (v) => v.toLocaleString() },
  { key: "survival_rate", label: "Survival rate", fmt: (v) => `${(v * 100).toFixed(1)}%` },
  { key: "avg_age", label: "Average age", fmt: (v) => `${v}` },
  { key: "avg_fare", label: "Average fare", fmt: (v) => `$${v}` },
  { key: "pct_female", label: "% Female", fmt: (v) => `${(v * 100).toFixed(1)}%` },
  { key: "pct_first_class", label: "% 1st class", fmt: (v) => `${(v * 100).toFixed(1)}%` },
];

export default function KeyMetrics({ metrics }) {
  return (
    <section className={styles.row}>
      {METRIC_DEFS.map(({ key, label, fmt }) => (
        <div key={key} className={styles.card}>
          <div className={styles.label}>{label}</div>
          <div className={styles.value}>{fmt(metrics[key])}</div>
        </div>
      ))}
    </section>
  );
}
