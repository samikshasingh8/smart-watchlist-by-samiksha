"""
Portfolio insight -- the honest version of
"what should I invest in based on my portfolio."

Deliberately NOT prescriptive. This never says "buy X" or "you should
diversify into Y" -- that edges into investment advice, which is legally
loaded territory for a fintech. It only states facts about the watchlist 
that the user can act on however they want:

  - sector concentration ("60% of your watchlist is Banking")
  - directional alignment ("6 of 8 moved the same direction today" --
    a cheap, real proxy for "your watchlist isn't as diversified as it
    looks," since correlated stocks moving together is a concentration
    signal in itself, independent of sector labels)

This is explicitly the fallback for the ML-based recommendation engine
from the original brainstorm -- same instinct, buildable without
training data or a model.
"""

MIN_ITEMS_FOR_INSIGHT = 3
CONCENTRATION_THRESHOLD_PCT = 40.0
ALIGNMENT_THRESHOLD_PCT = 70.0


def compute_portfolio_insight(items: list[dict]) -> dict | None:
    valid_items = [i for i in items if not i.get("error") and i.get("day_change_pct") is not None]

    if len(valid_items) < MIN_ITEMS_FOR_INSIGHT:
        return None

    total = len(valid_items)

    sector_counts: dict[str, int] = {}
    for item in valid_items:
        sector = item.get("sector", "Unknown")
        sector_counts[sector] = sector_counts.get(sector, 0) + 1

    sector_breakdown = sorted(
        [
            {"sector": s, "count": c, "pct": round(c / total * 100, 1)}
            for s, c in sector_counts.items()
        ],
        key=lambda x: -x["pct"],
    )

    top_sector = sector_breakdown[0]
    concentration_flag = top_sector["pct"] >= CONCENTRATION_THRESHOLD_PCT

    up_count = sum(1 for i in valid_items if i["day_change_pct"] > 0)
    down_count = sum(1 for i in valid_items if i["day_change_pct"] < 0)
    aligned_count = max(up_count, down_count)
    aligned_pct = round(aligned_count / total * 100, 1)
    alignment_flag = aligned_pct >= ALIGNMENT_THRESHOLD_PCT and total >= 4
    aligned_direction = "up" if up_count >= down_count else "down"

    notes = []
    if concentration_flag:
        notes.append(
            f"{top_sector['pct']:.0f}% of your watchlist is {top_sector['sector']} "
            f"({top_sector['count']} of {total} stocks)."
        )
    if alignment_flag:
        notes.append(
            f"{aligned_count} of {total} stocks moved {aligned_direction} together today "
            f"-- they may be more correlated than they look."
        )

    return {
        "total_stocks": total,
        "sector_breakdown": sector_breakdown,
        "concentration_flag": concentration_flag,
        "alignment_flag": alignment_flag,
        "notes": notes,
    }