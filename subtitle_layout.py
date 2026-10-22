"""Measured line wrapping and pagination for constant-height game overlays."""
from __future__ import annotations


def wrap_measured(text: str, width: int, measure) -> list[str]:
    """Word-wrap within a measured width; split long tokens character by character.

    measure(text) is e.g. Qt QFontMetrics.horizontalAdvance.
    All non-whitespace characters are preserved in order.
    """
    width = max(1, int(width))
    lines = []
    for para in text.replace('\r\n', '\n').split('\n'):
        if not para.strip():
            continue
        current = ''
        for word in para.split():
            candidate = f'{current} {word}' if current else word
            if measure(candidate) <= width:
                current = candidate
                continue
            if current:
                lines.append(current)
                current = ''
            if measure(word) <= width:
                current = word
                continue
            # Long uninterrupted strings / Hangul syllables may exceed width.
            partial = ''
            for char in word:
                if partial and measure(partial + char) > width:
                    lines.append(partial)
                    partial = char
                else:
                    partial += char
            current = partial
        if current:
            lines.append(current)
    return lines


def pages_for_text(text: str, width: int, measure, lines_per_page: int = 2) -> list[str]:
    lines = wrap_measured(text, width, measure)
    if not lines:
        return ['']
    count = max(1, int(lines_per_page))
    return ['\n'.join(lines[i:i + count]) for i in range(0, len(lines), count)]
