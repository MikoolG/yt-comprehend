"""Shared helpers for formatting transcripts."""


def format_time(seconds: float) -> str:
    """Format seconds as MM:SS or HH:MM:SS."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def group_segments_by_interval(
    segments,
    interval: int = 30,
    end_time: float | None = None,
    bold: bool = False,
) -> str:
    """Group timed segments into N-second interval blocks.

    Args:
        segments: Iterable of objects with `.start` (float) and `.text` (str)
        interval: Seconds per block
        end_time: Total duration for the final label, or None for "end"
        bold: Wrap the timestamp header in markdown bold

    Returns:
        Text grouped under `[MM:SS - MM:SS]` headers
    """
    segments = list(segments)
    if not segments:
        return ""

    def header(start: float, end_label: str) -> str:
        text = f"[{format_time(start)} - {end_label}]"
        return f"**{text}**" if bold else text

    lines = []
    current_interval_start = 0
    current_texts = []

    for seg in segments:
        start = getattr(seg, "start", 0)
        text = getattr(seg, "text", str(seg)).strip()

        interval_num = int(start // interval)
        expected_start = interval_num * interval

        if expected_start > current_interval_start and current_texts:
            end = current_interval_start + interval
            lines.append(header(current_interval_start, format_time(end)))
            lines.append(" ".join(current_texts))
            lines.append("")
            current_texts = []
            current_interval_start = expected_start

        current_texts.append(text)

    if current_texts:
        end_label = format_time(end_time) if end_time else "end"
        lines.append(header(current_interval_start, end_label))
        lines.append(" ".join(current_texts))

    return "\n".join(lines)
