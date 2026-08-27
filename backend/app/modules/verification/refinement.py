"""Response Refinement — the last stage before the Verified Answer.

Annotates the generated answer in place: sentences whose claim was not
supported by any evidence are flagged inline, so a hallucination is
visible in the answer text itself, not just buried in a side-channel
confidence score. Insertion works from the end of the text backwards so
earlier claim spans stay valid as later ones are annotated.
"""

from app.modules.verification.claim_extraction import Claim
from app.modules.verification.types import ClaimVerification

_CONTRADICTED_TAG = " [⚠ contradicted by source]"
_UNVERIFIED_TAG = " [⚠ unverified]"


def refine_response(
    answer_text: str, claims: list[Claim], verifications: list[ClaimVerification]
) -> str:
    """Insert an inline warning after every unsupported claim's sentence."""
    insertions: list[tuple[int, str]] = []
    for claim, verification in zip(claims, verifications):
        if verification.supported:
            continue
        tag = _CONTRADICTED_TAG if verification.verdict == "contradiction" else _UNVERIFIED_TAG
        insertions.append((claim.end, tag))

    refined = answer_text
    for end_index, tag in sorted(insertions, key=lambda pair: pair[0], reverse=True):
        refined = refined[:end_index] + tag + refined[end_index:]
    return refined
