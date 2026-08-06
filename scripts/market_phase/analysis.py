from __future__ import annotations

import math
import statistics
from collections import defaultdict


def aligned_pairs(left: dict[str, float], right: dict[str, float], lag: int = 0):
    dates = sorted(set(left) & set(right))
    if lag > 0:
        return [(left[a], right[b]) for a, b in zip(dates[:-lag], dates[lag:])]
    if lag < 0:
        shift = -lag
        return [(left[b], right[a]) for a, b in zip(dates[:-shift], dates[shift:])]
    return [(left[day], right[day]) for day in dates]


def pearson(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < 3:
        return None
    xs, ys = zip(*pairs)
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    numerator = sum((x - mx) * (y - my) for x, y in pairs)
    denominator = math.sqrt(
        sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)
    )
    return None if denominator == 0 else max(-1.0, min(1.0, numerator / denominator))


def ranks(values: tuple[float, ...]) -> tuple[float, ...]:
    ordered = sorted(range(len(values)), key=values.__getitem__)
    result = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[index]]:
            end += 1
        rank = (index + end - 1) / 2 + 1
        for position in ordered[index:end]:
            result[position] = rank
        index = end
    return tuple(result)


def spearman(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < 3:
        return None
    xs, ys = zip(*pairs)
    return pearson(list(zip(ranks(xs), ranks(ys))))


def daily_returns(prices: dict[str, float]) -> dict[str, float]:
    result: dict[str, float] = {}
    previous = None
    for day, price in sorted(prices.items()):
        if previous is not None and previous > 0 and price > 0:
            result[day] = math.log(price / previous)
        previous = price
    return result


def normalize(prices: dict[str, float]) -> dict[str, float]:
    valid = [(day, value) for day, value in sorted(prices.items()) if value > 0]
    if not valid:
        return {}
    base = valid[0][1]
    return {day: round(value / base * 100, 6) for day, value in valid}


def correlation_matrix(
    returns: dict[str, dict[str, float]], method: str = "pearson", minimum: int = 20
) -> tuple[dict[str, dict[str, float | None]], dict[str, dict[str, int]]]:
    calculate = pearson if method == "pearson" else spearman
    symbols = sorted(returns)
    matrix = {symbol: {} for symbol in symbols}
    samples = {symbol: {} for symbol in symbols}
    for left in symbols:
        for right in symbols:
            pairs = aligned_pairs(returns[left], returns[right])
            samples[left][right] = len(pairs)
            matrix[left][right] = calculate(pairs) if len(pairs) >= minimum else None
    return matrix, samples


def average_distance(
    left: set[str], right: set[str], matrix: dict[str, dict[str, float | None]]
) -> float:
    values = [
        1 - matrix[a][b]
        for a in left for b in right if matrix[a][b] is not None
    ]
    return statistics.fmean(values) if values else 2.0


def cluster(matrix: dict[str, dict[str, float | None]], target: int = 6) -> dict[str, int]:
    groups = [{symbol} for symbol in sorted(matrix)]
    while len(groups) > max(1, min(target, len(groups))):
        choices = [
            (average_distance(groups[i], groups[j], matrix), i, j)
            for i in range(len(groups)) for j in range(i + 1, len(groups))
        ]
        _, i, j = min(choices)
        groups[i] |= groups[j]
        del groups[j]
    return {
        symbol: cluster_id
        for cluster_id, group in enumerate(groups, start=1)
        for symbol in sorted(group)
    }


def lead_lag(
    returns: dict[str, dict[str, float]], max_lag: int = 10, minimum: int = 20
) -> list[dict]:
    symbols = sorted(returns)
    results = []
    for index, left in enumerate(symbols):
        for right in symbols[index + 1:]:
            candidates = []
            for lag in range(-max_lag, max_lag + 1):
                pairs = aligned_pairs(returns[left], returns[right], lag)
                value = pearson(pairs) if len(pairs) >= minimum else None
                if value is not None:
                    candidates.append((value, lag, len(pairs)))
            if not candidates:
                continue
            value, lag, samples = max(candidates, key=lambda item: (item[0], -abs(item[1])))
            results.append({
                "left": left, "right": right, "lag": lag,
                "correlation": round(value, 6), "samples": samples,
                "leader": left if lag > 0 else right if lag < 0 else None,
                "follower": right if lag > 0 else left if lag < 0 else None,
            })
    return sorted(results, key=lambda row: row["correlation"], reverse=True)


def streaks(returns: dict[str, float]) -> dict[str, list[int]]:
    output = {"up": [], "down": []}
    direction, length = None, 0
    for value in returns.values():
        current = "up" if value > 0 else "down" if value < 0 else None
        if current == direction:
            length += 1
        else:
            if direction:
                output[direction].append(length)
            direction, length = current, 1 if current else 0
    if direction:
        output[direction].append(length)
    return output


def cycle_summary(prices: dict[str, float], returns: dict[str, float]) -> dict:
    values = list(sorted(prices.items()))
    peaks, troughs = [], []
    for index in range(1, len(values) - 1):
        previous, current, following = values[index - 1][1], values[index][1], values[index + 1][1]
        if current > previous and current > following:
            peaks.append(index)
        if current < previous and current < following:
            troughs.append(index)
    return {
        **streaks(returns),
        "peak_intervals": [right - left for left, right in zip(peaks, peaks[1:])],
        "trough_intervals": [right - left for left, right in zip(troughs, troughs[1:])],
        "peak_to_trough": [
            next((trough - peak for trough in troughs if trough > peak), None)
            for peak in peaks
        ],
        "autocorrelation": {
            str(lag): pearson(list(zip(list(returns.values())[:-lag], list(returns.values())[lag:])))
            for lag in range(1, min(21, len(returns)))
        },
    }


def top_pairs(matrix: dict[str, dict[str, float | None]], highest: bool, limit: int = 15):
    symbols = sorted(matrix)
    rows = [
        {"left": left, "right": right, "correlation": round(matrix[left][right], 6)}
        for i, left in enumerate(symbols)
        for right in symbols[i + 1:]
        if matrix[left][right] is not None
    ]
    return sorted(rows, key=lambda row: row["correlation"], reverse=highest)[:limit]
