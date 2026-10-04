"""Coverage checks across tracks; a gap on one track is not necessarily black/silent."""


def uncovered(intervals: list[tuple[int, int]], start: int, end: int) -> list[dict]:
    cursor, gaps = start, []
    for left, right in sorted(intervals):
        left, right = max(start, left), min(end, right)
        if right <= left:
            continue
        if left > cursor:
            gaps.append({"start_frame": cursor, "end_frame": left, "frames": left - cursor})
        cursor = max(cursor, right)
    if cursor < end:
        gaps.append({"start_frame": cursor, "end_frame": end, "frames": end - cursor})
    return gaps
