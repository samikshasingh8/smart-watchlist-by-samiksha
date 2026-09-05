export default function PortfolioInsight({ insight }) {
  if (!insight) return null;

  return (
    <div className="insight">
      <div className="insight__header">
        <span className="insight__title">Portfolio snapshot</span>
        <span className="insight__subtitle">rule-based, not a recommendation</span>
      </div>

      <div className="insight__bars">
        {insight.sector_breakdown.map((s) => (
          <div key={s.sector} className="insight__bar-row">
            <span className="insight__bar-label">{s.sector}</span>
            <div className="insight__bar-track">
              <div
                className="insight__bar-fill"
                style={{ width: `${s.pct}%` }}
              />
            </div>
            <span className="insight__bar-pct mono">{s.pct}%</span>
          </div>
        ))}
      </div>

      {insight.notes.length > 0 && (
        <ul className="insight__notes">
          {insight.notes.map((note, i) => (
            <li key={i}>{note}</li>
          ))}
        </ul>
      )}
    </div>
  );
}