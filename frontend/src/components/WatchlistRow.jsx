import { formatPrice, formatPct, formatVolume, timeAgo } from "../format";

const FLAG_LABELS = {
  big_move: "Big move",
  unusual_for_stock: "Unusual for this stock",
  week52_high: "52w high",
  week52_low: "52w low",
  volume_spike: "Volume spike",
  gap: "Gap",
  vs_market: "vs Nifty",
};

function Sparkline({ points }) {
  if (!points || points.length < 2) return null;

  const width = 72;
  const height = 28;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;

  const coords = points.map((p, i) => {
    const x = (i / (points.length - 1)) * width;
    const y = height - ((p - min) / range) * height;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const trendUp = points[points.length - 1] >= points[0];

  return (
    <svg className="sparkline" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      <polyline
        points={coords.join(" ")}
        fill="none"
        stroke={trendUp ? "var(--gain)" : "var(--loss)"}
        strokeWidth="1.5"
      />
    </svg>
  );
}

export default function WatchlistRow({ item, onRemove }) {
  if (item.error) {
    return (
      <div className="row row--error">
        <div className="row__main">
          <span className="row__symbol">{item.symbol}</span>
          <span className="row__error-msg">{item.error}</span>
        </div>
        <button className="row__remove" onClick={() => onRemove(item.symbol)}>
          Remove
        </button>
      </div>
    );
  }

  const changeClass =
    item.day_change_pct > 0 ? "is-up" : item.day_change_pct < 0 ? "is-down" : "";

  return (
    <div className="row">
      <div className="row__identity">
        <div className="row__name-line">
          <span className="row__symbol">{item.symbol}</span>
          <span className="row__sector">{item.sector}</span>
        </div>
        <span className="row__company">{item.name}</span>
      </div>

      <div className="row__price-block">
        <span className="row__ltp mono">{formatPrice(item.ltp)}</span>
        <span className={`row__change mono ${changeClass}`}>
          {formatPct(item.day_change_pct)}
        </span>
      </div>

      <Sparkline points={item.sparkline} />

      <div className="row__meta">
        <span className="row__meta-line mono">
          H {formatPrice(item.day_high)} · L {formatPrice(item.day_low)}
        </span>
        <span className="row__meta-line mono">Vol {formatVolume(item.volume)}</span>
        <span className="row__timestamp">
          {item.is_market_open ? "Live" : "Last close"} · {timeAgo(item.data_as_of)}
          {item.stale && " · delayed"}
        </span>
      </div>

      <div className="row__signals">
        {item.diff && item.diff.pct_change_since_last_seen !== 0 && (
          <span className="pill pill--diff mono">
            {formatPct(item.diff.pct_change_since_last_seen)} since you last checked
          </span>
        )}

        {item.flags.map((f) => (
          <span key={f.type} className={`pill pill--${f.severity}`}>
            {f.message || FLAG_LABELS[f.type] || f.type}
          </span>
        ))}

        {item.news && item.news.headline ? (<a className="pill pill--news" href={item.news.link || "#"} target="_blank" rel="noopener noreferrer">{"\u{1F4F0} " + item.news.headline}</a>) : null}
      </div>

      <button
        className="row__remove"
        onClick={() => onRemove(item.symbol)}
        aria-label={"Remove " + item.symbol}
      >
        ×
      </button>
    </div>
  );
}