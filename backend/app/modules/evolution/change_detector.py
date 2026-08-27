"""Change Detector — the gate at the front of the evolution pipeline.

Decides, from content hashes alone, whether there is anything to compare
at all: a brand-new document has no prior version; a re-upload with an
identical hash never reaches here (``DocumentService`` deduplicates
before creating a version). What lands here is always a genuine change —
this stage just classifies it before the heavier diff/drift/conflict
stages run.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChangeDetectionResult:
    is_new_document: bool  # no previous version exists at all
    previous_hash: str | None
    new_hash: str


def detect_change(previous_hash: str | None, new_hash: str) -> ChangeDetectionResult:
    return ChangeDetectionResult(
        is_new_document=previous_hash is None,
        previous_hash=previous_hash,
        new_hash=new_hash,
    )
