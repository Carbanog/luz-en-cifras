"""Index published price windows without hiding overlapping or missing quotes."""

from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import UTC, datetime

from .models import EnergyRate


class PriceIndex:
    """Select potentially overlapping quotes in logarithmic time plus matches."""

    def __init__(self, rates: tuple[EnergyRate, ...]) -> None:
        grouped: dict[str, list[EnergyRate]] = defaultdict(list)
        for rate in rates:
            grouped[rate.group_id].append(rate)
        self._groups: dict[str, tuple[list[datetime], list[datetime], tuple[EnergyRate, ...]]] = {}
        for group, values in grouped.items():
            ordered = tuple(sorted(values, key=lambda item: item.valid_from.astimezone(UTC)))
            starts = [item.valid_from.astimezone(UTC) for item in ordered]
            # Prefix maxima keep older overlapping quotes in the candidate set.
            # Looking back just one quote would silently accept invalid overlaps.
            ends = []
            maximum = datetime.min.replace(tzinfo=UTC)
            for item in ordered:
                maximum = max(
                    maximum,
                    item.valid_to.astimezone(UTC)
                    if item.valid_to
                    else datetime.max.replace(tzinfo=UTC),
                )
                ends.append(maximum)
            self._groups[group] = starts, ends, ordered

    def window(self, group: str, start: datetime, end: datetime) -> tuple[EnergyRate, ...]:
        data = self._groups.get(group)
        if data is None:
            return ()
        starts, ends, ordered = data
        left = bisect_right(ends, start.astimezone(UTC))
        right = bisect_left(starts, end.astimezone(UTC))
        return ordered[left:right]

    def instant(self, group: str, stamp: datetime) -> tuple[EnergyRate, ...]:
        data = self._groups.get(group)
        if data is None:
            return ()
        starts, ends, ordered = data
        stamp = stamp.astimezone(UTC)
        return ordered[bisect_right(ends, stamp) : bisect_right(starts, stamp)]
