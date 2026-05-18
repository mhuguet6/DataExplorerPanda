import styles from "./DatasetOverview.module.css";

export default function DatasetOverview({ dataset }) {
  const { raw_shape, final_shape, missing_before, transformations } = dataset;
  const missingEntries = Object.entries(missing_before);

  return (
    <section className={styles.panel}>
      <h2>Dataset overview</h2>

      <div className={styles.shape}>
        <div>
          <span className={styles.dim}>Raw</span>
          <span className={styles.bignum}>
            {raw_shape[0]} × {raw_shape[1]}
          </span>
        </div>
        <div className={styles.arrow}>→</div>
        <div>
          <span className={styles.dim}>Cleaned</span>
          <span className={styles.bignum}>
            {final_shape[0]} × {final_shape[1]}
          </span>
        </div>
      </div>

      <h3 className={styles.subhead}>Missing values (before cleaning)</h3>
      {missingEntries.length === 0 ? (
        <p className={styles.dim}>None.</p>
      ) : (
        <ul className={styles.list}>
          {missingEntries.map(([col, n]) => (
            <li key={col}>
              <code>{col}</code>
              <span className={styles.dim}>{n} missing</span>
            </li>
          ))}
        </ul>
      )}

      <h3 className={styles.subhead}>Transformations</h3>
      <div className={styles.transformGrid}>
        <div>
          <div className={styles.tag}>Dropped cols</div>
          <p>{transformations.dropped.join(", ")}</p>
        </div>
        {transformations.filtered && transformations.filtered.length > 0 && (
          <div>
            <div className={styles.tag}>Filtered rows</div>
            <ul className={styles.imputed}>
              {transformations.filtered.map((f, i) => (
                <li key={i}>
                  <code>{f.rule}</code>{" "}
                  <span className={styles.dim}>
                    −{f.rows_removed} rows ({f.reason})
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
        <div>
          <div className={styles.tag}>Added cols ({transformations.added.length})</div>
          <p>{transformations.added.join(", ")}</p>
        </div>
        <div>
          <div className={styles.tag}>Imputed</div>
          <ul className={styles.imputed}>
            {transformations.imputed.map((im) => (
              <li key={im.column}>
                <code>{im.column}</code> <span className={styles.dim}>{im.method}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
