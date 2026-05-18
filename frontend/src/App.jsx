import { useEffect, useState } from "react";
import DatasetOverview from "./components/DatasetOverview.jsx";
import KeyMetrics from "./components/KeyMetrics.jsx";
import KeyFindings from "./components/KeyFindings.jsx";
import ChartsGrid from "./components/ChartsGrid.jsx";
import TablesGrid from "./components/TablesGrid.jsx";
import TabBar from "./components/TabBar.jsx";
import PipelineView from "./components/PipelineView.jsx";
import styles from "./App.module.css";

const TABS = [
  { id: "dashboard", label: "Dashboard" },
  { id: "pipeline", label: "Pipeline" },
];

export default function App() {
  const [insights, setInsights] = useState(null);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("dashboard");

  useEffect(() => {
    fetch("/insights.json")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setInsights)
      .catch((e) => setError(e.message));
  }, []);

  if (error) {
    return (
      <main className={styles.shell}>
        <div className={styles.error}>
          <h2>Couldn't load insights</h2>
          <p>{error}</p>
          <p className={styles.hint}>
            Did you run <code>python backend/src/export.py</code> and{" "}
            <code>npm run sync</code>?
          </p>
        </div>
      </main>
    );
  }

  if (!insights) {
    return (
      <main className={styles.shell}>
        <div className={styles.loading}>Loading…</div>
      </main>
    );
  }

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <h1>🐼 Data Explorer Panda</h1>
        <p className={styles.subtitle}>
          Exploring the <strong>{insights.dataset.name}</strong> dataset —{" "}
          {insights.dataset.final_shape[0]} passengers,{" "}
          {insights.dataset.final_shape[1]} features
        </p>
      </header>

      <TabBar tabs={TABS} active={activeTab} onChange={setActiveTab} />

      {activeTab === "dashboard" && (
        <>
          <KeyMetrics metrics={insights.metrics} />

          <section className={styles.twoCol}>
            <DatasetOverview dataset={insights.dataset} />
            <KeyFindings findings={insights.key_findings} />
          </section>

          <ChartsGrid charts={insights.charts} />

          <TablesGrid tables={insights.tables} />
        </>
      )}

      {activeTab === "pipeline" && (
        <PipelineView sections={insights.pipeline_sections} />
      )}

      <footer className={styles.footer}>
        Source: {insights.dataset.source}
      </footer>
    </main>
  );
}
