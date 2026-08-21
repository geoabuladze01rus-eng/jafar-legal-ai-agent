from __future__ import annotations

from collections import Counter

from .analytics import PostMetrics


def recommend_formats(metrics: list[tuple[str, PostMetrics]], *, top_n: int = 3) -> list[str]:
    """Return format labels ordered by aggregate performance.

    The caller supplies (format, metrics) pairs. This deliberately keeps the
    scoring layer independent from Telegram and storage.
    """
    scores: dict[str, float] = {}
    counts = Counter()
    for fmt, item in metrics:
        score = item.engagement_rate + item.conversion_rate
        scores[fmt] = scores.get(fmt, 0.0) + score
        counts[fmt] += 1
    ranked = sorted(scores, key=lambda fmt: scores[fmt] / counts[fmt], reverse=True)
    return ranked[:top_n]
