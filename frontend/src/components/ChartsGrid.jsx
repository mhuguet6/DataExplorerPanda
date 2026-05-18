import styles from "./ChartsGrid.module.css";

export default function ChartsGrid({ charts }) {
  return (
    <section>
      <h2 className={styles.heading}>Visualizations</h2>
      <div className={styles.grid}>
        {charts.map((c) => (
          <figure key={c.filename} className={styles.card}>
            <img
              src={`/charts/${c.filename}`}
              alt={c.title}
              className={styles.img}
              loading="lazy"
            />
            <figcaption>
              <h3>{c.title}</h3>
              <p>{c.caption}</p>
            </figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}
