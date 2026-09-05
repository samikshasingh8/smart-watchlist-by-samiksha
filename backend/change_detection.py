"""
Two independent things happen here:

1. DIFF vs last_seen: "what changed since YOU last looked."
2. FLAGS on current state: "does this deserve attention right now" --
   evaluated against the stock's own recent character, independent of
   whether this device has ever looked at it before.

Thresholds are named constants on purpose -- these are the "what counts
as a meaningful change" judgment calls the brief asks you to own.
"""

BIG_MOVE_PCT = 3.0
RELATIVE_MOVE_STDEV = 2.0
VOLUME_SPIKE_MULTIPLE = 2.0
GAP_PCT = 2.0
BENCHMARK_DIVERGENCE_PCT = 2.0  # percentage-point gap vs Nifty 50's day change

def compute_flags(price: dict) -> list[dict]:
    flags = []
    ltp = price.get("ltp")
    prev_close = price.get("prev_close")
    open_p = price.get("open")
    volume = price.get("volume")
    avg_vol = price.get("avg_volume_20d")
    week52_high = price.get("week52_high")
    week52_low = price.get("week52_low")
    daily_vol_pct = price.get("daily_volatility_pct")

    if ltp is not None and prev_close:
        day_change_pct = (ltp - prev_close) / prev_close * 100

        if abs(day_change_pct) >= BIG_MOVE_PCT:
            flags.append({
                "type": "big_move",
                "severity": "high" if abs(day_change_pct) >= BIG_MOVE_PCT * 1.5 else "medium",
                "message": f"{'Up' if day_change_pct > 0 else 'Down'} {abs(day_change_pct):.1f}% today",
            })
        elif daily_vol_pct and abs(day_change_pct) >= RELATIVE_MOVE_STDEV * daily_vol_pct:
            flags.append({
                "type": "unusual_for_stock",
                "severity": "medium",
                "message": f"Moved {abs(day_change_pct):.1f}% \u2014 unusual for this stock's typical range",
            })

    if week52_high is not None and ltp is not None and ltp >= week52_high:
        flags.append({"type": "week52_high", "severity": "high", "message": "New 52-week high"})
    if week52_low is not None and ltp is not None and ltp <= week52_low:
        flags.append({"type": "week52_low", "severity": "high", "message": "New 52-week low"})

    if avg_vol and volume and avg_vol > 0 and volume >= VOLUME_SPIKE_MULTIPLE * avg_vol:
        flags.append({
            "type": "volume_spike",
            "severity": "medium",
            "message": f"Volume {volume / avg_vol:.1f}x the 20-day average",
        })

    if open_p is not None and prev_close:
        gap_pct = (open_p - prev_close) / prev_close * 100
        if abs(gap_pct) >= GAP_PCT:
            flags.append({
                "type": "gap",
                "severity": "medium",
                "message": f"Gapped {'up' if gap_pct > 0 else 'down'} {abs(gap_pct):.1f}% at open",
            })

    return flags


def compute_diff(price: dict, last_seen: dict | None) -> dict | None:
    if last_seen is None or last_seen.get("ltp") is None:
        return None

    ltp = price.get("ltp")
    prev_ltp = last_seen["ltp"]
    if ltp is None or not prev_ltp:
        return None

    pct_change_since_last_seen = (ltp - prev_ltp) / prev_ltp * 100

    newly_broke_52w_high = (
        price.get("week52_high") is not None
        and ltp >= price["week52_high"]
        and last_seen.get("week52_high") is not None
        and prev_ltp < last_seen["week52_high"]
    )
    newly_broke_52w_low = (
        price.get("week52_low") is not None
        and ltp <= price["week52_low"]
        and last_seen.get("week52_low") is not None
        and prev_ltp > last_seen["week52_low"]
    )

    return {
        "price_then": prev_ltp,
        "price_now": ltp,
        "pct_change_since_last_seen": round(pct_change_since_last_seen, 2),
        "newly_broke_52w_high": newly_broke_52w_high,
        "newly_broke_52w_low": newly_broke_52w_low,
        "seen_at": last_seen.get("seen_at"),
    }


def compute_benchmark_flag(day_change_pct: float | None, index_change_pct: float | None) -> dict | None:
    """Is this stock moving meaningfully differently from the broader
    market today?"""
    if day_change_pct is None or index_change_pct is None:
        return None
    divergence = day_change_pct - index_change_pct
    if abs(divergence) < BENCHMARK_DIVERGENCE_PCT:
        return None
    direction = "Outperforming" if divergence > 0 else "Underperforming"
    severity = "high" if abs(divergence) >= BENCHMARK_DIVERGENCE_PCT * 2 else "medium"
    return {
        "type": "vs_market",
        "severity": severity,
        "message": f"{direction} Nifty 50 by {abs(divergence):.1f}pp today",
    }


_SEVERITY_WEIGHT = {"high": 2, "medium": 1}


def compute_attention_score(item: dict) -> float:
    """Ranks how much this stock deserves the user's attention right now."""
    score = 0.0
    for f in item.get("flags", []):
        score += _SEVERITY_WEIGHT.get(f.get("severity"), 0)

    diff = item.get("diff")
    if diff:
        score += min(abs(diff.get("pct_change_since_last_seen", 0)) / 5, 2)

    return score


def build_digest(items: list[dict]) -> dict:
    total = len(items)
    moved = [
        i for i in items
        if i.get("diff") and i["diff"]["pct_change_since_last_seen"] != 0
    ]
    flagged = [i for i in items if i.get("flags")]
    big_movers = [i for i in items if any(f["type"] == "big_move" for f in i.get("flags", []))]
    week52_events = [
        i for i in items
        if any(f["type"] in ("week52_high", "week52_low") for f in i.get("flags", []))
    ]

    if not moved and not flagged:
        headline = "Nothing new since your last visit."
    else:
        parts = []
        if big_movers:
            parts.append(f"{len(big_movers)} big mover{'s' if len(big_movers) != 1 else ''}")
        if week52_events:
            parts.append(f"{len(week52_events)} at a 52-week extreme")
        remaining_flagged = len(flagged) - len(big_movers) - len(week52_events)
        if remaining_flagged > 0:
            parts.append(f"{remaining_flagged} other flagged")
        headline = ", ".join(parts) + " while you were away." if parts else \
            f"{len(moved)} stock{'s' if len(moved) != 1 else ''} moved since your last visit."

    return {
        "headline": headline,
        "total_watched": total,
        "changed_count": len(moved),
        "flagged_count": len(flagged),
    }