import styles from "./KeyFindings.module.css";

export default function KeyFindings({ findings }) {
  return (
    <section className={styles.panel}>
      <h2>Key findings</h2>
      <ul className={styles.list}>
        {findings.map((text, i) => (
          <li key={i}>
            <span className={styles.bullet}>{i + 1}</span>
            <span>{text}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
