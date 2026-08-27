"""Context builder — the final stage of context fusion.

Turns the compressed, reranked evidence list into the exact prompt
shape handed to the LLM: one numbered SOURCE block per chunk, carrying
its document/version/page provenance ahead of the content — so the
model (and a human reading the prompt) can tell instantly where each
fact comes from.
"""

from dataclasses import dataclass

from app.modules.context_fusion.types import EvidenceChunk


@dataclass(frozen=True, slots=True)
class ContextBlock:
    """One retrieved chunk as presented to the generator."""

    index: int  # 1-based citation marker, matches "SOURCE {index}"
    document_title: str
    version_number: int
    page_number: int | None
    section: str | None
    content: str


def build_context_blocks(items: list[EvidenceChunk]) -> list[ContextBlock]:
    """Number the final (deduped, reranked, compressed) evidence 1..N."""
    return [
        ContextBlock(
            index=i,
            document_title=item.document_title,
            version_number=item.version_number,
            page_number=item.page_number,
            section=item.section,
            content=item.content,
        )
        for i, item in enumerate(items, start=1)
    ]


def build_context_text(blocks: list[ContextBlock]) -> str:
    """Render blocks as SOURCE N / Document / Version / Page / CONTENT."""
    sections = []
    for block in blocks:
        lines = [
            f"SOURCE {block.index}",
            f"Document: {block.document_title}",
            f"Version: {block.version_number}",
            f"Page: {block.page_number if block.page_number is not None else 'N/A'}",
        ]
        if block.section:
            lines.append(f"Section: {block.section}")
        lines.append("")
        lines.append("CONTENT:")
        lines.append(block.content.strip())
        sections.append("\n".join(lines))
    return "\n\n".join(sections)
