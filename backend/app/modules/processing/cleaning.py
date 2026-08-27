"""Text cleaning and noise removal for extracted document text.

Page boundaries arrive as form-feed characters (``\\f``, inserted by the
PDF extractor) and are preserved so the chunker can assign page numbers.
"""

import re
import unicodedata
from dataclasses import dataclass, field

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0e-\x1f\x7f]")  # keeps \t \n \f
_HYPHEN_LINEBREAK = re.compile(r"(\w)-\n(\w)")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")
_MULTI_NEWLINE = re.compile(r"\n{3,}")

# Boilerplate lines that carry no knowledge: bare page markers and separators.
_NOISE_LINE = re.compile(
    r"^\s*("
    r"page\s+\d+(\s+of\s+\d+)?"
    r"|-\s*\d+\s*-"
    r"|\d+"
    r"|[-_=*.·•]{3,}"
    r")\s*$",
    re.IGNORECASE,
)


@dataclass(slots=True)
class CleaningResult:
    text: str
    noise_lines_removed: int = 0
    original_chars: int = 0
    stats: dict[str, int] = field(default_factory=dict)


def clean_text(raw: str) -> CleaningResult:
    """Normalize and de-noise extracted text, preserving \\f page breaks."""
    original_chars = len(raw)

    text = unicodedata.normalize("NFKC", raw)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL_CHARS.sub("", text)
    # Re-join words hyphenated across line breaks ("adap-\ntive" -> "adaptive").
    text = _HYPHEN_LINEBREAK.sub(r"\1\2", text)

    noise_removed = 0
    cleaned_pages: list[str] = []
    for page in text.split("\f"):
        kept: list[str] = []
        previous: str | None = None
        for line in page.split("\n"):
            line = _MULTI_SPACE.sub(" ", line).strip()
            if line and _NOISE_LINE.match(line):
                noise_removed += 1
                continue
            if line and line == previous:  # consecutive duplicate lines
                noise_removed += 1
                continue
            kept.append(line)
            previous = line or previous
        cleaned_pages.append(_MULTI_NEWLINE.sub("\n\n", "\n".join(kept)).strip())

    return CleaningResult(
        text="\f".join(cleaned_pages).strip("\f").strip(),
        noise_lines_removed=noise_removed,
        original_chars=original_chars,
    )
