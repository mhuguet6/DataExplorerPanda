import styles from "./TabBar.module.css";

export default function TabBar({ tabs, active, onChange }) {
  return (
    <nav className={styles.bar} role="tablist">
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={active === t.id}
          className={`${styles.tab} ${active === t.id ? styles.active : ""}`}
          onClick={() => onChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </nav>
  );
}
