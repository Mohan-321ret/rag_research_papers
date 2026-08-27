"""Contracts for verifying generated answers against their evidence."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

from app.modules.context_fusion.interfaces import FusedContext


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Outcome of grounding an answer in its retrieved context."""

    grounded: bool
    confidence: float
    unsupported_claims: Sequence[str]


class AnswerVerifier(ABC):
    """Checks whether an answer is supported by the fused context."""

    @abstractmethod
    async def verify(self, answer: str, context: FusedContext) -> VerificationResult: ...
