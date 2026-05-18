import styles from "./PipelineView.module.css";

export default function PipelineView({ sections }) {
  let stepCounter = 0;

  return (
    <div className={styles.wrap}>
      <header className={styles.intro}>
        <h2>How the data was processed</h2>
        <p>
          Every number on the Dashboard tab comes from the pandas pipeline below.
          Each step shows <em>what</em> the code does, <em>why</em> we did it
          that way, and the resulting effect on the dataset.
        </p>
      </header>

      {sections.map((section) => (
        <section key={section.id} className={styles.section}>
          <div className={styles.sectionHead}>
            <h3>{section.title}</h3>
            <p>{section.summary}</p>
          </div>

          <ol className={styles.steps}>
            {section.steps.map((step) => {
              stepCounter += 1;
              return (
                <li key={step.title} className={styles.step}>
                  <div className={styles.stepNum}>{stepCounter}</div>
                  <div className={styles.stepBody}>
                    <h4>{step.title}</h4>
                    <p className={styles.why}>
                      <span className={styles.tag}>Why</span> {step.why}
                    </p>
                    <pre className={styles.code}>
                      <code>{step.code}</code>
                    </pre>
                    <p className={styles.result}>
                      <span className={styles.tagOk}>Result</span> {step.result}
                    </p>
                  </div>
                </li>
              );
            })}
          </ol>
        </section>
      ))}
    </div>
  );
}
