export default function DigestBanner({ digest, loading }) {
  if (loading) {
    return (
      <div className="digest digest--loading">
        <p className="digest__headline">Checking what's changed…</p>
      </div>
    );
  }

  if (!digest || digest.total_watched === 0) {
    return (
      <div className="digest digest--empty">
        <p className="digest__headline">Your watchlist is empty.</p>
        <p className="digest__sub">Add a few stocks to start tracking what changes.</p>
      </div>
    );
  }

  const hasNews = digest.changed_count > 0 || digest.flagged_count > 0;

  return (
    <div className={`digest ${hasNews ? "digest--active" : "digest--quiet"}`}>
      <p className="digest__headline">{digest.headline}</p>
      <p className="digest__sub">
        Watching {digest.total_watched} stock{digest.total_watched !== 1 ? "s" : ""}
        {digest.flagged_count > 0 && ` · ${digest.flagged_count} flagged for attention`}
      </p>
    </div>
  );
}