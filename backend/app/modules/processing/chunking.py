"""Structure-aware semantic chunking.

Splits cleaned text into retrieval units that respect document structure:
section headings start new chunks and are carried as chunk context, page
boundaries (``\\f``) are tracked for citations, paragraphs are packed up
to a token budget, and oversized paragraphs are split at sentence
boundaries with sentence overlap between adjacent chunks.
"""

import re
from dataclasses import dataclass

# A rough but serviceable token estimate for budget purposes.
_CHARS_PER_TOKEN = 4

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")

# Headings: markdown (#), numbered ("2.", "3.1"), or short ALL-CAPS lines.
_MD_HEADING = re.compile(r"^#{1,6}\s+(?P<title>.+)$")
_NUMBERED_HEADING = re.compile(r"^(?P<num>\d+(\.\d+)*)[.)]?\s+(?P<title>[A-Z][^\n]{0,80})$")
_SHEET_HEADING = re.compile(r"^\[Sheet:\s*(?P<title>[^\]]+)\]$")


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    """A chunk produced by the splitter, before persistence."""

    chunk_index: int
    content: str
    token_estimate: int
    page_number: int | None
    section: str | None


def _heading_of(line: str) -> str | None:
    line = line.strip()
    if not line or len(line) > 100:
        return None
    for pattern in (_MD_HEADING, _SHEET_HEADING, _NUMBERED_HEADING):
        match = pattern.match(line)
        if match:
            return match.group("title").strip()
    words = line.split()
    if 1 <= len(words) <= 8 and line.isupper():
        return line.title()
    return None


@dataclass(slots=True)
class _Block:
    text: str
    page: int
    section: str | None


class SemanticChunker:
    def __init__(self, *, target_tokens: int = 300, overlap_sentences: int = 1) -> None:
        self._target_chars = target_tokens * _CHARS_PER_TOKEN
        self._overlap_sentences = overlap_sentences

    def split(self, text: str) -> list[ChunkDraft]:
        blocks = self._blocks(text)
        if not blocks:
            return []

        chunks: list[ChunkDraft] = []
        current: list[_Block] = []
        current_len = 0

        def flush() -> None:
            nonlocal current, current_len
            if not current:
                return
            content = "\n\n".join(b.text for b in current).strip()
            if content:
                chunks.append(
                    ChunkDraft(
                        chunk_index=len(chunks),
                        content=content,
                        token_estimate=max(1, len(content) // _CHARS_PER_TOKEN),
                        page_number=current[0].page,
                        section=current[0].section,
                    )
                )
            current = []
            current_len = 0

        previous_section: str | None = None
        for block in blocks:
            starts_new_section = block.section != previous_section
            if current and (starts_new_section or current_len + len(block.text) > self._target_chars):
                overlap = self._overlap_tail(current) if not starts_new_section else None
                flush()
                if overlap is not None:
                    current = [overlap]
                    current_len = len(overlap.text)
            current.append(block)
            current_len += len(block.text)
            previous_section = block.section
        flush()
        return chunks

    def _blocks(self, text: str) -> list[_Block]:
        """Paragraph blocks annotated with page number and current section."""
        blocks: list[_Block] = []
        section: str | None = None
        for page_index, page in enumerate(text.split("\f"), start=1):
            for paragraph in re.split(r"\n\s*\n", page):
                paragraph = paragraph.strip()
                if not paragraph:
                    continue
                heading = _heading_of(paragraph.split("\n", 1)[0])
                if heading is not None:
                    section = heading
                    body = paragraph.split("\n", 1)[1].strip() if "\n" in paragraph else ""
                    if not body:
                        continue
                    paragraph = body
                blocks.extend(
                    _Block(text=piece, page=page_index, section=section)
                    for piece in self._split_oversized(paragraph)
                )
        return blocks

    def _split_oversized(self, paragraph: str) -> list[str]:
        if len(paragraph) <= self._target_chars:
            return [paragraph]
        sentences = _SENTENCE_SPLIT.split(paragraph)
        pieces: list[str] = []
        buffer = ""
        for sentence in sentences:
            if buffer and len(buffer) + len(sentence) + 1 > self._target_chars:
                pieces.append(buffer.strip())
                buffer = ""
            buffer += (" " if buffer else "") + sentence
        if buffer.strip():
            pieces.append(buffer.strip())
        return pieces

    def _overlap_tail(self, blocks: list[_Block]) -> _Block | None:
        """Carry the last sentence(s) into the next chunk for continuity."""
        if self._overlap_sentences <= 0:
            return None
        last = blocks[-1]
        sentences = _SENTENCE_SPLIT.split(last.text)
        tail = " ".join(sentences[-self._overlap_sentences :]).strip()
        if not tail or len(tail) > self._target_chars // 2:
            return None
        return _Block(text=tail, page=last.page, section=last.section)
