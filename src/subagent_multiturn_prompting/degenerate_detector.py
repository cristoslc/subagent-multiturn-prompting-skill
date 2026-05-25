"""Degenerate output detection."""


def is_degenerate(text: str) -> bool:
    """Check if output is a repetitive loop rather than meaningful text."""
    lines = text.strip().split("\n")
    if len(lines) > 20:
        # Check for identical repeating 5-line blocks
        chunks = [lines[i : i + 5] for i in range(0, len(lines), 5)]
        for chunk in chunks:
            stripped = [l.strip() for l in chunk if l.strip()]
            if len(stripped) >= 3 and len(set(stripped)) == 1:
                return True

    if len(text) >= 200:
        # Check for copy-paste mid-output
        half = len(text) // 2
        if text[:100] == text[half:half + 100]:
            return True

    return False
